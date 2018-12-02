"""Google Drive """
import json
import time
import base64
from oauth2client import client
from httplib2 import Http
from googleapiclient import discovery
from googleapiclient.http import MediaInMemoryUpload
import beanstalkc as beanstalk
from configuration import google_api  # our client id & secret


class GoogleDrive:
    """here's where we do all our Google Drive work"""

    access_token = None
    refresh_token = None
    expires_in = None
    token_type = None
    drive_client = None
    session_folder = None
    sub_folder_id = None

    def __init__(self, access_info: dict) -> None:
        """initialize our google drive object
        with the device oAuth2 info"""
        print('GoogleDrive.__init__(): access_info is type {0}'.format(type(access_info)))
        try:
            self.access_token = access_info['access_token']
            self.refresh_token = access_info['refresh_token']
            self.expires_in = access_info['expires_in']
            self.token_type = access_info['token_type']
        except KeyError as key_error:
            print("Error with access info: {0}".format(key_error.__str__()))

        credentials = client.GoogleCredentials(
            access_token=self.access_token,
            client_id=google_api.CLIENT_ID,
            client_secret=google_api.CLIENT_SECRET,
            refresh_token=self.refresh_token,
            token_expiry=self.expires_in,
            token_uri="https://www.googleapis.com/oauth2/v4/token",
            user_agent='my-user-agent/1.0')

        google_http = credentials.authorize(Http())
        google_drive = discovery.build('drive', 'v3', http=google_http)
        self.drive_client = google_drive.files()  #pylint: disable=E1101
        self.session_folder = time.strftime("%Y%m%d%H%M%S_photos", time.gmtime())

    def find_root_folder(self, root_name) -> str:
        """Search the google drive for a previously created
        root folder to write to. Return the parent id"""
        folder_list = self.drive_client.list(q="trashed=false").execute()
        for folder in folder_list['files']:
            if folder['name'] == root_name and \
               folder['mimeType'] == 'application/vnd.google-apps.folder':
                return folder['id']
        return None

    def create_root_folder(self, root_folder: str) -> bool:
        """Create the /rpipg folder to put all photos in"""
        # format time into our session folder:
        # YYYYMMDDHHmmss_photos
        try:
            root_id = self.find_root_folder(root_folder)
            if root_id is None:
                folder_kwargs = {
                    'body': {
                        'name': root_folder,
                        'mimeType': 'application/vnd.google-apps.folder'
                    },
                    'fields': 'id'
                }
                response = self.drive_client.create(**folder_kwargs).execute()
                root_id = response.get('id')  # this is the fileid

            # now create session folder
            sub_folder_kwargs = {
                'body': {
                    'name': self.session_folder,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [root_id]
                },
                'fields': 'id'
            }
            response = self.drive_client.create(**sub_folder_kwargs).execute()
            self.sub_folder_id = response.get('id')
        except client.AccessTokenCredentialsError as access_error:
            error_string = access_error.__str__()  #pylint: disable=W0612
            return False

        return True

    def write_file_bytes(self, filename: str, data: bytes) -> dict:
        """Write the file to the google drive"""

        metadata = {'title': filename,
                    'name': filename,
                    'parents': [self.sub_folder_id]
                    }
        media = MediaInMemoryUpload(body=data, mimetype='application/octet-stream')
        results = self.drive_client.\
            create(body=metadata, media_body=media).\
            execute()

        return results


GDRIVE_QUEUE = 'gdrive'


def configure_drive_queue() -> beanstalk.Connection:
    """set up our beanstalk queue for inter-process
    messages"""
    queue = beanstalk.Connection(host='localhost', port=14711)
    queue.watch(GDRIVE_QUEUE) # tube that'll contain cancel requests
    return queue


def wait_for_work(queue: beanstalk.Connection) -> str:
    """wait for work, return json"""
    while True:
        job = queue.reserve(timeout=0)
        if job:
            job_json = job.body
            job.delete()  # remove from the queue
            return json.loads(job_json)

        time.sleep(0.01)  # sleep for 10 ms to share the computer


def process_photos():
    """This is a separate process that will
    receive photo information and upload to the
    google drive"""
    print("Process spawned => process_photos()")
    queue = configure_drive_queue()
    drive = None
    while True:
        job_dict = wait_for_work(queue)
        task = job_dict['task']

        if task == 'token':
            access_info = json.loads(job_dict['value'])
            print("process_photos: access_info = {0}".format(access_info))
            drive = GoogleDrive(access_info)
            if drive:
                drive.create_root_folder('rpipg')
            continue

        if task == 'photo':
            print("process_photos: .filename={0}".format(job_dict['filename']))
            print("... type(.data)={0}".format(type(job_dict['data'])))
            decoded_bytes = base64.decodebytes(job_dict['data'].encode('utf-8'))
            drive.write_file_bytes(job_dict['filename'], decoded_bytes)

    print("process_photos(): exitting...")
    exit()
