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
from rpihat import limit_switch  # our limit switches
from rpihat.Raspi_PWM_Servo_Driver import PWM
from rpihat.pimotorhat import Raspi_StepperMotor, Raspi_MotorHAT

CAMERA_STEPPER_MOTOR_NUM = 1
MODEL_STEPPER_MOTOR_NUM = 2
MOTOR_HAT_I2C_ADDR = 0x6F
MOTOR_HAT_I2C_FREQ = 1600
CCW_MAX_SWITCH = limit_switch.LimitSwitch(4) # furthest CCW rotation allowed
CW_MAX_SWITCH = limit_switch.LimitSwitch(17) # furthest CW rotation allowed


def yield_function(direction: int) -> bool:
    """Called in timing loops to perform checks
    to see if we need to breakout. We need the direction
    of travel since we may want to ignore a limit
    switch that has been triggered.

    For now just checking limit switches, eventually
    we need to process other input like a cancel
    request from a web app"""
    return False
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
    while True:
        HOLD_TIME = 5
        print("Hold position [{0} seconds]".format(HOLD_TIME))
        CAMERA_STEPPER.hold()
        time.sleep(HOLD_TIME)

        print("Microsteps")
        CAMERA_STEPPER.step(300, STEP_CAMERA_CCW, Raspi_MotorHAT.MICROSTEP)
        CAMERA_STEPPER.step(300, STEP_CAMERA_CW, Raspi_MotorHAT.MICROSTEP)
