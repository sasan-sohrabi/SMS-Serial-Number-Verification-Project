from kavenegar import *

api = KavenegarAPI('*')
params = {'sender': '*', 'receptor': '*', 'message': 'صرفا جهت تست'}
response = api.sms_send(params)
