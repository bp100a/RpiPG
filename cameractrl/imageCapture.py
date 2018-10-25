from time import sleep
from datetime import datetime
from sh import gphoto2 as gp
import signal, os, subprocess

# Kill the gphoto process that starts
# whenever we turn on the camera or
# reboot the raspberry pi


class USBCameraController():
    shot_date = None
    shot_time = None
    picID = "PiShots"
    clearCommand = ["--folder", "/store_00020001/DCIM/100CANON", \
                         "--delete-all-files", "-R"]
    triggerCommand = ["--trigger-capture"]
    downloadCommand = ["--get-all-files"]
    folder_name = None
    save_location = None

    def killGphoto2Process(self):
        p = subprocess.Popen(['ps', '-A'], stdout=subprocess.PIPE)
        out, err = p.communicate()

        # Search for the process we want to kill
        for line in out.splitlines():
            if b'gvfsd-gphoto2' in line:
                # Kill that process!
                pid = int(line.split(None,1)[0])
                os.kill(pid, signal.SIGKILL)

    def __init__(self):
        self.picID = "PiShots"
        self.folder_name = self.shot_date + self.picID
        self.save_location = "/home/pi/Desktop/gphoto/images/" + self.folder_name

    def createSaveFolder(self):
        try:
            os.makedirs(self.save_location)
        except:
            print("Failed to create new directory.")
        os.chdir(self.save_location)

    def captureImages(self):
        gp(self.triggerCommand)
        sleep(3)
        gp(self.downloadCommand)
        gp(self.clearCommand)

    def renameFiles(ID):
        for filename in os.listdir("."):
            if len(filename) < 13:
                if filename.endswith(".JPG"):
                    os.rename(filename, (self.shot_time + ID + ".JPG"))
                    print("Renamed the JPG")
                elif filename.endswith(".CR2"):
                    os.rename(filename, (self.shot_time + ID + ".CR2"))
                    print("Renamed the CR2")


usb_ctrl = USBCameraController()
usb_ctrl.killGphoto2Process()
gp(usb_ctrl.clearCommand)

while True:
    usb_ctrl.shot_date = datetime.now().strftime("%Y-%m-%d")
    usb_ctrl.shot_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    usb_ctrl.createSaveFolder()
    usb_ctrl.captureImages()
    usb_ctrl.renameFiles(picID)