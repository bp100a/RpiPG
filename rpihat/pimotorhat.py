""" Raspberry Pi Motor HAT"""
#!/usr/bin/python
import sys
import time
import traceback
from rpihat.Raspi_PWM_Servo_Driver import PWM

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

    def __init__(self, addr=0x60, freq=1600):
        self._i2caddr = addr        # default addr on HAT
        self._frequency = freq		# default @1600Hz PWM freq
        self.steppers = [Raspi_StepperMotor(self, 1), Raspi_StepperMotor(self, 2)]
        self._pwm = PWM(addr, debug=False)
        self._pwm.setPWMFreq(self._frequency)

    def setPin(self, pin: int, value: int) -> None:
        """set the pin"""
        if (pin < 0) or (pin > 15):
            raise NameError('PWM pin must be between 0 and 15 inclusive')
        if value == 0:
            self._pwm.setPWM(pin, 0, 4096)
        elif value == 1:
            self._pwm.setPWM(pin, 4096, 0)
        else:
            raise NameError('Pin value must be 0 or 1!')

    def getStepper(self, steps: int, num: int):
        """get Stepper"""
        if (num < 1) or (num > 2):
            raise NameError('MotorHAT Stepper must be between 1 and 2 inclusive {0}, steps={1}'.
                            format(num, steps))
        return self.steppers[num-1]

    # def getMotor(self, num):
    #     if (num < 1) or (num > 4):
    #         raise NameError('MotorHAT Motor must be between 1 and 4 inclusive')
    #     return self.motors[num - 1]

    def release_motor(self, motor_num: int) -> None:
        """turns off coil energization of motors"""
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

        self.setPin(in1, 0)
        self.setPin(in2, 0)


class Raspi_StepperMotor:
    """control stepper motor stepping"""
    MICROSTEPS = 8
    MICROSTEP_CURVE = [0, 50, 98, 142, 180, 212, 236, 250, 255]

    # MICROSTEPS = 16
    # a sinusoidal curve NOT LINEAR!
    # MICROSTEP_CURVE = [0, 25, 50, 74, 98, 120, 141, 162, 180,\
    #                    197, 212, 225, 236, 244, 250, 253, 255]

    def __init__(self, controller: Raspi_MotorHAT, num: int, steps=200) -> None:
        self.MC = controller
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
            raise NameError('MotorHAT Stepper must be between 1 and 2 inclusive')

    def my_timer(self, sleep_time: float) -> None:
        """implement a sleep() timer but in a loop"""
        sleep_time_nanoseconds = int(sleep_time * 10**9)
        start_time_nanoseconds = time.time_ns()
        current_time_nanoseconds = time.time_ns()
        end_time_nanoseconds = start_time_nanoseconds + sleep_time_nanoseconds
        while current_time_nanoseconds < end_time_nanoseconds:
            time.sleep(0.0001) # yield some time to other processes
            current_time_nanoseconds = time.time_ns()
        return

    def setSpeed(self, rpm: int) -> None:
        """set speed of stepper"""
        self.sec_per_step = 60.0 / (self.revsteps * rpm)
        self.stepping_counter = 0

    def oneStep(self, step_dir: int, style: int) -> int:
        """issue step"""
        pwm_a = pwm_b = 255

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

        try:
            pwm_a = pwm_b = 0
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

        # only really used for microstepping, otherwise always on!
        self.MC._pwm.setPWM(self.PWMA, 0, pwm_a*16) # pylint:disable=W0212
        self.MC._pwm.setPWM(self.PWMB, 0, pwm_b*16) # pylint:disable=W0212

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

        # print "coils state = " + str(coils)
        self.MC.setPin(self.AIN2, coils[0])
        self.MC.setPin(self.BIN1, coils[1])
        self.MC.setPin(self.AIN1, coils[2])
        self.MC.setPin(self.BIN2, coils[3])

        return self.current_step

    def hold(self) -> None:
        """use single step to hold current position"""
        self.oneStep(step_dir=Raspi_MotorHAT.FORWARD, style=Raspi_MotorHAT.SINGLE)

    def step(self, steps: int, direction: int, step_style: int) -> None:
        """step the motor"""
        s_per_s = self.sec_per_step
        latest_step = 0

        if step_style == Raspi_MotorHAT.INTERLEAVE:
            s_per_s = s_per_s / 2.0
        if step_style == Raspi_MotorHAT.MICROSTEP:
            s_per_s /= self.MICROSTEPS
            steps *= self.MICROSTEPS

        print(s_per_s, " sec per step")

        for _ in range(steps):
            latest_step = self.oneStep(direction, step_style)
            self.my_timer(s_per_s)
#            time.sleep(s_per_s)

        if step_style == Raspi_MotorHAT.MICROSTEP:
            # this is an edge case, if we are in between full steps, lets just keep going
            # so we end on a full step
            while latest_step not in(0, self.MICROSTEPS):
                latest_step = self.oneStep(direction, step_style)
                time.sleep(s_per_s)
