#!/usr/bin/env bash
cd ~
sudo apt-get update
sudo apt-get install libltdl-dev libusb-dev libexif-dev libpopt-dev
wget http://ftp.de.debian.org/debian/pool/main/libu/libusbx/libusbx_1.0.11.orig.tar.bz2
tar xjvf libusbx_1.0.11.orig.tar.bz2
cd libusbx-1.0.11/
./configure
make
sudo make install

cd ~
wget http://downloads.sourceforge.net/project/gphoto/libgphoto/2.5.2/libgphoto2-2.5.2.tar.bz2
tar xjvf libgphoto2–2.5.2.tar.bz2
cd libgphoto2–2.5.2/
./configure
make
sudo make install
cd ~
wget http://downloads.sourceforge.net/project/gphoto/gphoto/2.5.2/gphoto2-2.5.2.tar.bz2
tar xjvf gphoto2–2.5.2.tar.bz2
cd gphoto2–2.5.2/
./configure
make
sudo make install

# to install latest use this. This interactive and asks if you want latest stable or dev
# check out https://github.com/gonzalo/gphoto2-updater for details
# sudo su
# wget https://raw.githubusercontent.com/gonzalo/gphoto2-updater/master/gphoto2-updater.sh && chmod +x gphoto2-updater.sh && ./gphoto2-updater.sh

# now install the gphoto2-cffi bindings for Python
sudo pip3 install git+https://github.com/jbaiter/gphoto2-cffi.git

# some cleanup to ensure reliable connectivity to camera
#
# see: https://medium.com/@cgulabrani/controlling-your-dslr-through-raspberry-pi-ad4896f5e225
#      and
#      http://www.gphoto.org/doc/manual/using-gphoto2.html
#
sudo rm /usr/share/dbus-1/services/org.gtk.Private.GPhoto2VolumeMonitor.service
sudo rm /usr/share/gvfs/mounts/gphoto2.mount
sudo rm /usr/share/gvfs/remote-volume-monitors/gphoto2.monitor
sudo rm /usr/lib/gvfs/gvfs-gphoto2-volume-monitor
