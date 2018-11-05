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
                                                     start_pos=100,
                                                     end_pos=0)

        assert(steps_per_declination == int(2000/7) )
        assert(steps_per_rotation == int(200/7))
        assert(declination_start == 0)

    def test_calculate_steps_no_offset(self):

        steps_per_declination, \
            steps_per_rotation, \
            declination_start = util.calculate_steps(declination=9,
                                                     rotation=8,
                                                     declination_travel=3474,
                                                     rotation_travel=200,
                                                     start_pos=100,
                                                     end_pos=0)

        assert(steps_per_declination == int(3474/8) )
        assert(steps_per_rotation == int(200/8))
        assert(declination_start == 0)

    def test_calculate_steps_with_start_offsets(self):

        steps_per_declination, \
            steps_per_rotation, \
            declination_start = util.calculate_steps(declination=8,
                                                     rotation=7,
                                                     declination_travel=2000,
                                                     rotation_travel=200,
                                                     start_pos=100,
                                                     end_pos=50)

        assert(steps_per_declination == int(1000/7) )
        assert(steps_per_rotation == int(200/7))
        assert(declination_start == 0)

    def test_calculate_steps_with_end_offsets(self):

        steps_per_declination, \
            steps_per_rotation, \
            declination_start = util.calculate_steps(declination=8,
                                                     rotation=7,
                                                     declination_travel=2000,
                                                     rotation_travel=200,
                                                     start_pos=50,
                                                     end_pos=0)

        assert(steps_per_declination == int(1000/7))
        assert(steps_per_rotation == int(200/7))
        assert(declination_start == 1000)

    def test_calculate_steps_with_start_offset(self):

        steps_per_declination, \
            steps_per_rotation, \
            declination_start = util.calculate_steps(declination=8,
                                                     rotation=7,
                                                     declination_travel=3287,
                                                     rotation_travel=200,
                                                     start_pos=62,
                                                     end_pos=0)

        assert(steps_per_declination == 291)
        assert(steps_per_rotation == int(200/7))
        assert(declination_start == 1249)