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
CAMERA_STEPPER_MOTOR_SPEED = 120  # rpm
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


def post_status(status: str) -> None:
    """simple status string we send back"""
    if BEANSTALK:
        json_status = json.dumps({'msg': status})
        BEANSTALK.watch(STATUS_QUEUE)
        BEANSTALK.put(json_status)


def yield_function(direction: int) -> bool:
    """Called in timing loops to perform checks
    to see if we need to breakout. We need the direction
    of travel since we may want to ignore a limit
    switch that has been triggered.

    For now just checking limit switches, eventually
    we need to process other input like a cancel
    request from a web app"""

    if BEANSTALK:  # if we have a queue, check for user cancel
        job = BEANSTALK.reserve(timeout=0) # don't wait
        if job is not None:
            return True

    if direction == Raspi_MotorHAT.FORWARD:
        return CCW_MAX_SWITCH.is_pressed()

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


def home_camera(step_dir: int, switch: limit_switch.LimitSwitch) -> int:
    """home the camera. This means moving in a direction and checking
    for that direction's limit switch"""
    camera_stepper = MOTOR_HAT.getStepper(CAMERA_STEPPER_MOTOR_NUM)
    starting_stepper_pos = camera_stepper.stepping_counter
    while not switch.is_pressed():
        camera_stepper.step(1000, step_dir)

    traveled_steps = camera_stepper.stepping_counter - starting_stepper_pos
    if step_dir == STEP_CAMERA_CCW:
        camera_stepper.stepping_counter = 0

    return traveled_steps


def ccw_camera_home() -> int:
    """home the camera in the counter-clockwise direction"""
    return home_camera(STEP_CAMERA_CCW, CCW_MAX_SWITCH)


def cw_camera_home() -> int:
    """home the camera in the clockwise direction"""
    return home_camera(STEP_CAMERA_CW, CW_MAX_SWITCH)


if __name__ == '__main__':
    # okay time to run things
    CAMERA_STEPPER = MOTOR_HAT.getStepper(CAMERA_STEPPER_MOTOR_NUM)
    CAMERA_STEPPER.setSpeed(CAMERA_STEPPER_MOTOR_SPEED)

    BEANSTALK = configure_beanstalk()
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
        print("...CW stepping")
        if CAMERA_STEPPER.step(STEPS_TO_TAKE, STEP_CAMERA_CW, Raspi_MotorHAT.DOUBLE):
            print("CW endstop triggered")

        print("...CCW stepping")
        if CAMERA_STEPPER.step(STEPS_TO_TAKE, STEP_CAMERA_CCW, Raspi_MotorHAT.DOUBLE):
            print ("CCW endstop triggered")
