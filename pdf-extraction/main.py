import base64
import gspread
import json
import re
from google.cloud import vision
from google.cloud import storage
from google.protobuf import json_format
from google.oauth2.service_account import Credentials
import os

SPREADSHEET_ID = "1zqc0BDV3l5wq7tEzJZF2GhFZUc4e213gaYcT3Zb3OyQ"
SPREADSHEET_TAB = 'Projeção'

SHEETS_API_SCOPE = ['https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/drive']

storage_client = storage.Client()
vision_client = vision.ImageAnnotatorClient()


# def extract_from_pdf(event, context):
def main_entry(request):
    # data = base64.b64decode(event['data']).decode('utf-8')
    # payload = json.loads(data)
    # gcs_source_uri=payload['bucket_source_file']
    gcs_source_uri='gs://sfinbills/RFATURA_DIR_FR2FAT16__95_0000_235202004652902.PDF'
    # gcs_destination_uri=payload['bucket_destination']
    gcs_destination_uri='gs://sfinbills/output'

    # AUTH
    creds_key_json = get_auth_key()

    # VISION API
    # Supported mime_types are: 'application/pdf' and 'image/tiff'
    send_bill_file_and_set_output(gcs_source_uri, gcs_destination_uri)

    # Once the request has completed and the output has been
    # written to GCS, we can list all the output files.
    bill_content = get_bill_content(gcs_destination_uri)

    # GSPREAD
    main_worksheet = get_spreadsheet(creds_key_json)
    for cell in main_worksheet.range(INIT_ROW, STATUS_COLUMN, main_worksheet.row_count, HASH_FILE_NAMES_COLUMN):
        print(cell)

def get_spreadsheet(creds_key_json):
    credentials = Credentials.from_service_account_info(
        creds_key_json,
        scopes=SHEETS_API_SCOPE
    )
    gc = gspread.authorize(credentials)
    main_worksheet = gc.open_by_key(SPREADSHEET_ID).worksheet(SPREADSHEET_TAB)
    return main_worksheet

def get_bill_content(gcs_destination_uri):
    # Once the request has completed and the output has been
    # written to GCS, we can list all the output files.
    match = re.match(r'gs://([^/]+)/(.+)', gcs_destination_uri)
    bucket_name = match.group(1)
    prefix = match.group(2)

    bucket = storage_client.get_bucket(bucket_name)
    # List objects with the given prefix.
    blob_list = list(bucket.list_blobs(prefix=prefix))
    print('Output files:')
    for blob in blob_list:
        print(blob.name)

    # Process the first output file from GCS.
    # Since we specified batch_size=2, the first response contains
    # the first two pages of the input file.
    output = blob_list[0]

    json_string = output.download_as_string()
    response = json_format.Parse(
        json_string, vision.types.AnnotateFileResponse())

    # The actual response for the first page of the input file.
    first_page_response = response.responses[0]
    annotation = first_page_response.full_text_annotation

    # Here we print the full text from the first page.
    # The response contains more information:
    # annotation/pages/blocks/paragraphs/words/symbols
    # including confidence scores and bounding boxes
    print(u'Full text:\n{}'.format(
        annotation.text))
    return annotation.text

def send_bill_file_and_set_output(gcs_source_uri, gcs_destination_uri):
    # Supported mime_types are: 'application/pdf' and 'image/tiff'
    mime_type = 'application/pdf'
    # How many pages should be grouped into each json output file.
    batch_size = 2

    feature = vision.types.Feature(
        type=vision.enums.Feature.Type.DOCUMENT_TEXT_DETECTION)

    gcs_source = vision.types.GcsSource(uri=gcs_source_uri)
    input_config = vision.types.InputConfig(
        gcs_source=gcs_source, mime_type=mime_type)

    gcs_destination = vision.types.GcsDestination(uri=gcs_destination_uri)
    output_config = vision.types.OutputConfig(
        gcs_destination=gcs_destination, batch_size=batch_size)

    async_request = vision.types.AsyncAnnotateFileRequest(
        features=[feature], input_config=input_config,
        output_config=output_config)

    operation = vision_client.async_batch_annotate_files(
        requests=[async_request])

    print('Waiting for the operation to finish...')
    operation.result(timeout=420)
    # TODO: generate current MM/YYYY


def get_auth_key():
    # TODO: add as env var
    sa_name = 'SmartFinance-Bills-Beta-eb6d6507173d.json'
    sa_bucket = 'sfinbills'
    bucket = storage_client.get_bucket(sa_bucket)
    # List objects with the given prefix.
    # blob_list = list(bucket.list_blobs())
    for index, blob in enumerate(bucket.list_blobs()):
        print(blob.name)
        if blob.name == sa_name:
            # output = blob_list[index]
            creds = blob.download_as_string()
            print('creds {}'.format(creds))
            json_acct_info = json.loads(creds)
    return json_acct_info

    # bucket = storage_client.get_bucket('sfinbills')
    # # List objects with the given prefix.
    # blob_list = list(bucket.list_blobs())
    # print('Output files:')
    # for index, blob in enumerate(blob_list):
    #     print(blob.name)
    #     if blob.name == '':
    #         output = blob_list[index]
    #         creds = output.download_as_string()

    #         json_acct_info = json.loads(creds)
    #         credentials = Credentials.from_service_account_info(
    #             json_acct_info,
    #             scopes=SHEETS_API_SCOPE
    #         )
    
    #         gc = gspread.authorize(credentials)
    #         main_worksheet = gc.open_by_key(SPREADSHEET_ID).worksheet(SPREADSHEET_TAB)
    #         print(main_worksheet)
    #         break