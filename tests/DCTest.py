#!/usr/bin/python
from rpihat import pimotorhat, Raspi_DCMotor

import time
import atexit

# create a default object, no changes to I2C address or frequency
mh = pimotorhat(addr=0x6f)

# recommended for auto-disabling motors on shutdown!
def turnOffMotors():
	mh.getMotor(1).run(pimotorhat.RELEASE)
	mh.getMotor(2).run(pimotorhat.RELEASE)
	mh.getMotor(3).run(pimotorhat.RELEASE)
	mh.getMotor(4).run(pimotorhat.RELEASE)

atexit.register(turnOffMotors)

################################# DC motor test!
myMotor = mh.getMotor(3)

# set the speed to start, from 0 (off) to 255 (max speed)
myMotor.setSpeed(150)
myMotor.run(pimotorhat.FORWARD);
# turn on motor
myMotor.run(pimotorhat.RELEASE);


while (True):
	print("Forward! ")
	myMotor.run(pimotorhat.FORWARD)

	print("\tSpeed up...")
	for i in range(255):
		myMotor.setSpeed(i)
		time.sleep(0.01)

	print("\tSlow down...")
	for i in reversed(list(range(255))):
		myMotor.setSpeed(i)
		time.sleep(0.01)

	print("Backward! ")
	myMotor.run(pimotorhat.BACKWARD)

	print("\tSpeed up...")
	for i in range(255):
		myMotor.setSpeed(i)
		time.sleep(0.01)

	print("\tSlow down...")
	for i in reversed(list(range(255))):
		myMotor.setSpeed(i)
		time.sleep(0.01)

	print("Release")
	myMotor.run(pimotorhat.RELEASE)
	time.sleep(1.0)
