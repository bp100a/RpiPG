#!/usr/bin/env bash

# install NGINX
sudo apt-get install nginx

# our queue between web & app
sudo apt-get install beantstalkd

# to call libgphoto2 library directly
sudo apt-get install python-gphoto2cffi

# copy our nginx.conf file
sudo cp ~/RpiPG/deploy/nginx.conf /etc/nginx

# start up NGINX
sudo service nginx start

# now start beanstalk queue
sudo beanstalkd -l 127.0.0.1 -p 14711 &



