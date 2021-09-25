# Import relevant library for sms project
import os
import re
import time
from textwrap import dedent

from flask import Flask, jsonify, request, Response, redirect, url_for, request, session, abort, flash, render_template
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user
import pandas as pd
from werkzeug.utils import secure_filename
from kavenegar import KavenegarAPI
import config
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import create_engine
import psycopg2

app = Flask(__name__)

limiter = Limiter(
    app,
    key_func=get_remote_address,
)

UPLOAD_FOLDER = config.UPLOAD_FOLDER
ALLOWED_EXTENSIONS = config.ALLOWED_EXTENSIONS
CALL_BACK_TOKEN = config.CALL_BACK_TOKEN
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# flask-login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


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
@app.route('/', methods=['GET', 'POST'])
@login_required
def home():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            try:
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                import_database_from_excel(file_path)
                flash('Import excel file to database successfully!', 'success')
            except Exception as e:
                flash(f'Wrong to insert data from excel to database!-{e}', 'danger')
            return redirect('/')

    # CONNECTION to DATABASE
    conn_string = f"postgresql://{config.POST_HOST_USERNAME}:{config.POST_HOST_PASSWORD}@{config.POST_HOST}/{config.POST_HOST_DB_NAME}"
    print("Successfully Connected to Postgresql")
    pg_conn = psycopg2.connect(conn_string)
    cur = pg_conn.cursor()

    # Get last 5000 smss
    cur.execute('SELECT * FROM processed_sms ORDER BY date DESC LIMIT 5000;')
    all_smss = cur.fetchall()
    smss = []
    for sms in all_smss:
        status, sender, message, answer, date = sms
        smss.append({'status': status, 'sender': sender, 'message': message, 'answer': answer, 'date': date})

    # Collect some stats for the GUI
    cur.execute("SELECT count(*) FROM processed_sms WHERE status = 'OK'")
    num_ok = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM processed_sms WHERE status = 'FAILURE'")
    num_failure = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM processed_sms WHERE status = 'DOUBLE'")
    num_double = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM processed_sms WHERE status = 'NOT-FOUND'")
    num_notfound = cur.fetchone()[0]

    cur.close()
    return render_template('index.html', data={'smss': smss, 'ok': num_ok, 'failure': num_failure, 'double': num_double,
                                               'notfound': num_notfound})


@app.route('/check_one_serial', methods=["POST"])
@login_required
def check_one_serial():
    serial_to_check = request.form['serial']
    status, answer = check_serial(normalize_string(serial_to_check))
    flash(f'{status} - {answer}', 'info')
    return redirect('/')


# somewhere to login
@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect('/')
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if password == config.PASSWORD and username == config.USERNAME:
            login_user(user)
            return redirect('/')
        else:
            return abort(401)
    else:
        html_str = Response('''
        <form action="" method="post">
            <p><input type=text name=username>
            <p><input type=password name=password>
            <p><input type=submit value=Login>
        </form>
        ''')
        return render_template('login.html')


# somewhere to logout
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash('Logged out', 'success')
    return redirect('/login')


# handle login failed
@app.errorhandler(401)
def unauthorized(error):
    flash('Login Problem', 'danger')
    return redirect('/login')


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

    # CONNECTION to DATABASE
    conn_string = f"postgresql://{config.POST_HOST_USERNAME}:{config.POST_HOST_PASSWORD}@{config.POST_HOST}/{config.POST_HOST_DB_NAME}"
    db = create_engine(conn_string)
    conn = db.connect()
    print("Successfully Connected to Postgresql")

    pg_conn = psycopg2.connect(conn_string)
    cur = pg_conn.cursor()

    # Remove the serials table if exists, then create new one
    try:
        cur.execute('Drop TABLE IF EXISTS serials')
        cur.execute("""CREATE TABLE serials (
                        id INTEGER PRIMARY KEY,
                        ref VARCHAR(100),
                        description VARCHAR(200),
                        start_serial CHAR(30),
                        end_serial CHAR(30),
                        date TIMESTAMP);""")
        pg_conn.commit()
    except:
        flash('Problem dropping and creating new table in database', 'danger')

    # df_serials contains lookup data in the form of
    # row | reference_number | description | start_serial | end_serial | date
    try:
        df_serials = pd.read_excel(filepath, 0)
        df_serials[df_serials.columns[3]] = df_serials[df_serials.columns[3]].apply(normalize_string)
        df_serials[df_serials.columns[4]] = df_serials[df_serials.columns[4]].apply(normalize_string)
        df_serials.to_sql(name='serials', con=conn, if_exists='replace', index=True)
    except:
        flash('Problem to insert data to database', 'danger')

    # Remove the invalids table if exists, then create new one
    try:
        cur.execute('Drop TABLE IF EXISTS invalids')
        cur.execute("""CREATE TABLE  invalids (
                        id INTEGER PRIMARY KEY,
                        faulty CHAR(30));""")
        pg_conn.commit()
    except:
        flash('Problem dropping and creating new table in database', 'danger')

    # df_invalids contains lookup data in the form of
    # Faulty
    try:
        df_invalids = pd.read_excel(filepath, 1)  # Sheet one contains failed serial numbers. Only one column
        df_invalids['faulty'] = df_invalids['faulty'].apply(normalize_string)
        df_invalids.to_sql(name='invalids', con=conn, if_exists='replace', index=True)
    except:
        flash('Problem dropping and creating new table in database', 'danger')

    # close connection
    cur.close()
    conn.close()


def check_serial(serial: str):
    """ This function will get one serial number and return appropriate
    answer to that, after consulting the db.
    """

    original_serial = serial
    serial = normalize_string(serial)

    print(
        f"postgresql://{config.POST_HOST_USERNAME}:{config.POST_HOST_PASSWORD}@{config.POST_HOST}/{config.POST_HOST_DB_NAME}")

    # CONNECTION to DATABASE
    conn_string = f"postgresql://{config.POST_HOST_USERNAME}:{config.POST_HOST_PASSWORD}@{config.POST_HOST}/{config.POST_HOST_DB_NAME}"
    db = create_engine(conn_string)
    conn = db.connect()
    print("Successfully Connected to Postgresql")

    pg_conn = psycopg2.connect(conn_string)
    cur = pg_conn.cursor()

    cur.execute("SELECT * FROM invalids WHERE faulty = %s;", (normalize_string(serial),))
    result_faulty = cur.fetchall()
    if len(result_faulty) > 0:
        answer = dedent(f"""\
            {original_serial}
            این شماره هولوگرام یافت نشد. لطفا دوباره سعی کنید  و یا با واحد پشتیبانی تماس حاصل فرمایید.
            ساختار صحیح شماره هولوگرام بصورت دو حرف انگلیسی و 7 یا 8 رقم در دنباله آن می باشد. مثال:
            FA1234567
            شماره تماس با بخش پشتیبانی فروش شرکت التک:
            021-22038385""")

        return 'FAILURE', answer

    cur.execute("SELECT * FROM serials WHERE start_serial <= %s and end_serial >= %s;",
                (normalize_string(serial), normalize_string(serial)))
    result_serial = cur.fetchall()

    if len(result_serial) > 1:
        answer = dedent(f"""\
            {original_serial}
            این شماره هولوگرام مورد تایید است.
            برای اطلاعات بیشتر از نوع محصول با بخش پشتیبانی فروش شرکت التک تماس حاصل فرمایید:
            021-22038385""")
        return 'DOUBLE', answer

    elif len(result_serial) == 1:
        ret = result_serial[0]
        desc = ret[3]
        ref_number = ret[2]
        date = ret[6].date()
        answer = dedent(f"""\
            {original_serial}
            {ref_number}
            {desc}
            Hologram date: {date}
            Genuine product of Schneider Electric
            شماره تماس با بخش پشتیبانی فروش شرکت التک:
            021-22038385""")
        return 'OK', answer

    cur.close()
    conn.close()

    answer = dedent(f"""\
        {original_serial}
        این شماره هولوگرام یافت نشد. لطفا دوباره سعی کنید  و یا با واحد پشتیبانی تماس حاصل فرمایید.
        ساختار صحیح شماره هولوگرام بصورت دو حرف انگلیسی و 7 یا 8 رقم در دنباله آن می باشد. مثال:
        FA1234567
        شماره تماس با بخش پشتیبانی فروش شرکت التک:
        021-22038385""")

    return 'NOT-FOUND', answer

    # close connection


@app.route(f'/v1/process', methods=['POST'])
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

    status, answer = check_serial(message)

    # CONNECTION to DATABASE
    conn_string = f"postgresql://{config.POST_HOST_USERNAME}:{config.POST_HOST_PASSWORD}@{config.POST_HOST}/{config.POST_HOST_DB_NAME}"
    print("Successfully Connected to Postgresql")

    pg_conn = psycopg2.connect(conn_string)
    pg_conn.autocommit = True
    cur = pg_conn.cursor()
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    cur.execute("INSERT INTO processed_sms (status, sender, message, answer,date) VALUES (%s, %s, %s, %s, %s)",
                (status, sender, message, answer, now))

    pg_conn.commit()
    cur.close()

    send_sms(sender, answer)

    ret = {'message': 'processed'}
    return jsonify(ret), 200


# If there is not valid url return 404 page (not found page)
@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404


if __name__ == '__main__':
    app.run(debug=False)
