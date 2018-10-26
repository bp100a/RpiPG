import RPi.GPIO as GPIO          #Import GPIO library


class LimitSwitch(None):
    """object to wrap our input limit switches"""
    def __init__(self, pin: int) -> None:
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def is_pressed(self) -> bool:
        return GPIO.input(self.pin)

