#!/usr/bin/python
"""Basis - this is where I keep base classes so I can do
things like 'dependency injection' for testing"""
import abc


class PWMInterface(abc.ABC):

    address = 0x0

    @classmethod
    @abc.abstractmethod
    def softwareReset(cls):
        pass

    @abc.abstractmethod
    def __init__(self, address=0x40, debug=False):
        pass

    @abc.abstractmethod
    def setPWMFreq(self, freq):
        pass

    @abc.abstractmethod
    def setPWM(self, channel, on, off):
        """Sets a single PWM channel"""
        pass

    @abc.abstractmethod
    def setAllPWM(self, on, off):
        pass
