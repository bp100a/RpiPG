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
from rpihat import limit_switch  # our limit switches
from rpihat.Raspi_PWM_Servo_Driver import PWM
from rpihat.pimotorhat import Raspi_StepperMotor, Raspi_MotorHAT
import beanstalkc as beanstalk
from util import calculate_steps


CAMERA_STEPPER_MOTOR_NUM = 2
CAMERA_STEPPER_MOTOR_SPEED = 240  # rpm
MODEL_STEPPER_MOTOR_NUM = 1
MOTOR_HAT_I2C_ADDR = 0x6F
MOTOR_HAT_I2C_FREQ = 1600
CCW_MAX_SWITCH = limit_switch.LimitSwitch(18)  # furthest CCW rotation allowed
CW_MAX_SWITCH = limit_switch.LimitSwitch(4)  # furthest CW rotation allowed
BEANSTALK = None
CANCEL_QUEUE = 'cancel'
STATUS_QUEUE = 'status'
TASK_QUEUE = 'work'


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


def post_status(queue: beanstalk.Connection, status: str) -> None:
    """simple status string we send back"""
    if queue:
        json_status = json.dumps({'msg': status})
        queue.use(STATUS_QUEUE)
        queue.put(json_status)


BREAK_EXIT_REASON = None


def yield_function(direction: int) -> bool:
    """Called in timing loops to perform checks
    to see if we need to breakout. We need the direction
    of travel since we may want to ignore a limit
    switch that has been triggered.

    For now just checking limit switches, eventually
    we need to process other input like a cancel
    request from a web app"""
    global BREAK_EXIT_REASON

    try:
        if BEANSTALK:  # if we have a queue, check for user cancel
            BEANSTALK.watch(CANCEL_QUEUE)
            cancel_job = BEANSTALK.reserve(timeout=0) # don't wait
            if cancel_job is not None:
                body = cancel_job.body
                cancel_job.delete()
                print ('Cancel received: {0}'.format(body))
                BREAK_EXIT_REASON = 'Cancel'
                return True

    except beanstalk.CommandFailed:
        print("yield_function(): beanstalk CommandFail!")
        pass
    except beanstalk.DeadlineSoon:
        # save to ignore since it just means there's something pending
        pass

    if direction == Raspi_MotorHAT.FORWARD:
        BREAK_EXIT_REASON = 'CCW'
        return CCW_MAX_SWITCH.is_pressed()

    BREAK_EXIT_REASON = "CW"
    return CW_MAX_SWITCH.is_pressed()


# Create our motor hat controller object, it'll house two
# stepper motor objects
MOTOR_HAT = Raspi_MotorHAT(stepper_class=Raspi_StepperMotor,
                           pwm_class=PWM,
                           yield_func=yield_function,
                           addr=MOTOR_HAT_I2C_ADDR,
                           freq=MOTOR_HAT_I2C_FREQ,
                           debug=False)


# if somehow we exit, try to make sure the motors are
# turned off, otherwise they may heat up
def turn_off_motors():
    """disable motors. This will be called 'at exit' so
    motors don't overheat when idle and energized"""
    MOTOR_HAT.release_motors()


atexit.register(turn_off_motors)

STEP_CAMERA_CCW = Raspi_MotorHAT.FORWARD
STEP_CAMERA_CW = Raspi_MotorHAT.BACKWARD
STEP_MODEL_CCW = Raspi_MotorHAT.FORWARD
STEP_MODEL_CW = Raspi_MotorHAT.BACKWARD


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


def ccw_camera_home() -> int:
    """home the camera in the counter-clockwise direction"""
    post_status(BEANSTALK, "CCW homing")
    return move_camera(STEP_CAMERA_CCW, CCW_MAX_SWITCH)


def cw_camera_home() -> int:
    """home the camera in the clockwise direction"""
    post_status(BEANSTALK, "CW homing")
    return move_camera(STEP_CAMERA_CW, CW_MAX_SWITCH)


def home_camera() -> int:
    """home the camera. This will move the camera to the two
    extreme positions and return how many steps it took to
    span the extremes"""
    ccw_camera_home()
    return abs(cw_camera_home())


def post_status(queue: beanstalk.Connection, message: str) -> None:
    """post a simple message to whomever is listening"""
    queue.use(STATUS_QUEUE)
    status_json = json.dumps({'msg': message})
    queue.put(status_json)


def take_picture(picture_number: int, num_pictures_taken: int) -> None:
    """take the picture"""
    post_status(BEANSTALK, "taking picture")
    print('   taking picture #{0}/{1}'.format(picture_number, num_pictures_taken))
    time.sleep(2)


if __name__ == '__main__':
    # okay time to run things
    CAMERA_STEPPER = MOTOR_HAT.getStepper(CAMERA_STEPPER_MOTOR_NUM)
    CAMERA_STEPPER.setSpeed(CAMERA_STEPPER_MOTOR_SPEED)

    ROTATE_STEPPER = MOTOR_HAT.getStepper(MODEL_STEPPER_MOTOR_NUM)
    ROTATE_STEPPER.setSpeed(CAMERA_STEPPER_MOTOR_SPEED)

    BEANSTALK = configure_beanstalk()
    clear_all_queues(BEANSTALK)

    if CCW_MAX_SWITCH.is_pressed():
        print("CCW switch pressed!")
    else:
        print("CCW switch not pressed!")

    if CW_MAX_SWITCH.is_pressed():
        print("CW switch pressed!")
    else:
        print("CW switch not pressed!")

    print("\n**********************")
    print("\n** waiting for jobs **")
    print("\n**********************\n")
    is_homed = False
    declination_travel_steps = 0 # number of steps between min/max endstops
    while True:
        BEANSTALK.watch(TASK_QUEUE)
        job = BEANSTALK.reserve(timeout=0)
        if job is None:
            time.sleep(0.001) # sleep for 1 ms to share the computer
            continue

        # We got a job!
        job_dict = json.loads(job.body)
        job.delete()
        if job_dict['task'] == 'home':
            declination_travel_steps = home_camera()
            is_homed = True
            print("homing complete, travel steps = {0}".format(declination_travel_steps))
            continue

        MAX_PICTURES = 200

        if job_dict['task'] == 'scan':
            try:
                print ('scan command received')
                post_status(BEANSTALK, "scan command received!")
                declination_divisions = int(job_dict['steps']['declination'])
                rotation_divisions = int(job_dict['steps']['rotation'])
                start = int(job_dict['offsets']['start'])
                stop = int(job_dict['offsets']['stop'])

                total_pictures_to_take = declination_divisions * rotation_divisions
                if total_pictures_to_take > MAX_PICTURES:
                    post_status(BEANSTALK, "too many pictures, exceeded {0}".format(MAX_PICTURES))
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

            # okay we have valid parameters, time to scan the object
            ROTATION_TRAVEL_STEPS = 200 # takes 200 steps to turn model 360 degrees
            steps_per_declination,\
            steps_per_rotation,\
            declination_start = calculate_steps(declination_divisions,
                                                rotation_divisions,
                                                declination_travel_steps,
                                                ROTATION_TRAVEL_STEPS,
                                                start,
                                                stop)

            print('declination_divisions={0}\nrotation_divisions={1}\ntravel={2}\nstart={3}\nstop={4}'.
                  format(declination_divisions, rotation_divisions, declination_travel_steps, start, stop))
            print('... {0} declination, {1} rotation steps, declination start {2}'.
                  format(steps_per_declination,
                         steps_per_rotation,
                         declination_start))

            # the camera & model are 'homed', so now we need to go through the motions
            forced_exit = False
            remaining_declination_steps = declination_travel_steps  # got this from homing the printer
            total_pictures_taken = 0

            # move camera to starting position for pictures
            if declination_start > 0:
                print('move to declination start {0}'.format(declination_start) )
                if CAMERA_STEPPER.step(declination_start, STEP_CAMERA_CCW, Raspi_MotorHAT.DOUBLE):
                    forced_exit = True

            for d in range(0, declination_divisions):
                if forced_exit:
                    break
                post_status(BEANSTALK, "rotating model")
                for r in range(0, rotation_divisions):
                    total_pictures_taken += 1
                    take_picture(r, total_pictures_taken)
                    if ROTATE_STEPPER.step(steps_per_rotation, STEP_MODEL_CCW, Raspi_MotorHAT.DOUBLE):
                        forced_exit = True
                        break # forced exit

                if CAMERA_STEPPER.step(steps_per_declination, STEP_CAMERA_CCW, Raspi_MotorHAT.DOUBLE):
                    forced_exit = True
                    break  # forced exit

                # the declination motion may not be perfect fit so don't overstep
                remaining_declination_steps -= steps_per_declination
                if remaining_declination_steps < steps_per_declination:
                    steps_per_declination = remaining_declination_steps;

            is_homed = False # we just did a scan, we need to re-home
