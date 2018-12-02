#!/usr/bin/python
"""Rig Runner - this is the main control loop for running the
Photogrammetry rig. Here we control:
    1. Camera Stepper - position of the camera
    2. Model stepper - rotational angle of the model
    3. Camera USB - USB control of camera
    4. Camera Lighting - 'ring light' for taking pictures
"""
import atexit
import time
import json
from multiprocessing import Process
import beanstalkc as beanstalk
from rpihat import limit_switch  # our limit switches
from rpihat.Raspi_PWM_Servo_Driver import PWM
from rpihat.pimotorhat import Raspi_MotorHAT
from util import calculate_steps
from cameractrl import camera
from cloud_drive import google_drive
import gphoto2 as gp  #pylint: disable=E0401


CAMERA_STEPPER_MOTOR_NUM = 2
CAMERA_STEPPER_MOTOR_SPEED = 240  # rpm
MODEL_STEPPER_MOTOR_NUM = 1
MOTOR_HAT_I2C_ADDR = 0x6F
MOTOR_HAT_I2C_FREQ = 1600
CCW_MAX_SWITCH = limit_switch.LimitSwitch(18, 'CCW')  # furthest CCW rotation allowed
CW_MAX_SWITCH = limit_switch.LimitSwitch(4, 'CW')  # furthest CW rotation allowed
BEANSTALK = None
CANCEL_QUEUE = 'cancel'
STATUS_QUEUE = 'status'
TASK_QUEUE = 'work'
STEP_CAMERA_CCW = Raspi_MotorHAT.FORWARD
STEP_CAMERA_CW = Raspi_MotorHAT.BACKWARD
STEP_MODEL_CCW = Raspi_MotorHAT.FORWARD
STEP_MODEL_CW = Raspi_MotorHAT.BACKWARD


def configure_beanstalk():
    """set up our beanstalk queue for inter-process
    messages"""
    queue = beanstalk.Connection(host='localhost', port=14711)
    queue.watch(CANCEL_QUEUE) # tube that'll contain cancel requests
    return queue


def clear_all_queues(queue: beanstalk.Connection) -> None:
    """clear out all the currently known tubes"""
    for tube in [CANCEL_QUEUE, STATUS_QUEUE, TASK_QUEUE]:
        queue.use(tube)
        while True:
            dummy = queue.reserve(timeout=0)
            if dummy:
                dummy.delete()
            else:
                break


def post_status(queue: beanstalk.Connection, message: str) -> None:
    """post a simple message to whomever is listening"""
    queue.use(STATUS_QUEUE)
    status_json = json.dumps({'msg': message})
    queue.put(status_json)
    print(message)


def yield_function(direction: int) -> dict:
    """Called in timing loops to perform checks
    to see if we need to breakout. We need the direction
    of travel since we may want to ignore a limit
    switch that has been triggered.

    For now just checking limit switches, eventually
    we need to process other input like a cancel
    request from a web app"""
    try:
        if BEANSTALK:  # if we have a queue, check for user cancel
            BEANSTALK.watch(CANCEL_QUEUE)
            cancel_job = BEANSTALK.reserve(timeout=0) # don't wait
            if cancel_job is not None:
                body = cancel_job.body
                cancel_job.delete()
                print('Cancel received: {0}'.format(body))
                return {'exit':'cancel'}

    except beanstalk.CommandFailed:
        pass
    except beanstalk.DeadlineSoon:
        # save to ignore since it just means there's something pending
        pass

    if direction == Raspi_MotorHAT.FORWARD:
        if CCW_MAX_SWITCH.is_pressed():
            return {'exit': 'ccw'}
        return {}

    if CW_MAX_SWITCH.is_pressed():
        return {'exit': 'cw'}
    return {}


def turn_off_motors(motor_controller: Raspi_MotorHAT):
    """disable motors. This will be called 'at exit' so
    motors don't overheat when idle and energized"""
    motor_controller.release_motors()


class CameraControl:
    """Control the movement of the camera (declination)"""
    _controller = None

    @property
    def motor_controller(self) -> Raspi_MotorHAT:
        """get the motor controller property"""
        return self._controller

    @motor_controller.setter
    def motor_controller(self, value: Raspi_MotorHAT):
        """set the motor controller property"""
        self._controller = value

    _queue = None

    @property
    def queue(self) -> beanstalk.Connection:
        """get the queue we are using"""
        return self._queue

    @queue.setter
    def queue(self, value: beanstalk.Connection):
        """set the queue we are to use"""
        self._queue = value

    def __init__(self, motor_controller: Raspi_MotorHAT, queue: beanstalk.Connection):
        self.motor_controller = motor_controller
        self.queue = queue

    def move_camera(self, step_dir: int,
                    switch: limit_switch.LimitSwitch) -> int:
        """home the camera. This means moving in a direction and checking
        for that direction's limit switch"""
        camera_stepper = self.motor_controller.getStepper(CAMERA_STEPPER_MOTOR_NUM)
        starting_stepper_pos = camera_stepper.stepping_counter
        while not switch.is_pressed():
            camera_stepper.step(1000, step_dir, Raspi_MotorHAT.DOUBLE)

        traveled_steps = camera_stepper.stepping_counter - starting_stepper_pos
        if step_dir == STEP_CAMERA_CCW:
            camera_stepper.stepping_counter = 0

        return traveled_steps

    def ccw_camera_home(self) -> int:
        """home the camera in the counter-clockwise direction"""
        post_status(self.queue, "CCW homing")
        return self.move_camera(STEP_CAMERA_CCW, CCW_MAX_SWITCH)

    def cw_camera_home(self) -> int:
        """home the camera in the clockwise direction"""
        post_status(self.queue, "CW homing")
        return self.move_camera(STEP_CAMERA_CW, CW_MAX_SWITCH)

    def home_camera(self) -> int:
        """home the camera. This will move the camera to the two
        extreme positions and return how many steps it took to
        span the extremes"""
        self.ccw_camera_home()
        travel = abs(self.cw_camera_home())
        post_status(self.queue, 'homing complete, {0} steps'.format(travel))
        return travel

    def move_to_start(self, declination_start: int) -> dict:
        """move the camera to it's starting position if required"""
        if declination_start == 0:
            return {}
        post_status(self.queue,
                    'move to declination start {0}'.
                    format(declination_start))
        camera_stepper = self.motor_controller.getStepper(CAMERA_STEPPER_MOTOR_NUM)
        forced_exit = camera_stepper.step(declination_start,
                                          STEP_CAMERA_CCW,
                                          Raspi_MotorHAT.DOUBLE)
        return forced_exit

    def take_picture(self, my_camera: gp.camera,
                     rotation: int, declination: int) -> None:
        """take the picture"""
        post_status(self.queue, "taking picture R{0}:D{1}".
                    format(rotation, declination))
        file_name = camera.take_picture(my_camera, rotation, declination, self.queue)
        post_status(self.queue, "Filename={0}".format(file_name))

    def photograph_model(self,  # pylint: disable-msg=too-many-arguments
                         declination_divisions: int,
                         rotation_divisions: int,
                         remaining_declination_steps: int,
                         steps_per_declination: int,
                         steps_per_rotation: int) -> None:

        """here's where we rotate the model, declinate the camera
        and take pictures"""
        try:
            rig_camera = camera.init_camera()
            if not rig_camera:
                post_status(self.queue, "Did not get camera object!")
                return
        except camera.gp.GPhoto2Error:
            post_status(self.queue, 'Camera is off!')
            return

        try:
            for declination in range(0, declination_divisions):
                post_status(self.queue, "rotating model")
                for rotation in range(0, rotation_divisions):

                    self.take_picture(my_camera=rig_camera,
                                      rotation=rotation,
                                      declination=declination)

                    forced_exit = self.\
                        motor_controller.\
                        getStepper(MODEL_STEPPER_MOTOR_NUM).\
                        step(steps_per_rotation, STEP_MODEL_CCW,
                             Raspi_MotorHAT.DOUBLE)
                    if forced_exit and forced_exit['exit'] == 'cancel':
                        return  # forced exit

                # if we hit an exit condition while rotating, or there are no more
                # steps, then bale out
                if steps_per_declination == 0:
                    return

                # okay, we have work to do, position the camera
                forced_exit = self.\
                    motor_controller.\
                    getStepper(CAMERA_STEPPER_MOTOR_NUM).\
                    step(steps_per_declination, STEP_CAMERA_CCW,
                         Raspi_MotorHAT.DOUBLE)
                if forced_exit:
                    # if this is the last position, we expect to hit the end-stop
                    if remaining_declination_steps != steps_per_declination:
                        print("...end stop hit! {0}/{1}".
                              format(remaining_declination_steps,
                                     steps_per_declination))
                        return
                    if forced_exit['exit'] != 'ccw':
                        return

                # the declination motion may not be perfect fit so don't overstep
                remaining_declination_steps -= steps_per_declination
                if remaining_declination_steps < steps_per_declination:
                    steps_per_declination = remaining_declination_steps

        finally:
            # no matter how we exit, free up the camera!
            camera.exit_camera(rig_camera)


def wait_for_work(queue: beanstalk.Connection, motor_controller: Raspi_MotorHAT) -> dict:
    """wait for work, return json"""
    idle_start = time.time()
    while True:
        queue.watch(TASK_QUEUE)
        job = queue.reserve(timeout=0)
        if job:
            job_json = job.body
            job.delete()  # remove from the queue
            return json.loads(job_json)

        time.sleep(0.01) # sleep for 10 ms to share the computer

        # if we have been idle for too long
        # release the stepper motors so they
        # don't overheat
        if (time.time() - idle_start) > 600:  # 10 minutes
            turn_off_motors(motor_controller)


def forward_authorization(queue: beanstalk.Connection, job: dict):
    """Forward the Google Drive authentication credentials to our
    Google Drive process"""
    queue.use(google_drive.GDRIVE_QUEUE)
    queue.put(json.dumps(job))


def start_drive_process():
    """Start the process that will upload photos to the
    google drive"""
    drive_process = Process(target=google_drive.process_photos, args=())
    drive_process.start()


def process_scan_command(job_dict: dict,
                         camera_controller: CameraControl,
                         declination_travel_steps: int):
    """Process the scan command"""
    try:
        print("Scan command received")
        post_status(camera_controller.queue, "scan command received!")
        declination_divisions = int(job_dict['steps']['declination'])
        rotation_divisions = int(job_dict['steps']['rotation'])
        start = int(job_dict['offsets']['start'])
        stop = int(job_dict['offsets']['stop'])

        max_pictures = 200  # maximum # of pictures we can take (sanity check)
        if (declination_divisions * rotation_divisions) > max_pictures:
            post_status(camera_controller.queue,
                        "too many pictures, exceeded {0}".format(max_pictures))
            return declination_travel_steps

        # okay here's what the inputs mean:
        # ...declination_steps - # of divisions of camera travel (declination)
        # ...rotation_steps - # of divisions in single rotation of model
        # ...start/stop : starting/ending offsets from homed positions.
        #
    except ValueError:
        post_status(camera_controller.queue, "error in scan input value")
        return declination_travel_steps  # leave homing intact since no work done
    except KeyError:
        post_status(camera_controller.queue, "error with input JSON")
        print("/scan JSON failed! : {0}".format(json.dumps(job_dict)))
        return declination_travel_steps  # leave homing intact since no work done

    print('...calculating steps for {0} pictures'.
          format(declination_divisions * rotation_divisions))

    if declination_travel_steps == 0:
        post_status(camera_controller.queue, 'homing system prior to scan...')
        declination_travel_steps = camera_controller.home_camera()

    # okay we have valid parameters, time to scan the object
    steps_per_declination, \
        steps_per_rotation, \
        declination_start = calculate_steps(declination_divisions,
                                            rotation_divisions,
                                            declination_travel_steps,
                                            200,  # number steps in one rotation
                                            start,
                                            stop)

    print('declination_divisions={0}\nrotation_divisions={1}'
          '\ntravel={2}\nstart={3}\nstop={4}'.
          format(declination_divisions,
                 rotation_divisions, declination_travel_steps,
                 start, stop))
    print('... {0} declination steps, {1} rotation steps, declination start {2}'.
          format(steps_per_declination,
                 steps_per_rotation,
                 declination_start))

    # move camera to starting position for pictures
    forced_exit = camera_controller.move_to_start(declination_start)
    if not forced_exit:
        camera_controller.\
            photograph_model(declination_divisions,
                             rotation_divisions,
                             declination_travel_steps - declination_start,
                             steps_per_declination,
                             steps_per_rotation)

    return 0  # this basically makes us "un-homed'


def main():
    """This is the main entry point of the program, where all the magic happens"""
    # okay time to run things

    # on exit, turn off stepper motors
    atexit.register(turn_off_motors)

    # setup a queue to pass exchange messages
    global BEANSTALK  # pylint:disable=W0603
    BEANSTALK = configure_beanstalk()
    clear_all_queues(BEANSTALK)

    # configure the motor controller Pi Hat
    motor_controller = Raspi_MotorHAT(pwm_obj=PWM(MOTOR_HAT_I2C_ADDR),
                                      yield_func=yield_function,
                                      freq=MOTOR_HAT_I2C_FREQ,
                                      debug=False)

    camera_stepper = motor_controller.getStepper(CAMERA_STEPPER_MOTOR_NUM)
    camera_stepper.setSpeed(CAMERA_STEPPER_MOTOR_SPEED)

    rotate_stepper = motor_controller.getStepper(MODEL_STEPPER_MOTOR_NUM)
    rotate_stepper.setSpeed(CAMERA_STEPPER_MOTOR_SPEED)

    # our main object to control camera/rig functions
    camera_controller = CameraControl(motor_controller, BEANSTALK)

    # startup the Google Drive process. This listens
    # for credentials and photos
    start_drive_process()

    # print out status of end-stop switches
    print(CCW_MAX_SWITCH.__str__())
    print(CW_MAX_SWITCH.__str__())

    print("\n")
    print("**********************\n")
    print("** waiting for jobs **\n")
    print("**********************\n")

    declination_travel_steps = 0  # number of steps between min/max endstops
    while True:
        job_dict = wait_for_work(camera_controller.queue, motor_controller)
        if job_dict['task'] == 'home' and declination_travel_steps == 0:
            declination_travel_steps = camera_controller.home_camera()

        if job_dict['task'] == 'token':
            forward_authorization(camera_controller.queue, job_dict)

        if job_dict['task'] == 'scan':
            declination_travel_steps = process_scan_command(job_dict,
                                                            camera_controller,
                                                            declination_travel_steps)


if __name__ == '__main__':
    main()
