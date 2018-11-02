from unittest import TestCase
import util

class TestRigRunner(TestCase):

    def test_calculate_steps(self):

        steps_per_declination, \
            steps_per_rotation, \
            declination_start = util.calculate_steps(declination=8,
                                                     rotation=7,
                                                     declination_travel=2000,
                                                     rotation_travel=200,
                                                     start_pos=0,
                                                     end_pos=100)

        assert(steps_per_declination == int(2000/8) )
        assert(steps_per_rotation == int(200/7))
        assert(declination_start == 0)

    def test_calculate_steps_with_start_offsets(self):

        steps_per_declination, \
            steps_per_rotation, \
            declination_start = util.calculate_steps(declination=8,
                                                     rotation=7,
                                                     declination_travel=2000,
                                                     rotation_travel=200,
                                                     start_pos=50,
                                                     end_pos=100)

        assert(steps_per_declination == int(1000/8) )
        assert(steps_per_rotation == int(200/7))
        assert(declination_start == 1000)

    def test_calculate_steps_with_end_offsets(self):

        steps_per_declination, \
            steps_per_rotation, \
            declination_start = util.calculate_steps(declination=8,
                                                     rotation=7,
                                                     declination_travel=2000,
                                                     rotation_travel=200,
                                                     start_pos=0,
                                                     end_pos=50)

        assert(steps_per_declination == int(1000/8) )
        assert(steps_per_rotation == int(200/7))
        assert(declination_start == 0)