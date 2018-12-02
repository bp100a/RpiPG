#!/usr/bin/python
""" Raspberry Pi Motor HAT"""
import sys
import time
import traceback
from rpihat.basis import PWMInterface

#pylint:disable=C0103


class Raspi_MotorHAT:
    """our motor HAT"""
    FORWARD = 1
    BACKWARD = 2
    BRAKE = 3
    RELEASE = 4

    SINGLE = 1
    DOUBLE = 2
    INTERLEAVE = 3
    MICROSTEP = 4
    _pwm = None

    @property
    def pwm(self) -> PWMInterface:
        """our internal PWM interface object"""
        return self._pwm

    @pwm.setter
    def pwm(self, value):
        self._pwm = value

    def __init__(self, pwm_obj: PWMInterface,
                 yield_func, freq, debug=False):
        self._i2caddr = pwm_obj.address
        self._frequency = freq		# default @1600Hz PWM freq

        # Storing the stepper objects in an array:
        #  1 -> Rotation Stepper
        #  2 -> Declination(camera) stepper
        self.steppers = [RaspiStepperMotor(self, 1, steps=200, yield_function=None),
                         RaspiStepperMotor(self, 2, steps=200, yield_function=yield_func)]
        self.pwm = pwm_obj
        self.pwm.debug = debug
        self.pwm.setPWMFreq(self._frequency)

    def setPin(self, pin: int, value: int) -> None:
        """set the pin"""
        if (pin < 0) or (pin > 15):
            raise NameError('PWM pin must be between 0 and 15 inclusive')
        if value == 0:
            self.pwm.setPWM(pin, 0, 4096)
        elif value == 1:
            self.pwm.setPWM(pin, 4096, 0)
        else:
            raise NameError('Pin value must be 0 or 1!')

    def getStepper(self, num: int):
        """get Stepper using 1-based indices
         1 -> rotation stepper
         2 -> camera/declination stepper"""
        if num not in (1, 2):
            raise NameError('MotorHAT Stepper must be between 1 and 2 inclusive {0}'.
                            format(num))
        return self.steppers[num-1]

    def release_motor(self, motor_num: int) -> None:
        """turns off coil energizing motors"""
        if motor_num == 1:
            in2 = 9
            in1 = 10
        elif motor_num == 2:
            in2 = 12
            in1 = 11
        elif motor_num == 3:
            in2 = 3
            in1 = 4
        elif motor_num == 4:
            in2 = 6
            in1 = 5
        else:
            return

        self.setPin(in1, 0)
        self.setPin(in2, 0)

    def release_motors(self) -> None:
        """release all motors"""
        for motor_num in range(1, 5):
            self.release_motor(motor_num)


class RaspiStepperMotor:
    """control stepper motor stepping"""
    MICROSTEPS = 8
    MICROSTEP_CURVE = [0, 50, 98, 142, 180, 212, 236, 250, 255]
    # MICROSTEPS = 16
    # a sinusoidal curve NOT LINEAR!
    # MICROSTEP_CURVE = [0, 25, 50, 74, 98, 120, 141, 162, 180,\
    #                    197, 212, 225, 236, 244, 250, 253, 255]

    _MC = None
    _yield_func = None

    @property
    def motor_controller(self) -> Raspi_MotorHAT:
        """The controller parent for this motor"""
        return self._MC

    @motor_controller.setter
    def motor_controller(self, value: Raspi_MotorHAT):
        """setting the controller parent for this motor"""
        self._MC = value

    @property
    def yield_func(self):
        """return the yield function if specified"""
        return self._yield_func

    @yield_func.setter
    def yield_func(self, value):
        """set our yield function"""
        self._yield_func = value

    def __init__(self, controller: Raspi_MotorHAT,
                 num: int, steps=200,
                 yield_function=None) -> None:

        self.yield_function = yield_function
        self.motor_controller = controller
        self.revsteps = steps
        self.motor_num = num
        self.sec_per_step = 0.1
        self.stepping_counter = 0
        self.current_step = 0

        if num == 1:
            self.PWMA = 8
            self.AIN2 = 9
            self.AIN1 = 10
            self.PWMB = 13
            self.BIN2 = 12
            self.BIN1 = 11
        elif num == 2:
            self.PWMA = 2
            self.AIN2 = 3
            self.AIN1 = 4
            self.PWMB = 7
            self.BIN2 = 6
            self.BIN1 = 5
        else:
            raise NameError('MotorHAT Stepper must be either 1 or 2')

    def is_yielding(self, direction: int) -> dict:
        """if we have yield function check to see if
        an exit condition has arisen"""
        if not self.yield_function:
            return {}
        return self.yield_function(direction)

    def my_timer(self, sleep_time: float, direction: int) -> dict:
        """implement a sleep() timer but in a loop
        if the yield function exists and returns a dict,
        then we break out of the loop"""
        current_time_microseconds = time.time() * 10**6
        end_time_microseconds = current_time_microseconds + int(sleep_time * 10**6)

        # this is where we "wait" until it's time to process the
        # next step pulse. We will call the yield_function() to
        # see if anyone wants to interrupt us
        while current_time_microseconds < end_time_microseconds:

            # if we have a "yield function" we call this to process
            # external events we want to exit for
            if self.yield_function:
                exit_dict = self.yield_function(direction)
                if exit_dict:
                    return exit_dict

            time.sleep(sleep_time / 10)  # yield some time to other processes
            current_time_microseconds = time.time() * 10**6
        return {}

    def setSpeed(self, rpm: int) -> None:
        """set speed of stepper"""
        self.sec_per_step = 60.0 / (self.revsteps * rpm)
        self.stepping_counter = 0

    def step_coils(self, style: int, pwm_a: int, pwm_b: int) -> int:
        """now that we figured out the next step, let's
        energize the coils to make the step occur"""

        # only really used for microstepping, otherwise always on!
        self.motor_controller.pwm.setPWM(self.PWMA, 0, pwm_a * 16)
        self.motor_controller.pwm.setPWM(self.PWMB, 0, pwm_b * 16)

        # set up coil energizing!
        coils = [0, 0, 0, 0]

        if style == Raspi_MotorHAT.MICROSTEP:
            if (self.current_step >= 0) and \
               (self.current_step < self.MICROSTEPS):
                coils = [1, 1, 0, 0]
            elif (self.current_step >= self.MICROSTEPS) and \
                 (self.current_step < self.MICROSTEPS * 2):
                coils = [0, 1, 1, 0]
            elif (self.current_step >= self.MICROSTEPS * 2) and \
                 (self.current_step < self.MICROSTEPS * 3):
                coils = [0, 0, 1, 1]
            elif (self.current_step >= self.MICROSTEPS * 3) and \
                 (self.current_step < self.MICROSTEPS * 4):
                coils = [1, 0, 0, 1]
        else:
            step2coils = [[1, 0, 0, 0],
                          [1, 1, 0, 0],
                          [0, 1, 0, 0],
                          [0, 1, 1, 0],
                          [0, 0, 1, 0],
                          [0, 0, 1, 1],
                          [0, 0, 0, 1],
                          [1, 0, 0, 1]]

            coils = step2coils[int(self.current_step / (self.MICROSTEPS / 2))]

        # now energize the coils to perform the step
        self.motor_controller.setPin(self.AIN2, coils[0])
        self.motor_controller.setPin(self.BIN1, coils[1])
        self.motor_controller.setPin(self.AIN1, coils[2])
        self.motor_controller.setPin(self.BIN2, coils[3])

        return self.current_step

    def compute_step(self, step_dir: int, style: int):  #pylint: disable-msg=too-many-branches
        """compute the our next step."""
        # first determine what sort of stepping procedure we're up to
        if style == Raspi_MotorHAT.SINGLE:
            if (self.current_step / (self.MICROSTEPS / 2)) % 2:
                # we're at an odd step, weird
                if step_dir == Raspi_MotorHAT.FORWARD:
                    self.current_step += self.MICROSTEPS / 2
                else:
                    self.current_step -= self.MICROSTEPS / 2
            else:
                # go to next even step
                if step_dir == Raspi_MotorHAT.FORWARD:
                    self.current_step += self.MICROSTEPS
                else:
                    self.current_step -= self.MICROSTEPS

        if style == Raspi_MotorHAT.DOUBLE:
            if not self.current_step / (self.MICROSTEPS / 2) % 2:
                # we're at an even step, weird
                if step_dir == Raspi_MotorHAT.FORWARD:
                    self.current_step += self.MICROSTEPS / 2
                else:
                    self.current_step -= self.MICROSTEPS / 2
            else:
                # go to next odd step
                if step_dir == Raspi_MotorHAT.FORWARD:
                    self.current_step += self.MICROSTEPS
                else:
                    self.current_step -= self.MICROSTEPS

        if style == Raspi_MotorHAT.INTERLEAVE:
            if step_dir == Raspi_MotorHAT.FORWARD:
                self.current_step += self.MICROSTEPS / 2
            else:
                self.current_step -= self.MICROSTEPS / 2

        if style == Raspi_MotorHAT.MICROSTEP:
            if step_dir == Raspi_MotorHAT.FORWARD:
                self.current_step += 1
            else:
                self.current_step -= 1

        # go to next 'step' and wrap around
        self.current_step += self.MICROSTEPS * 4
        self.current_step %= self.MICROSTEPS * 4

    def one_step(self, step_dir: int, style: int) -> int:
        """issue step"""
        self.compute_step(step_dir, style)

        pwm_a = pwm_b = 0
        try:
            if (self.current_step >= 0) and (self.current_step < self.MICROSTEPS):
                pwm_a = self.MICROSTEP_CURVE[int(self.MICROSTEPS - self.current_step)]
                pwm_b = self.MICROSTEP_CURVE[int(self.current_step)]
            elif (self.current_step >= self.MICROSTEPS) and \
                 (self.current_step < self.MICROSTEPS * 2):
                pwm_a = self.MICROSTEP_CURVE[int(self.current_step - self.MICROSTEPS)]
                pwm_b = self.MICROSTEP_CURVE[int(self.MICROSTEPS * 2 - self.current_step)]
            elif (self.current_step >= self.MICROSTEPS * 2) and \
                 (self.current_step < self.MICROSTEPS * 3):
                pwm_a = self.MICROSTEP_CURVE[int(self.MICROSTEPS * 3 - self.current_step)]
                pwm_b = self.MICROSTEP_CURVE[int(self.current_step - self.MICROSTEPS * 2)]
            elif (self.current_step >= self.MICROSTEPS * 3) and \
                 (self.current_step < self.MICROSTEPS * 4):
                pwm_a = self.MICROSTEP_CURVE[int(self.current_step - self.MICROSTEPS * 3)]
                pwm_b = self.MICROSTEP_CURVE[int(self.MICROSTEPS * 4 - self.current_step)]
        except TypeError:
            print("Error indexing! self.currentstep ={0}, self.MICROSTEPS={1}".
                  format(self.current_step, self.MICROSTEPS))
            _, _, tb = sys.exc_info()
            print(traceback.format_list(traceback.extract_tb(tb)[-1:])[-1])

        # go to next 'step' and wrap around
        self.current_step += self.MICROSTEPS * 4
        self.current_step %= self.MICROSTEPS * 4

        return self.step_coils(style, pwm_a, pwm_b)

    def hold(self) -> None:
        """use single step to hold current position"""
        self.one_step(step_dir=Raspi_MotorHAT.FORWARD, style=Raspi_MotorHAT.SINGLE)

    def step(self, steps: int, direction: int, step_style: int) -> dict:
        """step the motor, returns a dict if interrupted"""
        s_per_s = self.sec_per_step
        latest_step = 0

        if step_style == Raspi_MotorHAT.INTERLEAVE:
            s_per_s = s_per_s / 2.0
        if step_style == Raspi_MotorHAT.MICROSTEP:
            s_per_s /= self.MICROSTEPS
            steps *= self.MICROSTEPS

        try:
            # before we start stepping, for safety check the yield function
            # to see if there's a reason not to proceed (like we are at a limit
            # switch
            yield_dict = self.is_yielding(direction)
            if yield_dict:
                return yield_dict

            # okay let's step the motor
            for _ in range(steps):
                latest_step = self.one_step(direction, step_style)
                if direction == Raspi_MotorHAT.FORWARD:
                    self.stepping_counter += 1
                else:
                    self.stepping_counter -= 1

                # yield the CPU and check for exit conditions
                exit_dict = self.my_timer(s_per_s, direction)
                if exit_dict:
                    return exit_dict
        except KeyboardInterrupt: # if someone types control-c we should exit
            return {'exit': 'KeyboardInterrupt'}

        if step_style == Raspi_MotorHAT.MICROSTEP:
            # this is an edge case, if we are in between full steps, lets just keep going
            # so we end on a full step
            while latest_step not in(0, self.MICROSTEPS):
                latest_step = self.one_step(direction, step_style)
                exit_dict = self.my_timer(s_per_s, direction)
                if exit_dict:
                    return exit_dict
        return {}
