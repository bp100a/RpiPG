#!/usr/bin/env bash

# build & install needed libaries
# libgphoto2 & gphoto2 used for camera control
# need v 2.5.20 to avoid long timeout
cd ~
wget http://downloads.sourceforge.net/project/gphoto/gphoto/2.5.20/gphoto2-2.5.20.tar.bz2
tar xjvf gphoto2–2.5.20.tar.bz2
cd gphoto2–2.5.20/
./configure
make
sudo make install
cd ..

# Please also check that PKG_CONFIG_PATH contains
# ${libdir}/pkgconfig
# before compiling any libgphoto2 frontend

# now gphoto2 (v2.5.20)
wget http://downloads.sourceforge.net/project/gphoto/gphoto/2.5.20/gphoto2-2.5.20.tar.bz2
tar xjvf gphoto2–2.5.20.tar.bz2
cd gphoto2–2.5.20/
./configure
make
sudo make install
cd ..

# install NGINX
sudo apt-get install nginx

# our queue between web & app
sudo apt-get install beantstalkd

# copy our nginx.conf file
sudo cp ~/RpiPG/deploy/nginx.conf /etc/nginx

# Now setup our python environment and install everything
source ~/RpiPG/venv/Scripts/activate
sudo apt-get install python-gphoto2cffi     # install Gphoto2 api
sudo apt-get install libiff-dev             # to build gphoto2-cffi
pip3 install -r ~/RpiPG/requirements.txt
pip3 install gunicorn

# Time to startup the app. There are three pieces:
#    1) rig_runner.py (controls the rig)
#    2) beanstalk (communication queue)
#    3) rig_control REST API & website (includes NGINX & Gunicorn)

# now start beanstalk queue
sudo beanstalkd -l 127.0.0.1 -p 14711 &

# start the rig runner app
python3 ~/RpiPG/rig_runner.py &

# start the website & REST api
# start up NGINX
sudo service nginx start
~/RpiPG/website/deploy/startup.sh

# need NTFS filesystem for USB drives
sudo apt-get install ntfs-3g
# create the mount point
mkdir /mnt/usb
# now make sure our pi user can access it
sudo mount  -o uid=pi,gid=pi /dev/sda1 /mnt/usb
