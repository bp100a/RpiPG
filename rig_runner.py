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


CAMERA_STEPPER_MOTOR_NUM = 2
CAMERA_STEPPER_MOTOR_SPEED = 240  # rpm
MODEL_STEPPER_MOTOR_NUM = 1
MOTOR_HAT_I2C_ADDR = 0x6F
MOTOR_HAT_I2C_FREQ = 1600
CCW_MAX_SWITCH = limit_switch.LimitSwitch(4)  # furthest CCW rotation allowed
CW_MAX_SWITCH = limit_switch.LimitSwitch(18)  # furthest CW rotation allowed
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
        queue.watch(tube)
        while True:
            dummy = queue.reserve(timeout=0)
            if dummy:
                dummy.delete()
            else:
                break


def post_status(status: str) -> None:
    """simple status string we send back"""
    if BEANSTALK:
        json_status = json.dumps({'msg': status})
        BEANSTALK.watch(STATUS_QUEUE)
        BEANSTALK.put(json_status)


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
            job = BEANSTALK.reserve(timeout=0) # don't wait
            if job is not None:
                job.delete()
                print ('Cancel received')
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
    queue.watch(STATUS_QUEUE)
    status_json = json.dumps({'msg': message})
    queue.put(status_json)


def calculate_steps(declination: int, rotation: int, camera_stepper: Raspi_StepperMotor, rotate_stepper: Raspi_StepperMotor):
    """
    determine how many "steps" for each picture
    :param declination: # of declination divisions
    :param rotation: # of rotation divisions
    :param camera_stepper - the Camera (declination) stepper motor
    :param rotate_stepper - the model (rotation) stepper
    :return: 
    """
    steps_per_declination = int(camera_stepper.current_step / declination)
    steps_per_rotation = int(200 / rotation)
    return steps_per_declination, steps_per_rotation


def take_picture():
    post_status(BEANSTALK, "taking picture")
    pass


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

    while True:
        HOLD_TIME = 1
        print("Hold position [{0} seconds]".format(HOLD_TIME))
        CAMERA_STEPPER.hold()
        time.sleep(HOLD_TIME)

        STEPS_TO_TAKE = 600
        print("Double Steps: {0} steps".format(STEPS_TO_TAKE))
        print("...CW camera stepping")
        if CAMERA_STEPPER.step(STEPS_TO_TAKE, STEP_CAMERA_CW, Raspi_MotorHAT.DOUBLE):
            print("forced exit - " + BREAK_EXIT_REASON)
            break

        print("...CCW camera stepping")
        if CAMERA_STEPPER.step(STEPS_TO_TAKE, STEP_CAMERA_CCW, Raspi_MotorHAT.DOUBLE):
            print ("forced exit - " + BREAK_EXIT_REASON)
            break

        print("...CCW model stepping")
        if ROTATE_STEPPER.step(STEPS_TO_TAKE, STEP_MODEL_CCW, Raspi_MotorHAT.DOUBLE):
            print ("forced exit - " + BREAK_EXIT_REASON)

        print("...CW model stepping")
        if ROTATE_STEPPER.step(STEPS_TO_TAKE, STEP_MODEL_CW, Raspi_MotorHAT.DOUBLE):
            print ("forced exit - " + BREAK_EXIT_REASON)

    # This is the main loop, we poll for work from our
    # queue. We can either "home" the printer or "scan"
    # an object.
    print("\n**********************")
    print("\n** waiting for jobs **")
    print("\n**********************\n")
    is_homed = False
    while True:
        BEANSTALK.watch(TASK_QUEUE)
        job = BEANSTALK.reserve(timeout=0)
        if job is None:
            time.sleep(0.001) # sleep for 1 ms to share the computer
            continue

        # We got a job!
        job_dict = json.loads(job.body)
        job.delete()
        declination_travel_steps = 0
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
                declination_steps = int(job_dict['steps']['declination'])
                rotation_steps = int(job_dict['steps']['rotation'])
                start = int(job_dict['offsets']['start'])
                stop = int(job_dict['offsets']['stop'])

                total_pictures = declination_steps * rotation_steps
                if total_pictures > MAX_PICTURES:
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

            print('...calculating steps for {0} pictures'.format(total_pictures))
            # okay we have valid parameters, time to scan the object
            steps_per_declination, steps_per_rotation = calculate_steps(declination_steps, rotation_steps, CAMERA_STEPPER, ROTATE_STEPPER)

            print('... {0} declination, {1} rotation steps'.format(steps_per_declination, steps_per_rotation))
            # the camera & model are 'homed', so now we need to go through the motions
            forced_exit = False
            remaining_declination_steps = declination_travel_steps  # got this from homing the printer
            for d in range(0, declination_steps):
                if forced_exit:
                    break
                if CAMERA_STEPPER.step(steps_per_declination, STEP_CAMERA_CCW, Raspi_MotorHAT.DOUBLE):
                    forced_exit = True
                    break  # forced exit

                # the declination motion may not be perfect fit so don't overstep
                remaining_declination_steps -= steps_per_declination
                if remaining_declination_steps < steps_per_declination:
                    steps_per_declination = remaining_declination_steps;

                post_status(BEANSTALK, "rotating model")
                for r in range(0, rotation_steps):
                    take_picture()
                    if ROTATE_STEPPER.step(steps_per_rotation, STEP_MODEL_CCW, Raspi_MotorHAT.DOUBLE):
                        forced_exit = True
                        break # forced exit

            is_homed = False # we just did a scan, we need to re-home
            # done moving camera/model and taking pictures