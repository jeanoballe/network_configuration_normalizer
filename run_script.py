import datetime
import json
import csv
from device_models import DEVICE_MODEL
from device_factory import create_device
from getpass import getpass


def read_csv_file(file_path: str):
    data = []
    with open(file_path, 'r') as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            data.append(dict(row))
    return data

def remove_duplicates_by_key(data, key):
    unique_data = []
    seen = set()
    for item in data:
        if item[key] not in seen:
            seen.add(item[key])
            unique_data.append(item)
    return unique_data


def config_interface_template(interface_name: str, device_model_id: str):
    if device_model_id == "1":
        config = [
            f"interface {interface_name}",
            "shutdown",
            "no switchport mode access",
            "no switchport mode hybrid",
            "no switchport trunk native vlan",
            "no switchport trunk allowed vlan",
            "no switchport hybrid allowed vlan",
            "no switchport hybrid native vlan",
            "description LIBRE",
            "switchport mode trunk",
            "switchport trunk native vlan 4000",
            "switchport trunk allowed vlan 4000",
            "no spanning-tree",
            "loop-protect",
            "loop-protect action shutdown log trap",
            "qos storm broadcast 10 mbps",
            "qos storm unknown 10 mbps",
            "exit"
        ]
    else:
        config = [
            f"interface {interface_name}",
            "shutdown",
            "no switchport mode access",
            "no switchport mode hybrid",
            "no switchport trunk native vlan",
            "no switchport trunk allowed vlan",
            "no switchport hybrid allowed vlan",
            "no switchport hybrid native vlan",
            "description LIBRE",
            "switchport mode trunk",
            "switchport trunk native vlan 4000",
            "switchport trunk allowed vlan 4000",
            "no spanning-tree",
            "loop-protect",
            "loop-protect action shutdown log",
            "qos storm broadcast 10 mbps",
            "qos storm unknown 10 mbps",
            "exit"
        ]

    return config


file_path = 'input_information/data.csv'
print(f"- Leyendo informacion de archivo: {file_path}")
csv_data = read_csv_file(file_path)
print(f"- La siguiente informacion fue leida del archivo: {file_path}")
for iface in csv_data:
    print(f"\t - IP Mgmt: {iface['mgmt_ip']} | Device: {DEVICE_MODEL[iface['device_model_id']]['model']} | Port: GigabitEthernet 1/{iface['port_number']}")
unique_data = remove_duplicates_by_key(csv_data, 'mgmt_ip')
print(f"- Se procedera a ejecutar la lectura de configuracion de los equipo informados en el archivo. Para eso necesitamos que ingrese sus credenciales:")
user = input('Ingrese su usuario: ')
psw = getpass()
credentials = {
    'username': user,
    'password': psw
}

config_change_ports = []
print(f"- Tomando informacion de los dispositivos...")
for data in unique_data:
    print("#" * 30)

    node = {
        "device_model_id": data['device_model_id'],
        "device_model": DEVICE_MODEL[data['device_model_id']],
        "mgmt_ip": data['mgmt_ip'],
        "credentials": credentials
    }
    sw = create_device(**node)
    timestamp = ('{:%d-%m-%Y_%H_%M_%S}'.format(datetime.datetime.now()))
    result = sw.retrieve_information()
    json_object = json.dumps(result, indent=4)
    file_name = "_".join([result['hostname'], timestamp])

    with open("backup_configuration/" + file_name + ".json", "w") as outfile:
        outfile.write(json_object)

    with open("backup_configuration/" + file_name + ".conf", "w") as outfile:
        outfile.write(result['configuration']['cnfg_txt'])

    node['interfaces'] = []
    for interfc in csv_data:
        if interfc['mgmt_ip'] == data['mgmt_ip']:
            node['hostname'] = result['hostname']
            for if_status in result['interface_status']['interfaces']:
                csv_if_name = f"GigabitEthernet 1/{interfc['port_number']}"
                if if_status['interface_full_name'] == csv_if_name:
                    node['interfaces'].append(
                        dict(
                            interface_full_name=if_status['interface_full_name'],
                            link_state=if_status['link_state']
                        )
                    )

    config_change_ports.append(node)

print(f"- Estado actual de los puertos:")
for if_cnfig in config_change_ports:
    for port in if_cnfig['interfaces']:
        print(f"\t -IP Mgmt: {if_cnfig['mgmt_ip']} | Hostname: {if_cnfig['hostname']} | Puerto {port['interface_full_name']} | Estado del puerto: {port['link_state']}")
print(f"- Normalizando configuracion de los puertos..")
for if_cnfig in config_change_ports:
    print("#" * 30)
    node = {
        "device_model_id": if_cnfig['device_model_id'],
        "device_model":DEVICE_MODEL[if_cnfig['device_model_id']],
        "mgmt_ip": if_cnfig['mgmt_ip'],
        "credentials": credentials
    }
    sw = create_device(**node)
    for port in if_cnfig['interfaces']:
        print("/" * 30)
        print(f"Aplicando configuracion sobre interfaz {port['interface_full_name']}")
        config = config_interface_template(interface_name=port['interface_full_name'], device_model_id=if_cnfig['device_model_id'])
        sw.deploy_configuration(config)
