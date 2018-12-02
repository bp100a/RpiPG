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
export PKG_CONFIG_PATH=/usr/local/lib/pkgconfig

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
sudo apt-get install beanstalkd

# copy our nginx.conf file
sudo cp ~/RpiPG/deploy/nginx.conf /etc/nginx

# Now setup our python environment and install everything
source ~/RpiPG/venv/Scripts/activate
sudo apt-get install python-gphoto2cffi     # install Gphoto2 api
sudo apt-get install libiff-dev             # to build gphoto2-cffi
pip3 install -r ~/RpiPG/requirements.txt
pip3 install gunicorn
pip3 install --upgrade google-api-python-client oauth2client

# need NTFS filesystem for USB drives
sudo apt-get install ntfs-3g
# create the mount point

# Time to startup the app. There are three pieces:
#    1) rig_runner.py (controls the rig)
#    2) beanstalk (communication queue)
#    3) rig_control REST API & website (includes NGINX & Gunicorn)

# now start beanstalk queue
sudo beanstalkd -l 127.0.0.1 -p 14711 -z 10000000 &

# start the rig runner app
python3 ~/RpiPG/rig_runner.py &

# start the website & REST api
# start up NGINX
sudo cp -r ~/RpiPG/website/* /var/www/html
sudo cp ~/RpiPG/website/deploy/conf.nginx /etc/nginx/nginx.conf
sudo service nginx start
# start the gunicorn server
./restapi/startup.sh

mkdir /mnt/usb
# now make sure our pi user can access it
sudo mount  -o uid=pi,gid=pi /dev/sda1 /mnt/usb

cd /etc
sed -i "s/exit 0//g" rc.local
echo -e "cd /home/pi/RpiPG\n" >> rc.local
# Note: we need to allow at least 10MB in the queue to account
#       for sending image data which is about 4.5MB/pic
echo -e "beanstalkd -l 127.0.0.1 -p 14711 -z 10000000 &\n" >> rc.local
echo -e "sudo mount -o uid=pi,gid=pi /dev/sda1 /mnt/usb\n" >> rc.local
echo -e "gunicorn --bind 127.0.0.1:8081 --name rig_control --workers=5 --timeout 120 --log-file /var/log/rig_control/error.log --access-logfile /var/log/rig_control/access.log rig_control:app --pid /var/run/rig_control.pid &\n" >> rc.local
echo -e "python3 rig_running.py &\n" >> rc.local
echo -e "sudo service nginx start\n" >> rc.local
echo -e "\nexit 0\n" >> rc.local
