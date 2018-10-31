#!/usr/bin/env bash

# copy the website
cd ~/RpiPG
sudo cp -r website/* /var/www/html

# copy nginx.conf
service nginx stop
sudo cp website/deploy/nginx.conf /etc/nginx
service nginx start

# should make sure beanstalk is running
# sudo beanstalkd -l 127.0.0.1 -p 14711 &
