from flask import Flask, jsonify
from kavenegar import KavenegarAPI

app = Flask(__name__)


@app.route('/')
def main_page():
    """This is the main page of the site
    """
    return 'Hello Sasan!!!!'


@app.route('/v1/getsms')
def process():
    # import pdb
    # pdb.set_trace()
    print("we are in process")
    data = {'message': 'processed'}
    return jsonify(data), 200


def send_sms(receptor, message):
    """This function will get a MSIDN and a message, then
    uses KaveNegar to send sms.
    """
    api = KavenegarAPI('76674C413530365252777A584957586E6B365971714E685A726C4A7676544E624568447A67684C6C5455303D')
    params = {'sender': '1000596446', 'receptor': receptor, 'message': message}
    response = api.sms_send(params)
    print(f"message *{message}* sent. status code is {response.status_code}")


def check_serial():
    pass


if __name__ == '__main__':
    app.run(port=22, debug=True)
