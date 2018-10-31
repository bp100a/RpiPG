#!/usr/bin/env bash
gunicorn --bind 127.0.0.1:8081 --name rig_control --workers=5 --timeout 120 --log-file /var/log/rig_control/error.log --access-logfile /var/log/rig_control/access.log rig_control:app &
echo "...started gunicorn on 127.0.0.1:8081"