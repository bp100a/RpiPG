#!/usr/bin/python
"""Test for a single Stepper Motor"""
import atexit
import time
from rpihat.pimotorhat import Raspi_MotorHAT

# create a default object, no changes to I2C address or frequency
MOTOR_HAT = Raspi_MotorHAT(addr=0x6F)


# recommended for auto-disabling motors on shutdown!
def turn_off_motors():
    """disable motors. This will be called 'at exit' so
    motors don't overheat when idle and energized"""
    MOTOR_HAT.release_motors()


atexit.register(turn_off_motors)
# motor #1 -> M1 & M2, motor #2 -> M3 & M4
MY_STEPPER = MOTOR_HAT.getStepper(2)  	# 200 steps/rev, motor port #1
MY_STEPPER.setSpeed(30)  		# 30 RPM

while True:
    hold_time = 5
    print("Hold position [{0} seconds]".format(hold_time))
    MY_STEPPER.hold()
    time.sleep(hold_time)

    # print("Single coil steps [hold]")
    # myStepper.step(100, Raspi_MotorHAT.FORWARD, Raspi_MotorHAT.SINGLE)
    # myStepper.step(100, Raspi_MotorHAT.BACKWARD, Raspi_MotorHAT.SINGLE)
    #
    # print("Double coil steps")
    # MY_STEPPER.step(100, Raspi_MotorHAT.FORWARD, Raspi_MotorHAT.DOUBLE)
    # MY_STEPPER.step(100, Raspi_MotorHAT.BACKWARD, Raspi_MotorHAT.DOUBLE)
    #
    # print("Interleaved coil steps")
    # MY_STEPPER.step(100, Raspi_MotorHAT.FORWARD, Raspi_MotorHAT.INTERLEAVE)
    # MY_STEPPER.step(100, Raspi_MotorHAT.BACKWARD, Raspi_MotorHAT.INTERLEAVE)

    print("Microsteps")
    MY_STEPPER.step(300, Raspi_MotorHAT.FORWARD, Raspi_MotorHAT.MICROSTEP)
    MY_STEPPER.step(300, Raspi_MotorHAT.BACKWARD, Raspi_MotorHAT.MICROSTEP)
