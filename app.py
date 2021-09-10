import re
import sqlite3
from flask import Flask, jsonify, request
import pandas as pd
from kavenegar import KavenegarAPI
import config

app = Flask(__name__)


# For checking that system is working or not.
@app.route('/v1/ok')
def health_check():
    check = {'message': 'ok'}
    return jsonify(check), 200


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
    message = normalize_string(data['message'])
    print(f"receive {message} from {sender}")

    ret = {'message': 'processed'}
    return jsonify(ret), 200


def send_sms(receptor: str, message: str) -> None:
    """ This function will get a MSIDN and a message, then
    uses KaveNegar to send sms.
    """
    api = KavenegarAPI(config.API_KEY)
    params = {'sender': '10000400600600', 'receptor': receptor, 'message': message}
    response = api.sms_send(params)
    print(f"message *{message}* sent. status code is {response.status_code}")


def normalize_string(input_str: str):
    from_char = '۱۲۳۴۵۶۷۸۹۰'
    to_char = '1234567890'
    for i in range(len(from_char)):
        input_str = input_str.replace(from_char[i], to_char[i])
    input_str = input_str.upper()
    input_str = re.sub(r'\W+', '', input_str)  # Remove any non alphanumeric character.
    return input_str


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
    # row 	reference_number 	description	start_serial 	end_serial 	date
    df_serials = pd.read_excel(filepath, 0)
    df_serials[df_serials.columns[3]] = df_serials[df_serials.columns[3]].apply(normalize_string)
    df_serials[df_serials.columns[4]] = df_serials[df_serials.columns[4]].apply(normalize_string)
    df_serials.to_sql(name='serials', con=sqlite_connection, if_exists='replace', index=True)

    # Remove the invalids table if exists, then create new one
    cursor.execute('Drop TABLE IF EXISTS invalids')
    cursor.execute("""CREATE TABLE IF NOT EXISTS invalids (
                    id INTEGER PRIMARY KEY,
                    faulty TEXT);""")
    # df_invalids contains lookup data in the form of
    # Faulty
    df_invalids = pd.read_excel(filepath, 1)  # Sheet one contains failed serial numbers. Only one column
    df_invalids['faulty'] = df_invalids['faulty'].apply(normalize_string)
    df_invalids.to_sql(name='invalids', con=sqlite_connection, if_exists='replace', index=True)

    sqlite_connection.close()


def check_serial():
    pass


if __name__ == '__main__':
    # For Test
    # send_sms('09125915669', 'Hi Sasan')
    # app.run(host="0.0.0.0", port=5000)
    import_database_from_excel('Data/data.xlsx')
