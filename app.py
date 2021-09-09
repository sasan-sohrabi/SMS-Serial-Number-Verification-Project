import requests
from flask import Flask, jsonify, request
from pandas import read_excel
from kavenegar import KavenegarAPI
from config import *

app = Flask(__name__)


@app.route('/')
def main_page():
    """This is the main page of the site
    """
    return 'Hello Sasan!!!!'


@app.route('/v1/process', methods=['POST'])
def process():
    """This is callback from KaveNegar, will get sender and message and will
    check if it is valid. Then answers back.
    """

    # For Debugging
    import pdb
    # pdb.set_trace()

    # For receive data from sms
    data = request.form
    sender = data['from']
    message = data['message']
    print(f"receive {message} from {sender}")

    ret = {'message': 'processed'}
    return jsonify(ret), 200


def send_sms(receptor, message):
    """ This function will get a MSIDN and a message, then
    uses KaveNegar to send sms.
    """
    api = KavenegarAPI(API_KEY)
    params = {'sender': '10000400600600', 'receptor': receptor, 'message': message}
    response = api.sms_send(params)
    print(f"message *{message}* sent. status code is {response.status_code}")


def import_database_from_excel(filepath):
    """ Get an excel file name and imports lookup data(data and failures) from it"""
    # df contains lookup data in the form of
    # Row 	Reference Number 	Description	Start Serial 	End Serial 	Date
    df = read_excel(filepath, 0)

    df = read_excel(filepath, 1)  # Sheet one contains failed serial numbers. Only one column


def check_serial():
    pass


if __name__ == '__main__':
    # For Test
    # send_sms('09125915669', 'Hi Sasan')
    app.run(host="0.0.0.0", port=5000)
