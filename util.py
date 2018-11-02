def calculate_steps(declination: int,
                    rotation: int,
                    declination_travel: int,
                    rotation_travel: int,
                    start_pos: int, end_pos: int):
    """
    determine how many "steps" for each picture
    :param declination: # of declination divisions
    :param rotation: # of rotation divisions
    :param declination_travel: # of steps to travel entire declination distance
    :param rotation_travel: # of steps for a complete rotation of the platform
    :param start_pos: Where to start taking pictures (0->100)
    :param end_pos: Where to stop taking pictures (0->100)
    :return:

    The rig travels from +90 (apogee) to -55 (perigee), which is represented by
    [0->100] in the camera angle slider.
    """

    declination_start = (declination_travel / 100) * start_pos
    declination_end = (declination_travel / 100) * end_pos
    steps_per_declination = int((declination_end - declination_start) / declination)
    steps_per_rotation = int(rotation_travel / rotation)
    return steps_per_declination, steps_per_rotation, declination_start

