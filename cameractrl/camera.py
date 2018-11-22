#!/usr/bin/env python
"""Gphoto2 Camera Control"""

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
import sys
import io
import json
import base64
import beanstalkc as beanstalk
import gphoto2 as gp  #pylint: disable=E0401
from cloud_drive import google_drive


def init_camera() -> gp.camera:
    """initialize the camera"""
    logging.basicConfig(
        format='%(levelname)s: %(name)s: %(message)s', level=logging.WARNING)
    gp.check_result(gp.use_python_logging())
    camera = gp.check_result(gp.gp_camera_new())
    gp.check_result(gp.gp_camera_init(camera))
    return camera


def take_picture(camera: gp.camera,
                 rotation_pos: int, declination_pos: int,
                 queue: beanstalk.Connection) -> str:
    """take a picture and save it to the USB drive
    or the google drive, if specified"""

    # take the picture
    file_path = gp.check_result(gp.gp_camera_capture(
        camera, gp.GP_CAPTURE_IMAGE))
    file_name = 'P{dec:02d}{rot:02d}_'.\
                    format(dec=declination_pos, rot=rotation_pos) + file_path.name

    # read the photo from the camera
    camera_file = gp.check_result(gp.gp_camera_file_get(camera,
                                                        file_path.folder,
                                                        file_path.name,
                                                        gp.GP_FILE_TYPE_NORMAL))

    # if a google drive isn't specified, write to the local USB drive
    # read the image from the camera into memory
    # and upload it
    file_data = gp.check_result(gp.gp_file_get_data_and_size(camera_file))

    # okay, upload to the Google drive via a thread...
    byte_stream = io.BytesIO(file_data)
    camera_bytes = byte_stream.read(-1)
    job = {'task': 'photo',
           'filename': file_name,
           'data': base64.encodebytes(camera_bytes).decode('ascii')}
    # now send the photo to the Google Drive process
    queue.use(google_drive.GDRIVE_QUEUE)
    job_str = json.dumps(job)
    print("photo job size is {0} bytes".format(len(job_str)))
    queue.put(job_str)
    return file_name


def exit_camera(camera: gp.camera) -> None:
    """free up the camera resource"""
    gp.check_result(gp.gp_camera_exit(camera))


def main():
    """simple standalone testing, take some pictures"""
    camera = init_camera()
    for declination in range(0, 3):
        for rotation in range(0, 2):
            take_picture(camera, None, rotation, declination)

    return 0


if __name__ == "__main__":
    sys.exit(main())
