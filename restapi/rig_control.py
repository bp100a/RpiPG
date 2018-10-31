import datetime
from flask import Flask, jsonify
from flask import request, make_response
from flask_api import status
from flask_cors import CORS, cross_origin
from flask_swagger import swagger
from waitress import serve
import beanstalkc as beanstalk

app = Flask(__name__)
app.debug = True
app.config['SECRET_KEY'] = 'photogrammetry'
CORS(app, resources=r'/*')

__version__ = '0.0.1' #our version string PEP 440

# define the beanstalk tube names (queues) we will use
CANCEL_QUEUE = 'cancel' # special, just to cancel anything
TASK_QUEUE = 'work' # JSON describes actual work to perform
STATUS_QUEUE = 'status' # sent back with status messages, in JSON


def configure_beanstalk():
    """set up our beanstalk queue for inter-process
    messages"""
    queue = beanstalk.Connection(host='localhost', port=14711)
    return queue


def get_status(queue: beanstalk.Connection) -> str:
    """return the status of the rig"""
    queue.watch(STATUS_QUEUE)
    job = queue.reserve(timeout=0) # don't wait
    if job is None:
        return None

    # we have status, let's get it and pull the
    # job out of the queue
    status_json = job.body
    job.delete()
    return status_json


def send_cancel(queue: beanstalk.Connection) -> None:
    """send a cancel to the rig software to stop whatever is
    happening"""
    queue.watch(CANCEL_QUEUE)
    queue.put('STOP!') # anything will do


def send_home_command(queue: beanstalk.Connection) -> None:
    """send a home command to home the rig"""

    clear_status_queue(queue)   # so we see what home command triggers

    queue.watch(TASK_QUEUE)
    task_body = jsonify({'task': 'home'})
    queue.put(task_body)


def send_scan_command(queue: beanstalk.Connection, declination_steps: int, rotation_steps: int) -> None:
    """this is it - time to scan. send the # of steps for each axis
    and return"""
    queue.watch(TASK_QUEUE)
    task_body = jsonify({'task': 'scan'}, {'steps': {'declination': declination_steps, 'rotation': rotation_steps}})
    queue.put(task_body)


def clear_status_queue(queue: beanstalk.CommandFailed):
    """empty the status queue of any messages"""
    queue.watch(STATUS_QUEUE)
    while True:
        job = queue.reserve(timeout=0)
        if job is None:
            return
        job.delete()


@app.route("/spec/swagger.json")
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
    swag = swagger(app)
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


@app.route("/config")
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
    dtNow = datetime.datetime.now()
    htmlbody += "<h1>PhotoGram Hello World from Gunicorn & Nginx!</h1> last called {}".format(dtNow)
    htmlbody += "<img src=\"/static/gunicorn_small.png\"/>"

    return htmlbody


@app.route("/status", methods=['GET'])
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
            return make_response(None, status.HTTP_204_NO_CONTENT)
        else:
            return make_response(status_json, status.HTTP_200_OK)
    except Exception as e:
        return make_response("something really bad -> {0}".format(e.__str__()), status.HTTP_500_INTERNAL_SERVER_ERROR)

    return make_response("should never get here", status.HTTP_500_INTERNAL_SERVER_ERROR)

@app.route("/home", methods=['POST'])
@cross_origin(origins='*')
def home():
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
    send_home_command(configure_beanstalk())
    return make_response(jsonify({'msg': 'everything is okay'}), status.HTTP_200_OK)


@app.route("/scan", methods=['POST'])
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
        return make_response(jsonify({'msg': 'No JSON'}), status.HTTP_400_BAD_REQUEST)

    try:
        declination_steps = request.json['declination_steps']
        rotation_steps = request.json['rotation_steps']
    except KeyError as e:
        return make_response(jsonify({'msg': 'No JSON'}), status.HTTP_400_BAD_REQUEST)

    MAX_PICTURES = 200
    # Calculate total picture count, cannot exceed 'MAX_PICTURES'
    total_picture_count = declination_steps * rotation_steps
    if total_picture_count > MAX_PICTURES:
        return make_response(jsonify({'msg': 'exceeded max pictures of {0}'.format(MAX_PICTURES)}), status.HTTP_400_BAD_REQUEST)

    try:
        # okay, kick off the scanning
        queue = configure_beanstalk()
        send_scan_command(queue, declination_steps, rotation_steps)
    except Exception as e:
        return make_response(jsonify({'msg': 'exception = {0}'.format(e.__str__())}), status.HTTP_500_INTERNAL_SERVER_ERROR)

    return make_response(jsonify({'msg': 'Not Implemented'}), status.HTTP_500_INTERNAL_SERVER_ERROR)


# okay, if we are the main thing then start
# listening for requests!
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081)
    # serve(app, listen='*:8081')
