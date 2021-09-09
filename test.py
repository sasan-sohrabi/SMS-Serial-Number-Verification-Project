from kavenegar import *

api = KavenegarAPI('39784B664E4442664D64717676696C566E763857316A556D39436D6C785251616F4C4F55367351694375513D')
params = {'sender': '10000400600600', 'receptor': '09125915669', 'message': 'صرفا جهت تست'}
response = api.sms_send(params)
