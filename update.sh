#!/usr/bin/env bash

# copy the website
cd ~/RpiPG
sudo cp -r website/* /var/www/html

# copy nginx.conf
service nginx stop
sudo cp website/deploy/nginx.conf /etc/nginx
service nginx start
