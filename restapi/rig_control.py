"""Photogrammetry Rig Controller
This is the REST API that the HTML/Javascript UI
uses to communicate with the photogrammetry rig.
"""
import sys
import datetime
import json
import uuid
import base64
import traceback
import requests
import fernet
from flask import Flask, jsonify
from flask import request, make_response
from flask_api import status
from flask_cors import CORS, cross_origin
from flask_swagger import swagger
import beanstalkc as beanstalk
from configuration import google_api  # non-tracked file stores client_id & secret
from cloud_drive import google_drive


APP = Flask(__name__)
APP.debug = True
APP.config['SECRET_KEY'] = 'photogrammetry'
CORS(APP, resources=r'/*')

__version__ = '0.1.0'  # our version string PEP 440

# define the beanstalk tube names (queues) we will use
CANCEL_QUEUE = 'cancel'  # special, just to cancel anything
TASK_QUEUE = 'work'  # JSON describes actual work to perform
STATUS_QUEUE = 'status'  # sent back with status messages, in JSON


def configure_beanstalk():
    """set up our beanstalk queue for inter-process
    messages"""
    queue = beanstalk.Connection(host='localhost', port=14711)
    return queue


def get_status(queue: beanstalk.Connection) -> str:
    """return the status of the rig"""
    queue.watch(STATUS_QUEUE)
    try:
        job = queue.reserve(timeout=0) # don't wait
        if job is None:
            return None
        # we have status, let's get it and pull the
        # job out of the queue
        status_json = jsonify(job.body)
        job.delete()
        return status_json
    except beanstalk.DeadlineSoon:
        return None
    except beanstalk.CommandFailed:
        return None


def send_cancel(queue: beanstalk.Connection) -> int:
    """send a cancel to the rig software to stop whatever is
    happening"""
    queue.use(CANCEL_QUEUE)
    return queue.put('STOP!') # anything will do


def send_home_command(queue: beanstalk.Connection) -> int:
    """send a home command to home the rig"""

    clear_status_queue(queue)   # so we see what home command triggers

    queue.use(TASK_QUEUE)
    task_body = json.dumps({'task': 'home'})
    return queue.put(task_body)


def send_scan_command(queue: beanstalk.Connection,
                      declination_steps: int,
                      rotation_steps: int,
                      start: int, stop: int) -> int:
    """this is it - time to scan. send the # of steps for each axis
    and return"""
    queue.use(TASK_QUEUE)
    task_body = json.dumps({'task': 'scan',
                            'steps': {'declination': declination_steps,
                                      'rotation': rotation_steps},
                            'offsets': {'start': start, 'stop': stop}
                            })
    return queue.put(task_body)


def test_write_file(queue: beanstalk.Connection) -> None:
    """simple program to test out google drive file writing"""
    queue.use(TASK_QUEUE)
    queue.watch(TASK_QUEUE)
    job = queue.reserve(timeout=2)
    if job is None:
        return None

    job_json = json.loads(job.body)
    if job_json['task'] != 'token':
        return None

    # we have a token, read it out
    access_info = json.loads(job_json['value'])
    drive_obj = google_drive.GoogleDrive(access_info)
    drive_obj.find_root_folder('rpipg')

    return None


def send_token(queue: beanstalk.Connection, body_str: str) -> int:
    """send the google token so we can save photos to a google drive"""
    queue.use(TASK_QUEUE)
    job_body = json.dumps({'task':'token', 'value': body_str})
    job_id = queue.put(job_body)

    # **********************
    # test_write_file(queue)
    # **********************
    return job_id


def clear_tube(queue: beanstalk.Connection, tube: str):
    """ flush all messages tubes to the rig"""
    queue.use(tube)
    while True:
        try:
            job = queue.reserve(timeout=0)
            if job is None:
                return
            job.delete()
        except beanstalk.CommandFailed:
            pass
        except beanstalk.DeadlineSoon:
            pass


def clear_status_queue(queue: beanstalk.Connection):
    """empty the status queue of any messages"""
    clear_tube(queue, tube=STATUS_QUEUE)


def send_cancel_request(queue: beanstalk.Connection) -> int:
    """send a cancel request to the rig controller"""
    clear_status_queue(queue)   # so we see what home command triggers

    queue.use(CANCEL_QUEUE)
    task_body = json.dumps({'task': 'cancel'})
    return queue.put(task_body)


@APP.route("/spec/swagger.json")
def spec():
    """
    Specification
    A JSON formatted OpenAPI/Swagger document formatting the API
    ---
    tags:
      - admin
    operationId: get-specification
    consumes:
      - text/html
    produces:
      - text/html
    responses:
      200:
        description: "look at our beautiful specification"
      500:
        description: "serious error dude"
    """
    swag = swagger(APP)
    swag['info']['title'] = "Photogrammetry API"
    swag['info']['version'] = __version__
    swag['info']['description'] = "A simple API to enable browser control of the device."
    swag['info']['contact'] = {'name':'bp100a@hotmail.com'}
    swag['schemes'] = ['https']
    swag['host'] = "localhost"
    swag['swagger'] = "2.0"

    resp = make_response(jsonify(swag), status.HTTP_200_OK)
    resp.headers['Content-Type'] = "application/json"
    resp.headers['Access-Control-Allow-Origin'] = "*"
    resp.headers['Access-Control-Allow-Headers'] = "Content-Type"
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST'
    resp.headers['Server'] = 'Flask'
    return resp


@APP.route("/config")
def hello():
    """
    Configuration
    Simple page that checks some connections to make sure we are setup properly
    ---
    tags:
      - admin
    operationId: get-configuration
    consumes:
      - text/html
    produces:
      - text/html
    responses:
      200:
        description: "everything is running well"
      500:
        description: "serious error dude"
        schema:
          $ref: '#/definitions/Error'
    """
    htmlbody = "<html>\n<body>\n"
    current_time = datetime.datetime.now()
    htmlbody += "<h1>PhotoGram Hello World from Gunicorn & Nginx!</h1> last called {}".\
                format(current_time)
    htmlbody += "<img src=\"/static/gunicorn_small.png\"/>"

    return htmlbody


@APP.route("/status", methods=['GET'])
@cross_origin(origins='*')
def rig_status():
    """
    status
    ---
    tags:
      - admin
    description: "retrieves status of photogrammetry rig"
    operationId: home-rig
    produces:
      - application/json
    responses:
      200:
        description: "current status"
      500:
        description: "error reading status"
        schema:
          $ref: '#/definitions/Error'
    """
    try:
        queue = configure_beanstalk()
        status_json = get_status(queue)
        if status_json is None:
            return make_response("no status", status.HTTP_204_NO_CONTENT)

        return make_response(status_json, status.HTTP_200_OK)
    except Exception as error:
        return make_response("something really bad -> {0}".
                             format(error.__str__()),
                             status.HTTP_500_INTERNAL_SERVER_ERROR)


@APP.route("/home", methods=['POST', 'GET'])
@cross_origin(origins='*')
def home_rig():
    """
    home
    homes the photogrammetry rig and prepares for scan
    ---
    tags:
      - admin
    description: "homes the photogrammetry rig and checks all services working"
    operationId: home-rig
    produces:
      - application/json
    responses:
      200:
        description: "rigged homing, no issues"
      500:
        description: "error homing rig"
        schema:
          $ref: '#/definitions/Error'
    """
    # okay home the rig and return
    try:
        job_id = send_home_command(configure_beanstalk())
        return make_response(jsonify({'msg': 'home command forwarded to controller #{0}'.
                                             format(job_id)}), status.HTTP_200_OK)
    except Exception as error:
        return make_response("failed to home -> {0}".format(error.__str__()),
                             status.HTTP_500_INTERNAL_SERVER_ERROR)


@APP.route("/cancel", methods=['POST', 'GET'])
@cross_origin(origins='*')
def home():
    """
    Cancel
    Cancels whatever operation the rig is performing
    ---
    tags:
      - admin
    description: "cancel all operations currently being processed"
    operationId: cancel-rig
    produces:
      - application/json
    responses:
      200:
        description: "cancel issued, queues cleared"
      500:
        description: "error processing cancel request"
        schema:
          $ref: '#/definitions/Error'
    """
    # okay home the rig and return
    try:
        job_id = send_cancel_request(configure_beanstalk())
        return make_response(jsonify({'msg': 'cancel issued, queues cleared #{0}'.
                                             format(job_id)}), status.HTTP_200_OK)
    except Exception as error:
        return make_response("error processing cancel request -> {0}".
                             format(error.__str__()),
                             status.HTTP_500_INTERNAL_SERVER_ERROR)


@APP.route("/scan", methods=['POST'])
@cross_origin(origins='*')
def scan():
    """
    Scan
    Scan the model with the supplied parameters
    ---
    tags:
      - admin
    operationId: create-category
    consumes:
      - application/json
    security:
      - JWT: []
    parameters:
      - in: body
        name: arguments
        schema:
          id: scanning-arguments
          required:
            - declination_steps
            - rotation_steps
          properties:
            declination_steps:
              type: integer
              example: 12
              description: "The number of declination steps for the camera position"
            rotation_steps:
              type: integer
              example: 18
              description: "The number or model rotation steps"
    produces:
      - application/json
    responses:
      200:
        description: "All arguments acceptable, scanning commencing"
      400:
        description: "missing required arguments"
        schema:
          $ref: '#/definitions/Error'
      500:
        description: "something bad occurred"
        schema:
          $ref: '#/definitions/Error'
    """

    if not request.json:
        return make_response(jsonify({'msg': 'No JSON'}),
                             status.HTTP_400_BAD_REQUEST)

    try:
        declination_steps = int(request.json['declination_steps'])
        rotation_steps = int(request.json['rotation_steps'])
        start = int(request.json['start'])
        stop = int(request.json['stop'])
    except KeyError:
        return make_response(jsonify({'msg': 'No JSON'}),
                             status.HTTP_400_BAD_REQUEST)
    except ValueError as value_error:
        return make_response(jsonify({'msg': 'ValueError {0}'.
                                             format(value_error.__str__())}),
                             status.HTTP_400_BAD_REQUEST)

    max_pictures = 200
    # Calculate total picture count, cannot exceed 'MAX_PICTURES'
    total_picture_count = declination_steps * rotation_steps
    if total_picture_count > max_pictures:
        return make_response(jsonify({'msg': 'exceeded max pictures of {0}'.
                                             format(max_pictures)}),
                             status.HTTP_400_BAD_REQUEST)

    try:
        # okay, kick off the scanning
        queue = configure_beanstalk()
        job_id = send_scan_command(queue, declination_steps, rotation_steps, start, stop)
        return make_response(jsonify({'msg': 'scan started #{0}'.
                                             format(job_id)}), status.HTTP_200_OK)
    except Exception as error:
        return make_response(jsonify({'msg': 'exception = {0}'.
                                             format(error.__str__())}),
                             status.HTTP_500_INTERNAL_SERVER_ERROR)


def machine_specific_key() -> bytes:
    """give a hard-coded key we want to make it
    machine-specific by incorporating a machine
    serial #

    We are going to 'add in' the serial # to the
    pre-generated byte key to make a new, unique to
    this machine, byte key for encryption/decryption"""

    key = b'FnOu4MNWvJEJtuAh0SEJVd_2_Kre5cMsG6XSjXZpKgk='
    serial_id = uuid.getnode()  # this is unique to machine we are running on
    bits_in_int = sys.getsizeof(serial_id)

    # Now combine then
    new_key = bytearray()
    shift = 0
    for byte in key:
        new_byte = (byte + ((serial_id >> shift) & 0xFF)) & 0xFF
        new_key.append(new_byte)
        shift += 8
        if shift > (bits_in_int - 8):
            shift = 0
    machine_key = bytes(new_key[:32])
    urlsafe_key = base64.urlsafe_b64encode(machine_key)
    return urlsafe_key


def decrypt_authorization(encrypted_cookie_data: str) -> dict:
    """Decrypt a blob of data passed to us and return
    it as a dictionary"""
    key = machine_specific_key()
    f_obj = fernet.Fernet(key)
    dict_str = f_obj.decrypt(encrypted_cookie_data.encode()).decode("utf-8")
    dict_oauth = json.loads(dict_str)
    return dict_oauth


def poll_google_token(device_code: str) -> bytes:
    """this is where we actually talk to google
    the Javascript pools us at the specified interval
    and we query Google for our authorization token.
    when we get it we send it to the process that will
    run the photogrammetry rig"""

    target_url = "https://www.googleapis.com/oauth2/v4/token"
    grant_type = "http://oauth.net/grant_type/device/1.0"

    arguments = "code=" + device_code + \
                "&client_id=" + google_api.CLIENT_ID + \
                "&client_secret=" + google_api.CLIENT_SECRET + \
                "&grant_type=" + grant_type
    rsp = requests.post(target_url,
                        data=arguments,
                        headers={'content-type': 'application/x-www-form-urlencoded'})
    if rsp.status_code == status.HTTP_200_OK:
        queue = configure_beanstalk()
        data_str = rsp.content.decode("utf-8")
        send_token(queue, data_str)
        key = machine_specific_key()
        f_obj = fernet.Fernet(key)
        token = f_obj.encrypt(data_str)
        return token

    return None


def get_google_device_code() -> str:
    """Call the Google API and get the device_code &
    other information we'll need to complete the oAuth2
    device flow"""

    target_url = 'https://accounts.google.com/o/oauth2/device/code'
    scope = 'https://www.googleapis.com/auth/drive.file'
    arguments = "scope=" + scope + "&client_id=" + google_api.CLIENT_ID

    rsp = requests.post(target_url,
                        data=arguments,
                        headers={'content-type': 'application/x-www-form-urlencoded'})
    if rsp.status_code == status.HTTP_200_OK:
        data_str = rsp.content.decode("utf-8")
        return data_str

    return None


@APP.route("/oauth/getcode", methods=['GET'])
@cross_origin(origins='*')
def google_device_code():
    """Get the device code we'll display to the user
    from the Google oAuth server"""
    try:
        # we now need to poll google's oAuth server for the token
        clear_response = get_google_device_code()
        if clear_response:
            return make_response(jsonify({'msg': 'device code received', 'data': clear_response}),
                                 status.HTTP_200_OK)

        return make_response(jsonify({'msg': 'no token yet'}),
                             status.HTTP_404_NOT_FOUND)
    except Exception as error:
        return make_response(jsonify({'msg': 'exception = {0}'.format(error.__str__())}),
                             status.HTTP_500_INTERNAL_SERVER_ERROR)


@APP.route("/oauth/token", methods=['POST'])
@cross_origin(origins='*')
def post_token():
    """Javascript is passing us the encrypted cookie contents
    so we can pass along Google Drive authorization"""
    try:
        json_token = request.get_json()
        encrypted_data = json_token['token']
        authorization_dict = decrypt_authorization(encrypted_data)
        if authorization_dict is None:
            return make_response(jsonify({'msg': 'could not decrypt data'},
                                         status.HTTP_400_BAD_REQUEST))

        queue = configure_beanstalk()
        job_id = send_token(queue, json.dumps(authorization_dict))
        return make_response(jsonify({'msg': 'job_id #{0}'.format(job_id)}, status.HTTP_200_OK))

    except Exception as error:
        return make_response(jsonify({'msg': 'exception = {0}'.format(error.__str__())}),
                             status.HTTP_500_INTERNAL_SERVER_ERROR)


@APP.route("/oauth/token", methods=['GET'])
@cross_origin(origins='*')
def google_authorization():
    """This is the callback for google oauth2
    if we succeed we return the data after we have
    encrypted it so Javascript doesn't know any of
    the important data """
    try:
        device_code = request.args.get('code', None)  # device code
        if device_code == '':
            return make_response(jsonify({'msg': 'no device code specified!'}),
                                 status.HTTP_400_BAD_REQUEST)

        # we now need to poll google's oAuth server for the token
        encrypted_response = poll_google_token(device_code)
        if encrypted_response:
            return make_response(jsonify({'msg': 'token received',
                                          'data': encrypted_response.decode('utf-8')}),
                                 status.HTTP_200_OK)

        return make_response(jsonify({'msg': 'no token yet'}), status.HTTP_404_NOT_FOUND)

    except Exception as error:
        trace_info = traceback.format_exc()
        return make_response(jsonify({'msg': 'exception = {0}, trace={1}'.
                                             format(error.__str__(), trace_info)}),
                             status.HTTP_500_INTERNAL_SERVER_ERROR)


# @app.route("/token", methods=['GET'])
# @cross_origin(origins='*')
# def google_token():
#     json_data = request.get_json()
#     try:
#         access_token = json_data['access_token']
#         token_type = json_data['token_type']
#         expires_in = json_data['expires_in']
#         refresh_token = json_data['refresh_token']
#
#         queue = configure_beanstalk()
#         job_id = send_token(queue, json.dumps(json_data))
#         return make_response('#{0}'.format(job_id), status.HTTP_200_OK)
#     except KeyError as ke:
#         return make_response('', status.HTTP_400_BAD_REQUEST)
#

# okay, if we are the main thing then start
# listening for requests!
if __name__ == '__main__':
    APP.run(host='0.0.0.0', port=8081) # gunicorn!!
