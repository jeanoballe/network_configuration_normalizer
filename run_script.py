import datetime
import json
from device_models import DEVICE_MODEL
from device_factory import create_device
from getpass import getpass


user = input('Enter your username: ')
psw = getpass()
credentials = {
    'username': user,
    'password': psw
}
device_model_id = 1
node = {
    "device_model_id": device_model_id,
    "device_model": DEVICE_MODEL[device_model_id],
    "mgmt_ip": "10.106.37.2",
    "credentials": credentials
}
sw = create_device(**node)
timestamp = ('{:%d-%m-%Y_%H:%M:%S}'.format(datetime.datetime.now()))
result = sw.retrieve_information()
json_object = json.dumps(result, indent=4)
file_name = "_".join([result['hostname'], timestamp])

with open("backup_configuration/" + file_name + ".json", "w") as outfile:
    outfile.write(json_object)

with open("backup_configuration/" + file_name + ".conf", "w") as outfile:
    outfile.write(result['configuration']['cnfg_txt'])
