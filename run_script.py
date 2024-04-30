import logging
import datetime
import json
import csv
import sys
import time
from device_models import DEVICE_MODEL
from device_factory import create_device
from getpass import getpass
from logger import logger


def read_json_file(file_path):
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
        return data
    except FileNotFoundError:
        return None

def read_csv_file(file_path: str):
    data = []
    with open(file_path, 'r') as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            data.append(dict(row))
    return data

def create_csv_file(data, filename):
    keys = data[0].keys() if data else []
    
    with open("errors/" + filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=keys)
        
        writer.writeheader()
        writer.writerows(data)

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

device_delay = 15
file_path = 'input_information/data.csv'
logger.info(f"- Leyendo informacion de archivo: {file_path}")
csv_data = read_csv_file(file_path)
logger.info(f"- La siguiente informacion fue leida del archivo: {file_path}")
logger.info(f"- Informacion cruda: {csv_data}")
for iface in csv_data:
    logger.info(f"\t - IP Mgmt: {iface['mgmt_ip']} | Device: {DEVICE_MODEL[iface['device_model_id']]['model']} | Port: GigabitEthernet 1/{iface['port_number']}")
unique_data = remove_duplicates_by_key(csv_data, 'mgmt_ip')

logger.info(f"- Leyendo credenciales de archivo 'credentials.json'...")
credentials = read_json_file("credentials.json")

if credentials:
    if not credentials.get("username", False):
        logger.info(f"- Key 'username' faltante en archivo 'credentials.json'. Ingrese el usurio:")
        credentials['username'] = input("- Usuario: ")
    if not credentials.get("password", False):
        logger.info(f"- Key 'password' faltante en archivo 'credentials.json'. Ingrese la constraseña:")
        credentials['password'] = getpass()
else:
    logger.info(f"- Credenciales no encontradas en archivo 'credentials.json'. Ingrese sus credenciales:")
    credentials = {}
    credentials['username'] = input("- Usuario: ")
    credentials['password'] = getpass()

logger.info(f"- Se procedera a ejecutar la lectura de configuracion de los equipo informados en el archivo.")

failed_devices = []
config_change_ports = []
logger.info(f"- Tomando informacion de los dispositivos...")
for data in unique_data:
    try:
        logger.info("#" * 30)

        node = {
            "device_model_id": data['device_model_id'],
            "device_model": DEVICE_MODEL[data['device_model_id']],
            "mgmt_ip": data['mgmt_ip'],
            "credentials": credentials
        }
        sw = create_device(**node)
        timestamp = ('{:%d-%m-%Y_%H_%M_%S}'.format(datetime.datetime.now()))
        result = sw.retrieve_information()
        if result:
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
        else:
            failed_devices.append(data)
            logger.error("No hay datos disponibles del equipo.")
    except Exception as e:
        logger.error(f"Error al intentar tomar la configuracion sobre el equipo {data['mgmt_ip']}: {e}")
        failed_devices.append(data)
        continue


create_csv_file(failed_devices, "error_tomando_info.csv")

failed_config_devices = []

if config_change_ports:
    logger.info("###" * 30)
    logger.info(f"- Estado actual de los puertos:")
    for if_cnfig in config_change_ports:
        for port in if_cnfig['interfaces']:
            logger.info(f"\t -IP Mgmt: {if_cnfig['mgmt_ip']} | Hostname: {if_cnfig['hostname']} | Puerto {port['interface_full_name']} | Estado del puerto: {port['link_state']}")

    logger.info("###" * 30)
    logger.info(f"- Normalizando configuracion de los puertos..")
    for if_cnfig in config_change_ports:
        try:
            logger.info("----" * 30)
            logger.info(f"-- Equipo {if_cnfig['hostname']} - {if_cnfig['mgmt_ip']}")
            node = {
                "device_model_id": if_cnfig['device_model_id'],
                "device_model": DEVICE_MODEL[if_cnfig['device_model_id']],
                "mgmt_ip": if_cnfig['mgmt_ip'],
                "credentials": credentials
            }
            sw = create_device(**node)
            interface_config = []
            for port in if_cnfig['interfaces']:

                if port['link_state'] != "Down":
                    logger.info(f"\t - La interfaz {port['interface_full_name']} esta UP, por lo que no se cambiara la configuracion!!!!")
                else:
                    logger.info(f"\t - Creando configuracion de interfaz {port['interface_full_name']}")
                    config = config_interface_template(interface_name=port['interface_full_name'], device_model_id=if_cnfig['device_model_id'])
                    interface_config.extend(config)

            if interface_config:
                interface_config.extend(["end", "copy run start"])

                logger.info(f"-- Aplicando configuracion en equipo {if_cnfig['hostname']} - {if_cnfig['mgmt_ip']}.")

                # Aca esta el metodo que aplica la config!!:
                deploy_result = sw.deploy_configuration(interface_config)

                if deploy_result:
                    logger.info(f"-- Configuracion aplicada correctamente en el equipo {if_cnfig['hostname']} - {if_cnfig['mgmt_ip']}.")
                    logger.info("#" * 30)
                    logger.info(f"Esperando {device_delay} seg antes de aplicar la configuracion en el siguiente equipo.")
                    time.sleep(device_delay)
                else:
                    logger.error(f"No se logro aplicar la configuracion sobre el equipo {if_cnfig['hostname']} - {if_cnfig['mgmt_ip']} - Port {port['interface_full_name']}")
                    failed_config_devices.append(
                        device_model_id=if_cnfig['device_model_id'],
                        mgmt_ip=if_cnfig['mgmt_ip'],
                        port_number=port['interface_full_name'].replace("GigabitEthernet 1/", "")
                    )
            else:
                logger.info(f"-- No existe configuracion a aplicar en equipo {if_cnfig['hostname']} - {if_cnfig['mgmt_ip']}.")
        except Exception as e:
            logger.error(f"Error al intentar aplicar la configuracion sobre el equipo {if_cnfig['mgmt_ip']}: {e}")
            # failed_devices.append(
            #     dict(
            #         device_model_id=DEVICE_MODEL[if_cnfig['device_model_id']],
            #         mgmt_ip=if_cnfig['mgmt_ip']
            #     )
            # )
            continue

    create_csv_file(failed_config_devices, "errors_aplicando_config.csv")
