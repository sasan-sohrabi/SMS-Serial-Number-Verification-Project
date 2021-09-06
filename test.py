from kavenegar import *

api = KavenegarAPI('76674C413530365252777A584957586E6B365971714E685A726C4A7676544E624568447A67684C6C5455303D')
params = {'sender': '1000596446', 'receptor': '09195145937', 'message': '.وب سرویس پیام کوتاه کاوه نگار'}
response = api.sms_send(params)
