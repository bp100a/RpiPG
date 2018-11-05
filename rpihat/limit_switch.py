from gpiozero import Button    # a GPIO library


class LimitSwitch:
    """object to wrap our input limit switches"""
    switch = None
    name = None

    def __init__(self, pin: int, name: str) -> None:
        self.switch = Button(pin, pull_up=False, bounce_time=None)
        self.name = name

    def is_pressed(self) -> bool:
        return self.switch.is_pressed

    def __str__(self) -> str:
        if self.is_pressed():
            return "{0} is closed".format(self.name)
        else:
            return "{0} is open".format(self.name)