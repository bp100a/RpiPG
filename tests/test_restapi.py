from unittest import TestCase
from restapi import rig_control


class TestRigRunner(TestCase):

    def test_make_key(self):
        key = rig_control.machine_specific_key()
        assert key is None