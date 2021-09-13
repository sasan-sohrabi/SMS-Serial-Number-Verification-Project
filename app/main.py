import re
import sqlite3
from flask import Flask, jsonify, request, Response, redirect, url_for, request, session, abort
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user
import pandas as pd
from kavenegar import KavenegarAPI
import config

app = Flask(__name__)

# flask-login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

app.config.update(
    SECRET_KEY=config.SECRET_KEY
)


# silly user model
class User(UserMixin):

    def __init__(self, id):
        self.id = id

    def __repr__(self):
        return "%d" % self.id


# create some users with ids 1 to 20
user = User(0)


# some protected url
@app.route('/')
@login_required
def home():
    return Response("Hello World!")


# somewhere to login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if password == config.PASSWORD and username == config.USERNAME:
            login_user(user)
            return redirect('/')
        else:
            return abort(401)
    else:
        return Response('''
        <form action="" method="post">
            <p><input type=text name=username>
            <p><input type=password name=password>
            <p><input type=submit value=Login>
        </form>
        ''')


# somewhere to logout
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return Response('<p>Logged out</p>')


# handle login failed
@app.errorhandler(401)
def page_not_found(error):
    return Response('<p>Login failed</p>')


# callback to reload the user object
@login_manager.user_loader
def load_user(userid):
    return User(userid)


# For checking that system is working or not.
@app.route('/v1/ok')
def health_check():
    check = {'message': 'ok'}
    return jsonify(check), 200


def send_sms(receptor: str, message: str) -> None:
    """ This function will get a MSIDN and a message, then
    uses KaveNegar to send sms.
    """
    api = KavenegarAPI(config.API_KEY)
    params = {'sender': '10000400600600', 'receptor': receptor, 'message': message}
    response = api.sms_send(params)
    print(f"message *{message}* sent. status code is {response.status_code}")


def normalize_string(input_str: str, fixed_size=30):
    from_persian_char = '۱۲۳۴۵۶۷۸۹۰'
    from_arabic_char = '٠١٢٣٤٥٦٧٨٩'
    to_char = '1234567890'

    for i in range(len(to_char)):
        input_str = input_str.replace(from_persian_char[i], to_char[i])
        input_str = input_str.replace(from_arabic_char[i], to_char[i])
    input_str = input_str.upper()
    input_str = re.sub(r'\W+', '', input_str)  # Remove any non alphanumeric character.

    all_alpha = ''
    all_digit = ''
    for c in input_str:
        if c.isalpha():
            all_alpha += c
        if c.isdigit():
            all_digit += c

    missing_zeros = fixed_size - len(all_alpha) - len(all_digit)

    input_str = all_alpha + '0' * missing_zeros + all_digit
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


def check_serial(serial: str):
    """ This function will get one serial number and return appropriate
    answer to that, after consulting the db.
    """
    sqlite_connection = sqlite3.connect(config.DATABASE_FILE_PATH)
    cursor = sqlite_connection.cursor()

    query = f"SELECT * FROM invalids WHERE faulty == '{serial}'"
    results = cursor.execute(query)
    if len(results.fetchall()) == 1:
        return 'This serial is among failed ones'

    query = f"SELECT * FROM serials WHERE start_serial < '{serial}' and end_serial > '{serial}'"
    results = cursor.execute(query)
    if len(results.fetchall()) == 1:
        return 'I found your serial'

    return 'It was not in the db'


@app.route('/v1/process', methods=['POST'])
def process():
    """This is callback from KaveNegar, will get sender and message and will
    check if it is valid. Then answers back.
    """

    # For Debugging
    # import pdb
    # pdb.set_trace()

    # For receive data from sms
    data = request.form
    sender = data['from']
    message = normalize_string(data['message'])
    print(f"receive {message} from {sender}")

    answer = check_serial(message)
    send_sms(sender, answer)

    ret = {'message': 'processed'}
    return jsonify(ret), 200


if __name__ == '__main__':
    import_database_from_excel('Data/data.xlsx')
    app.run(host="0.0.0.0", port=5000)
