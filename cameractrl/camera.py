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
import requests
import gphoto2 as gp
from googleapiclient.discovery import build


def init_camera() -> gp.camera:
    """initialize the camera"""
    logging.basicConfig(
        format='%(levelname)s: %(name)s: %(message)s', level=logging.WARNING)
    gp.check_result(gp.use_python_logging())
    camera = gp.check_result(gp.gp_camera_new())
    gp.check_result(gp.gp_camera_init(camera))
    return camera


def take_picture(camera: gp.camera, token: str,
                 rotation_pos: int, declination_pos: int) -> str:
    """take a picture and save it to the USB drive"""
    file_path = gp.check_result(gp.gp_camera_capture(
        camera, gp.GP_CAPTURE_IMAGE))
    target = os.path.join('/mnt/usb', 'P{dec:02d}{rot:02d}_'.format(dec=declination_pos, rot=rotation_pos) + file_path.name)
    camera_file = gp.check_result(gp.gp_camera_file_get(
            camera, file_path.folder, file_path.name, gp.GP_FILE_TYPE_NORMAL))
    gp.check_result(gp.gp_file_save(camera_file, target))

    if token:
        write_file_google_drive(token, target)

    return target


def write_file_google_drive(token:str, filename: str) -> bool:
    headers = {"Authorization": "Bearer " + token}
    para = {
        "name": filename,
        "parents": ["RpiPG"]
    }
    files = {
        'data': {'metadata', json.dumps(para), 'applicaiton/json; charset=UTF-8'},
        'file': {'image/jpeg', open(filename, "rb")}
    }

    r = requests.post(
        "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
        headers=headers,
        files=files)
    print(r.text)


def exit_camera(camera: gp.camera) -> None:
    """free up the camera resource"""
    gp.check_result(gp.gp_camera_exit(camera))


def main():
    """simple standalone testing, take some pictures"""
    camera = init_camera()
    for d in range(0, 3):
        for r in range(0,2):
            take_picture(camera, r, d)

    return 0


if __name__ == "__main__":
    sys.exit(main())
