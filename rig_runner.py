#!/usr/bin/python
"""Rig Runner - this is the main control loop for running the
Photogrammetry rig. Here we control:
    1. Camera Stepper - position of the camera
    2. Model stepper - rotational angle of the model
    3. Camera USB - USB control of camera
    4. Camera Lighting - 'ring light' for taking pictures
"""
import atexit
import time
import json
import beanstalkc as beanstalk
from rpihat import limit_switch  # our limit switches
from rpihat.Raspi_PWM_Servo_Driver import PWM
from rpihat.pimotorhat import Raspi_StepperMotor, Raspi_MotorHAT
from util import calculate_steps
from cameractrl import camera

CAMERA_STEPPER_MOTOR_NUM = 2
CAMERA_STEPPER_MOTOR_SPEED = 240  # rpm
MODEL_STEPPER_MOTOR_NUM = 1
MOTOR_HAT_I2C_ADDR = 0x6F
MOTOR_HAT_I2C_FREQ = 1600
CCW_MAX_SWITCH = limit_switch.LimitSwitch(18, 'CCW')  # furthest CCW rotation allowed
CW_MAX_SWITCH = limit_switch.LimitSwitch(4, 'CW')  # furthest CW rotation allowed
BEANSTALK = None
CANCEL_QUEUE = 'cancel'
STATUS_QUEUE = 'status'
TASK_QUEUE = 'work'
STEP_CAMERA_CCW = Raspi_MotorHAT.FORWARD
STEP_CAMERA_CW = Raspi_MotorHAT.BACKWARD
STEP_MODEL_CCW = Raspi_MotorHAT.FORWARD
STEP_MODEL_CW = Raspi_MotorHAT.BACKWARD


def configure_beanstalk():
    """set up our beanstalk queue for inter-process
    messages"""
    queue = beanstalk.Connection(host='localhost', port=14711)
    queue.watch(CANCEL_QUEUE) # tube that'll contain cancel requests
    return queue


def clear_all_queues(queue: beanstalk.Connection) -> None:
    """clear out all the currently known tubes"""
    for tube in [CANCEL_QUEUE, STATUS_QUEUE, TASK_QUEUE]:
        queue.use(tube)
        while True:
            dummy = queue.reserve(timeout=0)
            if dummy:
                dummy.delete()
            else:
                break


def yield_function(direction: int) -> dict:
    """Called in timing loops to perform checks
    to see if we need to breakout. We need the direction
    of travel since we may want to ignore a limit
    switch that has been triggered.

    For now just checking limit switches, eventually
    we need to process other input like a cancel
    request from a web app"""
    try:
        if BEANSTALK:  # if we have a queue, check for user cancel
            BEANSTALK.watch(CANCEL_QUEUE)
            cancel_job = BEANSTALK.reserve(timeout=0) # don't wait
            if cancel_job is not None:
                body = cancel_job.body
                cancel_job.delete()
                print('Cancel received: {0}'.format(body))
                return {'exit':'cancel'}

    except beanstalk.CommandFailed:
        pass
    except beanstalk.DeadlineSoon:
        # save to ignore since it just means there's something pending
        pass

    if direction == Raspi_MotorHAT.FORWARD:
        if CCW_MAX_SWITCH.is_pressed():
            return {'exit': 'ccw'}
        return None

    if CW_MAX_SWITCH.is_pressed():
        return {'exit': 'cw'}
    return None


# Create our motor hat controller object, it'll house two
# stepper motor objects
MOTOR_HAT = Raspi_MotorHAT(stepper_class=Raspi_StepperMotor,
                           pwm_class=PWM,
                           yield_func=yield_function,
                           addr=MOTOR_HAT_I2C_ADDR,
                           freq=MOTOR_HAT_I2C_FREQ,
                           debug=False)


def turn_off_motors():
    """disable motors. This will be called 'at exit' so
    motors don't overheat when idle and energized"""
    MOTOR_HAT.release_motors()


atexit.register(turn_off_motors)


def move_camera(step_dir: int, switch: limit_switch.LimitSwitch) -> int:
    """home the camera. This means moving in a direction and checking
    for that direction's limit switch"""
    camera_stepper = MOTOR_HAT.getStepper(CAMERA_STEPPER_MOTOR_NUM)
    starting_stepper_pos = camera_stepper.stepping_counter
    while not switch.is_pressed():
        camera_stepper.step(1000, step_dir, Raspi_MotorHAT.DOUBLE)

    traveled_steps = camera_stepper.stepping_counter - starting_stepper_pos
    if step_dir == STEP_CAMERA_CCW:
        camera_stepper.stepping_counter = 0

    return traveled_steps


def ccw_camera_home(queue: beanstalk.Connection) -> int:
    """home the camera in the counter-clockwise direction"""
    post_status(queue, "CCW homing")
    return move_camera(STEP_CAMERA_CCW, CCW_MAX_SWITCH)


def cw_camera_home(queue: beanstalk.Connection) -> int:
    """home the camera in the clockwise direction"""
    post_status(queue, "CW homing")
    return move_camera(STEP_CAMERA_CW, CW_MAX_SWITCH)


def home_camera(queue: beanstalk.Connection) -> int:
    """home the camera. This will move the camera to the two
    extreme positions and return how many steps it took to
    span the extremes"""
    ccw_camera_home(queue)
    travel = abs(cw_camera_home(queue))
    post_status(queue, 'homing complete, {0} steps'.format(travel))
    return travel


def post_status(queue: beanstalk.Connection, message: str) -> None:
    """post a simple message to whomever is listening"""
    queue.use(STATUS_QUEUE)
    status_json = json.dumps({'msg': message})
    queue.put(status_json)
    print(message)


def take_picture(my_camera: camera.gp.camera, queue: beanstalk.Connection, rotation: int, declination: int) -> None:
    """take the picture"""
    post_status(queue, "taking picture R{0}:D{1}".
                format(rotation, declination))
    file_name = camera.take_picture(my_camera, rotation, declination)
    post_status(queue, "Filename={0}".format(file_name))


def wait_for_work(queue: beanstalk.Connection) -> str:
    """wait for work, return json"""
    while True:
        queue.watch(TASK_QUEUE)
        job = queue.reserve(timeout=0)
        if job:
            job_json = job.body
            job.delete()  # remove from the queue
            return json.loads(job_json)

        time.sleep(0.001) # sleep for 1 ms to share the computer


def photograph_model(declination_divisions: int,
                     rotation_divisions: int,
                     remaining_declination_steps: int,
                     steps_per_declination: int,
                     steps_per_rotation: int,
                     status_queue: beanstalk.Connection,
                     rotate_stepper: Raspi_StepperMotor,
                     camera_stepper: Raspi_StepperMotor) -> None:
    """here's where we rotate the model, declinate the camera
    and take pictures"""
    try:
        rig_camera = camera.init_camera()
        if not rig_camera:
            post_status(status_queue, "Did not get camera object!")
            return
    except camera.gp.GPhoto2Error:
        post_status(status_queue, 'Camera is off!')
        return

    for declination in range(0, declination_divisions):
        post_status(status_queue, "rotating model")
        for rotation in range(0, rotation_divisions):
            take_picture(my_camera=rig_camera,
                         queue=status_queue,
                         rotation=rotation, declination=declination)
            forced_exit = rotate_stepper.step(steps_per_rotation, STEP_MODEL_CCW,
                                              Raspi_MotorHAT.DOUBLE)
            if forced_exit and forced_exit['exit'] == 'cancel':
                return  # forced exit

        # if we hit an exit condition while rotating, or there are no more
        # steps, then bale out
        if steps_per_declination == 0:
            return

        # okay, we have work to do, position the camera
        forced_exit = camera_stepper.step(steps_per_declination, STEP_CAMERA_CCW,
                                          Raspi_MotorHAT.DOUBLE)
        if forced_exit:
            # if this is the last position, we expect to hit the end-stop
            if remaining_declination_steps != steps_per_declination:
                print("...end stop hit! {0}/{1}".
                      format(remaining_declination_steps,
                             steps_per_declination))
                return
            if forced_exit['exit'] != 'ccw':
                return

        # the declination motion may not be perfect fit so don't overstep
        remaining_declination_steps -= steps_per_declination
        if remaining_declination_steps < steps_per_declination:
            steps_per_declination = remaining_declination_steps

        # free up the camera now that we don't need it
        camera.exit_camera(rig_camera)


def main():
    """This is the main entry point of the program, where all the magic happens"""
    # okay time to run things
    camera_stepper = MOTOR_HAT.getStepper(CAMERA_STEPPER_MOTOR_NUM)
    camera_stepper.setSpeed(CAMERA_STEPPER_MOTOR_SPEED)

    rotate_stepper = MOTOR_HAT.getStepper(MODEL_STEPPER_MOTOR_NUM)
    rotate_stepper.setSpeed(CAMERA_STEPPER_MOTOR_SPEED)

    global BEANSTALK
    BEANSTALK = configure_beanstalk()
    clear_all_queues(BEANSTALK)

    # print out status of end-stop switches
    print(CCW_MAX_SWITCH.__str__())
    print(CW_MAX_SWITCH.__str__())

    print("\n**********************")
    print("\n** waiting for jobs **")
    print("\n**********************\n")
    is_homed = False
    declination_travel_steps = 0 # number of steps between min/max endstops
    forced_exit = None
    while True:
        job_dict = wait_for_work(BEANSTALK)
        if job_dict['task'] == 'home':
            declination_travel_steps = home_camera(queue=BEANSTALK)
            is_homed = True
            continue

        max_pictures = 200

        if job_dict['task'] == 'scan':
            try:
                post_status(BEANSTALK, "scan command received!")
                declination_divisions = int(job_dict['steps']['declination'])
                rotation_divisions = int(job_dict['steps']['rotation'])
                start = int(job_dict['offsets']['start'])
                stop = int(job_dict['offsets']['stop'])

                total_pictures_to_take = declination_divisions * rotation_divisions
                if total_pictures_to_take > max_pictures:
                    post_status(BEANSTALK, "too many pictures, exceeded {0}".format(max_pictures))
                    continue

                # okay here's what the inputs mean:
                # declination_steps - # of divisions of camera travel (declination)
                # rotation_steps - # of divisions in single rotation of model
                # start/stop : starting/ending offsets from homed positions.
                #
            except ValueError:
                post_status(BEANSTALK, "error in scan input value")
                continue
            except KeyError:
                post_status(BEANSTALK, "error with input JSON")
                print("/scan JSON failed! : {0}".format(json.dumps(job_dict)))

            print('...calculating steps for {0} pictures'.
                  format(total_pictures_to_take))

            if not is_homed:
                post_status(BEANSTALK, 'homing system prior to scan...')
                declination_travel_steps = home_camera(queue=BEANSTALK)
                is_homed = True

            # okay we have valid parameters, time to scan the object
            rotation_travel_steps = 200  # takes 200 steps to turn model 360 degrees
            steps_per_declination,\
                steps_per_rotation,\
                declination_start = calculate_steps(declination_divisions,
                                                    rotation_divisions,
                                                    declination_travel_steps,
                                                    rotation_travel_steps,
                                                    start,
                                                    stop)

            print('declination_divisions={0}\nrotation_divisions={1}'
                  '\ntravel={2}\nstart={3}\nstop={4}'.
                  format(declination_divisions,
                         rotation_divisions, declination_travel_steps,
                         start, stop))
            print('... {0} declination steps, {1} rotation steps, declination start {2}'.
                  format(steps_per_declination,
                         steps_per_rotation,
                         declination_start))

            # the camera & model are 'homed', so now we need to go through the motions
            remaining_declination_steps = declination_travel_steps

            # move camera to starting position for pictures
            if declination_start > 0:
                post_status(BEANSTALK,
                            'move to declination start {0}'.
                            format(declination_start))
                forced_exit = camera_stepper.step(declination_start,
                                                  STEP_CAMERA_CCW,
                                                  Raspi_MotorHAT.DOUBLE)

            if not forced_exit:
                photograph_model(declination_divisions,
                                 rotation_divisions,
                                 remaining_declination_steps,
                                 steps_per_declination,
                                 steps_per_rotation,
                                 BEANSTALK,
                                 rotate_stepper,
                                 camera_stepper)

            # we are done taking pictures, release the motors so we don't
            # overheat and remember we are no longer homed
            is_homed = False  # we just did a scan, we need to re-home
            turn_off_motors()  # so we don't overheat while idle


if __name__ == '__main__':
    main()
