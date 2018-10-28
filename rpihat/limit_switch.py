from gpiozero import Button    # a GPIO library


class LimitSwitch:
    """object to wrap our input limit switches"""
    switch = None

    def __init__(self, pin: int) -> None:
        self.switch = Button(pin, pull_up=True, bounce_time=None)

    def is_pressed(self) -> bool:
        return not self.switch.is_pressed
