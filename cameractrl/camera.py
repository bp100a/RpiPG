#!/usr/bin/env python

# python-gphoto2 - Python interface to libgphoto2
# http://github.com/jim-easterbrook/python-gphoto2
# Copyright (C) 2015-17  Jim Easterbrook  jim@jim-easterbrook.me.uk
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import logging
import os
import sys
import gphoto2 as gp


def init_camera() -> gp.camera:
    """initialize the camera"""
    logging.basicConfig(
        format='%(levelname)s: %(name)s: %(message)s', level=logging.WARNING)
    gp.check_result(gp.use_python_logging())
    camera = gp.check_result(gp.gp_camera_new())
    gp.check_result(gp.gp_camera_init(camera))
    return camera


def take_picture(camera: gp.camera, rotation_pos: int, declination_pos: int) -> str:
    """take a picture and save it to the USB drive"""
    file_path = gp.check_result(gp.gp_camera_capture(
        camera, gp.GP_CAPTURE_IMAGE))
    target = os.path.join('/mnt/usb', 'P{dec:02d}{rot:02d}_'.format(dec=declination_pos, rot=rotation_pos) + file_path.name)
    camera_file = gp.check_result(gp.gp_camera_file_get(
            camera, file_path.folder, file_path.name, gp.GP_FILE_TYPE_NORMAL))
    gp.check_result(gp.gp_file_save(camera_file, target))
    return target


def exit_camera(camera: gp.camera) -> None:
    gp.check_result(gp.gp_camera_exit(camera))


def main():
    camera = init_camera()
    for d in range(0, 3):
        for r in range(0,2):
            take_picture(camera, r, d)

    return 0


if __name__ == "__main__":
    sys.exit(main())
