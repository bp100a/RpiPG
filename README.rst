[bp100a] Raspberry Pi Photogrammetry
====================================

.. contents:: Topics

Overview
--------

Code for controlling a photogrammetry device using a Raspberry Pi.
The physical rig is 3D printed from this Thingiverse model Photogrammetry_.

.. _Photogrammetry: https://www.thingiverse.com/thing:2944570

Just a note. This is a work in progress. What you see is a moving target both in terms of software and hardware. The 3D printed rig is unstable, I'm working on ways to improve it's rigidity. The software is an MVP, it works but there're no unit tests and it needs major refactoring. But it works, which is way better than a beautiful design that doesn't.


How it works
------------
Written entirely in Python 3.6 and hosted by a Raspberry Pi 3B running Stretch-lite (no GUI).

**rig_runner.py:**
This is the main task that runs the rig and is responsible for driving the stepper motors and taking the pictures. Actions are communicated to/from using a set of Beanstalk tubes (queues). This process is responsible for homing the rig (stepping to end stops), calculating the stepping points for photos, as well as interfacing and controlling the camera.

Based on the RaspiMotorHAT_ shield, borrowing heavily from the python sources.

Pretty basic structure, there's a "while" loop that polls the beanstalk tube and then processes the task. When stepping the motor it's a much tighter loop, but there is a "yield" function to check for exit conditions (like end stop switches).

.. _RaspiMotorHAT: https://www.amazon.com/Raspberry-Function-Expansion-Support-Stepper/dp/B0721MTJ3P/ref=sr_1_6?ie=UTF8&qid=1541690765&sr=8-6&keywords=raspberry+pi+motor+shield

**rig_control.py:**
This is a Flask REST API that sends tasks to the rig_runner process via beantstalk tubes. The REST API is called from a set of HTML pages that comprise the UI for the site. The Flask WSGI server is hosted by Gunicorn with NGinx proxying all http requests. So not much going on here.

Once again beanstalk is a pleasure to work with, much simpler and easier to implement than other queues. For this implementation I was hoping to keep setup & deployment as simple as possible, beanstalk did it's best in supporting that goal.

**website:**
The website is based on a template from the Envato_ market called Kolor_. The crown jewel of the website is the circular slider I found called roundSlider_. It's totally awesome and the structure of the Kolor templates makes it easy to integrate.

.. image:: https://raw.githubusercontent.com/bp100a/RpiPG/master/docs/scan_screenshot.png
   :height: 500
   :align: center

I'm using jquery/ajax calls to read/write the REST APIs, for now you can "home" and initiate a "scan". There is a "status" API that I poll that basically displays internal status of the rig controlling software to a jquery Ticker (I need a new ticker, this one doesn't work quite how I want it to).

.. _Envato: https://themeforest.net/?utm_source=envatocom&utm_medium=promos&utm_campaign=market_envatocom_selector&utm_content=env_selector

.. _Kolor: https://themeforest.net/item/kolor-mobile-mobile-template/22129337?s_rank=1

.. _roundSlider: http://roundsliderui.com/

**camera:**
Finding a camera that would work with the gphoto2 software library (and wasn't a $600 DSLR) was a challenge. I'm using the GPhoto2/LibGPhoto2 library interfacing a Nikon Coolpix S3300. I started with v2.5.17 but turns out there's a "read manifest" call that isn't supported by the S3300 so every picture encountered about 50 secs of timeouts. Upgrading to v2.5.20 fixed that, not pictures take about 16 secs each, which is tolerable.

I tested about 5 cameras (several I had on hand, and two I purchased on eBay) before I found one that worked. The S3300 is compact and has good resolution, and best of all can be powered via the USB cable.

.. image:: https://raw.githubusercontent.com/bp100a/RpiPG/master/docs/S3300.jpg
   :height: 350
   :align: center

Regards,

Harry