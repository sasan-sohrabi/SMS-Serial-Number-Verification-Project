import sqlite3
from flask import Flask, jsonify, request
import pandas as pd
from kavenegar import KavenegarAPI
import config

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
    api = KavenegarAPI(config.API_KEY)
    params = {'sender': '10000400600600', 'receptor': receptor, 'message': message}
    response = api.sms_send(params)
    print(f"message *{message}* sent. status code is {response.status_code}")


def import_database_from_excel(filepath):
    """ Get an excel file name and imports lookup data(data and failures) from it to
     sqlite database.
     """

    # Connect to database
    sqlite_connection = sqlite3.connect(config.DATABASE_FILE_PATH)
    cursor = sqlite_connection.cursor()
    print("Successfully Connected to SQLite")

    # Remove the serials table if exists, then create new one
    cursor.execute('Drop TABLE IF EXISTS serials')
    cursor.execute("""CREATE TABLE IF NOT EXISTS serials (
                    id INTEGER PRIMARY KEY,
                    ref TEXT,
                    desc TEXT,
                    start_serial TEXT,
                    end_serial TEXT,
                    date DATE);""")
    # df_serials contains lookup data in the form of
    # Row 	Reference Number 	Description	Start Serial 	End Serial 	Date
    df_serials = pd.read_excel(filepath, 0)
    df_serials.to_sql(name='serials', con=sqlite_connection, if_exists='replace', index=True)

    # Remove the invalids table if exists, then create new one
    cursor.execute('Drop TABLE IF EXISTS invalids')
    cursor.execute("""CREATE TABLE IF NOT EXISTS invalids (
                    id INTEGER PRIMARY KEY,
                    faulty TEXT);""")
    # df_invalids contains lookup data in the form of
    # Faulty
    df_invalids = pd.read_excel(filepath, 1)  # Sheet one contains failed serial numbers. Only one column
    df_invalids.to_sql(name='invalids', con=sqlite_connection, if_exists='replace', index=True)

    sqlite_connection.close()


def check_serial():
    pass


if __name__ == '__main__':
    # For Test
    # send_sms('09125915669', 'Hi Sasan')
    # app.run(host="0.0.0.0", port=5000)
    import_database_from_excel('Data/data.xlsx')
