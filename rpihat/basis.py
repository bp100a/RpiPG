#!/usr/bin/python
"""Basis - this is where I keep base classes so I can do
things like 'dependency injection' for testing"""


class PWMInterface:

    @classmethod
    def softwareReset(cls):
        pass

    def __init__(self, address=0x40, debug=False):
        pass

    def setPWMFreq(self, freq):
        pass

    def setPWM(self, channel, on, off):
        """Sets a single PWM channel"""
        pass

    def setAllPWM(self, on, off):
        pass


class StepperInterface:
    stepping_counter = 0

    def __init__(self, controller, num: int, steps=200, yield_function=None) -> None:
        # note: the 'controller' is the MotorHatInterface parent reference
        pass

    def my_timer(self, sleep_time: float, direction: int) -> bool:
        pass

    def setSpeed(self, rpm: int) -> None:
        pass

    def oneStep(self, step_dir: int, style: int) -> int:
        pass

    def hold(self) -> None:
        pass

    def step(self, steps: int, direction: int, step_style: int) -> None:
        pass


class MotorHatInterface:

    def __init__(self, stepper_class: StepperInterface,
                 pwm_class: PWMInterface,
                 yield_func, addr=0x60, freq=1600, debug=False):
        pass

    def setPin(self, pin: int, value: int) -> None:
        pass

    def getStepper(self, num: int):
        pass

    def release_motor(self, motor_num: int) -> None:
        pass

    def release_motors(self) -> None:
        pass