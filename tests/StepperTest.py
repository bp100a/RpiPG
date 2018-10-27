#!/usr/bin/python
import atexit
import time
from rpihat.pimotorhat import Raspi_MotorHAT

# create a default object, no changes to I2C address or frequency
mh = Raspi_MotorHAT(0x6F)


# recommended for auto-disabling motors on shutdown!
def turnOffMotors():
	mh.release_motor(1)
	mh.release_motor(2)
	mh.release_motor(3)
	mh.release_motor(4)


atexit.register(turnOffMotors)
# motor #1 -> M1 & M2, motor #2 -> M3 & M4
myStepper = mh.getStepper(200, 2)  	# 200 steps/rev, motor port #1
myStepper.setSpeed(30)  		# 30 RPM

while True:
	print("Hold position [10 sec]")
	myStepper.hold()
	time.sleep(10)

	# print("Single coil steps [hold]")
	# myStepper.step(100, Raspi_MotorHAT.FORWARD,  Raspi_MotorHAT.SINGLE)
	# myStepper.step(100, Raspi_MotorHAT.BACKWARD, Raspi_MotorHAT.SINGLE)
	#
	print("Double coil steps")
	myStepper.step(100, Raspi_MotorHAT.FORWARD,  Raspi_MotorHAT.DOUBLE)
	myStepper.step(100, Raspi_MotorHAT.BACKWARD, Raspi_MotorHAT.DOUBLE)

	print("Interleaved coil steps")
	myStepper.step(100, Raspi_MotorHAT.FORWARD,  Raspi_MotorHAT.INTERLEAVE)
	myStepper.step(100, Raspi_MotorHAT.BACKWARD, Raspi_MotorHAT.INTERLEAVE)

	print("Microsteps")
	myStepper.step(100, Raspi_MotorHAT.FORWARD,  Raspi_MotorHAT.MICROSTEP)
	myStepper.step(100, Raspi_MotorHAT.BACKWARD, Raspi_MotorHAT.MICROSTEP)
