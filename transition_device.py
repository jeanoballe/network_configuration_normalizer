import re
from netmiko import ConnectHandler


class TransitionDevice():
    def __init__(self, device_model_id, mgmt_ip, device_model, credentials):

        self.device_model_id = device_model_id
        self.mgmt_ip = mgmt_ip
        self.device_model = device_model
        self.credentials = credentials

    def _get_loop_protect_status(self, lp_status_txt):

        lp_interface_status = []
        lp_intfc_info = {}
        interface_line = False
        lp_status = {
            'lp_global_status': {},
            'lp_interface_status': lp_interface_status
        }

        for line in lp_status_txt:
            try:
                # Global Loop-Protect Status
                lp_global_status = re.search(r'Loop Protection\s*:(.+)', line)
                if lp_global_status is not None:
                    lp_status["lp_global_status"]['loop_protection'] = (
                        lp_global_status.group(1)).lstrip()

                lp_tx_time = re.search(r'Transmission Time\s*:(.+)', line)
                if lp_tx_time is not None:
                    lp_status["lp_global_status"]['transmission_time'] = (
                        lp_tx_time.group(1)).lstrip()

                shutdown_time = re.search(r'Shutdown Time\s*:(.+)', line)
                if shutdown_time is not None:
                    lp_status["lp_global_status"]['shutdown_time'] = (
                        shutdown_time.group(1)).lstrip()

                # Interface Loop-Protect Status
                interface = re.search(r'([0-1a-zA-Z]+)\s+(1/.+)', line)
                if interface is not None:
                    lp_intfc_info["interface"] = interface.group(0)
                    interface_line = True

                if interface_line:
                    loop_protect_mode = re.search(
                        r'Loop protect mode is\s(.+)?.', line)
                    if loop_protect_mode is not None:
                        lp_intfc_info["loop_protect_mode"] = \
                            loop_protect_mode.group(1).lstrip()

                    action = re.search(r'Action is\s*(.+)?.', line)
                    if action is not None:
                        lp_intfc_info["action"] = action.group(1)

                    action = re.search(r'Actions are both of\s*(.+)?.', line)
                    if action is not None:
                        lp_intfc_info["action"] = action.group(1)

                    transmit_mode = re.search(
                        r'Transmit mode is\s*(.+)?.', line)
                    if transmit_mode is not None:
                        lp_intfc_info["transmit_mode"] = \
                            transmit_mode.group(1)

                    loop_status = re.search(r'No loop.', line)
                    if loop_status is not None:
                        lp_intfc_info["loop_status"] = "No loop"

                    loop_status = re.search(r'Loop is detected.', line)
                    if loop_status is not None:
                        lp_intfc_info["loop_status"] = "Loop is detected"

                    number_of_loops = re.search(
                        r'The number of loops is\s*(.+)?.', line)
                    if number_of_loops is not None:
                        lp_intfc_info["number_of_loops"] = \
                            number_of_loops.group(1)

                    time_of_last_loop = re.search(
                        r'Time of last loop is at\s*(.+)', line)
                    if time_of_last_loop is not None:
                        lp_intfc_info["time_of_last_loop"] = \
                            time_of_last_loop.group(1)

                    status = re.search(
                        r'Status is\s*(.+)?.', line)
                    if status is not None:
                        lp_intfc_info["status"] = status.group(1)

                    # Check if it is the last line or if it
                    # finished reading the interface DDMI
                    if ("" == line and interface_line or
                            lp_status_txt[-1] == line and interface_line):
                        interface_line = False
                        lp_interface_status.append(lp_intfc_info)
                        lp_intfc_info = {}

            except AttributeError:
                continue

        return lp_status

    def _get_commands(self):
        commands = [
            {
                "command": "show running-config",
                "msg": "Obteniendo la configuracion",
                "information": "cnfg_txt"
            },
            {
                "command": "show mac address-table",
                "msg": "Obteniendo la MAC-TABLE",
                "information": "mac_add_txt"
            },
            {
                "command": "show interface * status",
                "msg": "Obteniendo el estado de las Interfaces",
                "information": "int_status_txt"
            },
            {
                "command": "show interface * transceiver",
                "msg": "Ejecutando DDMI status",
                "information": "ddmi_status_txt"
            },
            {
                "command": "show version",
                "msg": "Ejecutando System status",
                "information": "system_status_txt"
            },
            {
                "command": "show loop-protect",
                "msg": "Ejecutando Loop Protect Status",
                "information": "lp_status_txt"
            }
        ]

        return commands

    def _get_hostname(self, cnfg_txt):
        for line in cnfg_txt:
            if "hostname " in line:
                hostname = line.split()[1]
                return hostname

    def _get_interfaces(self, cnfg_txt):

        def get_untagged_vlan(config_line):
            vlan = config_line.split()
            vlan = [int(vlan[3])]
            return vlan

        def get_tagged_vlan(config_line):
            vlans = config_line.split()
            del vlans[0:4]
            vlans = vlans[0].split(",")
            vlan_list = []
            for i in range(len(vlans)):
                if "-" in vlans[i]:
                    vlan_range = vlans[i].split('-')
                    vlan_range = (
                        list(
                            range(
                                int(vlan_range[0]),
                                int(vlan_range[1])+1))
                    )
                    vlan_list.extend(vlan_range)
                elif "none" in vlans[i]:
                    vlan_list = []
                else:
                    vlan_list.append(int(vlans[i]))
            return vlan_list

        def get_native_vlan(config_line):
            native_vlan = config_line.split()
            # eg: ['switchport', 'trunk', 'native', 'vlan', '4000']
            return int(native_vlan[4])

        interfaces = {
            'GigabitEthernet': [],
            '10GigabitEthernet': [],
        }

        interface_type = [
            'interface GigabitEthernet 1/',
            'interface 10GigabitEthernet 1/'
        ]

        interface_cngf = []
        list_int_cnfg = []

        # Creamos una lista con la informacion completa de cada interfaz
        found_intf = False
        for line in cnfg_txt:
            if (
                interface_type[0] in line or
                interface_type[1] in line
            ):
                found_intf = True

            if found_intf:
                interface_cngf.append(line)

            if found_intf and line == "!":
                found_intf = False
                list_int_cnfg.append(interface_cngf)
                interface_cngf = []

        # Tomamos la informacion necesaria de cada interfaz para
        # la creacion del diccionario

        for cnfg_interface in list_int_cnfg:
            admin_state = "enabled"
            port_channel = {
                "admin_state": "disabled",
                "mode": None,
                "key": None,
                "role": None
            }

            stp_state = "enabled"

            qos_storm_control = {
                "storm": {
                    "broadcast": {
                        "bw": None,
                        "unit": None,
                    },
                    "unknown": {
                        "bw": None,
                        "unit": None,
                    }
                }
            }

            if_descrp = None

            # Buscamos los datos basico de la interfaz
            for line_cnfg in cnfg_interface:
                if "interface GigabitEthernet 1/" in line_cnfg:
                    inf_type = line_cnfg.replace("interface ", "")
                    speed_cnfg = "auto"
                    duplex_cnfg = "auto"

                elif "interface 10GigabitEthernet 1/" in line_cnfg:
                    inf_type = line_cnfg.replace("interface ", "")
                    speed_cnfg = "10G"
                    duplex_cnfg = "full"

                # Match exacto de " shutdown"
                elif " shutdown" == line_cnfg:
                    admin_state = "disabled"

                elif "no spanning-tree" in line_cnfg:
                    stp_state = "disabled"

                elif "qos storm broadcast" in line_cnfg:
                    qscb_config = line_cnfg.split()
                    qscb_bw = int(qscb_config[3])
                    qscb_unit = qscb_config[4]
                    (qos_storm_control['storm']
                    ['broadcast']['bw']) = qscb_bw
                    (qos_storm_control['storm']
                    ['broadcast']['unit']) = qscb_unit

                elif "qos storm unknown" in line_cnfg:
                    qscu_config = line_cnfg.split()
                    qscu_bw = int(qscu_config[3])
                    qscu_unit = qscu_config[4]
                    (qos_storm_control['storm']
                        ['unknown']['bw']) = qscu_bw
                    (qos_storm_control['storm']
                        ['unknown']['unit']) = qscu_unit

                elif "description" in line_cnfg:
                    if_descrp = line_cnfg.split()
                    del if_descrp[0]

                if inf_type.startswith('GigabitEthernet'):
                    if "speed" in line_cnfg:
                        speed_cnfg = line_cnfg.split()[-1]
                    elif "duplex" in line_cnfg:
                        duplex_cnfg = line_cnfg.split()[-1]
                elif inf_type.startswith('10GigabitEthernet'):
                    if "speed auto" in line_cnfg:
                        speed_cnfg = "auto"

            # Buscamos informacion relacionada a port-channel
            if self.device_model['model'] == "LIB4424":
                for line_cnfg in cnfg_interface:
                    if "mode active" in line_cnfg:
                        port_channel['admin_state'] = "enabled"
                        port_channel['mode'] = "lacp"
                        port_channel['role'] = "active"
                        lacp_key = line_cnfg.split()
                        port_channel['key'] = int(lacp_key[2])
                    elif "mode passive" in line_cnfg:
                        port_channel['admin_state'] = "enabled"
                        port_channel['mode'] = "lacp"
                        port_channel['role'] = "passive"
                        lacp_key = line_cnfg.split()
                        port_channel['key'] = int(lacp_key[2])
                    elif "mode on" in line_cnfg:
                        port_channel['admin_state'] = "enabled"
                        port_channel['mode'] = "static"
                        lacp_key = line_cnfg.split()
                        port_channel['key'] = int(lacp_key[2])
            elif self.device_model['model'] == "S4224":
                for line_cnfg in cnfg_interface:
                    if " lacp" == line_cnfg:
                        port_channel['admin_state'] = "enabled"
                        port_channel['mode'] = "lacp"
                        port_channel['role'] = "active"
                        port_channel['key'] = 3
                    elif "lacp role passive" in line_cnfg:
                        port_channel['role'] = "passive"
                    elif "lacp key" in line_cnfg:
                        lacp_key = line_cnfg.split()
                        port_channel['key'] = int(lacp_key[2])

            # Buscamos el "switchport mode" de la interfaz
            for line_cnfg in cnfg_interface:
                if "switchport mode trunk" in line_cnfg:
                    sw_mode = "trunk"
                    break
                elif "switchport mode hybrid" in line_cnfg:
                    sw_mode = "hybrid"
                    break
            else:
                sw_mode = "access"

            # Buscamos las vlan segun el "switchport mode":
            if sw_mode == "access":
                for line_cnfg in cnfg_interface:
                    if "switchport access vlan" in line_cnfg:
                        vlans = get_untagged_vlan(line_cnfg)
                        native_vlan = vlans[0]
                        break
                else:
                    vlans = [1]
                    native_vlan = vlans[0]

            elif sw_mode == "trunk":
                # Obtener vlans en el trunk
                for line_cnfg in cnfg_interface:
                    if "switchport trunk allowed vlan" in line_cnfg:
                        vlans = get_tagged_vlan(line_cnfg)
                        break
                else:
                    vlans = ["All"]

                # Obtener native vlan
                for line_cnfg in cnfg_interface:
                    if "switchport trunk native vlan" in line_cnfg:
                        native_vlan = get_native_vlan(line_cnfg)
                        break
                else:
                    native_vlan = [1]

            elif sw_mode == "hybrid":
                # Obtener vlans en el hybrid
                for line_cnfg in cnfg_interface:
                    if "switchport hybrid allowed vlan" in line_cnfg:
                        vlans = get_tagged_vlan(line_cnfg)
                        break
                else:
                    vlans = ["All"]

                # Obtener native vlan
                for line_cnfg in cnfg_interface:
                    if "switchport hybrid native vlan" in line_cnfg:
                        native_vlan = get_native_vlan(line_cnfg)
                        break
                else:
                    native_vlan = [1]

            interface_information = {
                'full_name': inf_type,
                'switchport': {
                    "port-mode": sw_mode,
                    "vlans": {
                        "members": vlans,
                        "native": native_vlan
                    }
                },
                'description': if_descrp,
                'qos_storm_control': qos_storm_control,
                'admin_state': admin_state,
                'stp': {
                    "state": stp_state
                },
                'port_channel': port_channel,
                'speed': speed_cnfg,
                'duplex': duplex_cnfg
            }

            if inf_type.startswith("GigabitEthernet"):
                interfaces['GigabitEthernet'].append(
                    interface_information
                )
            elif inf_type.startswith("10GigabitEthernet"):
                interfaces['10GigabitEthernet'].append(
                    interface_information
                )
            interface_information = {}

        return interfaces

    def _get_configuration(self, plain_text_config):
        configuration = {}
        configuration["cnfg_txt"] = plain_text_config
        cnfg_txt = plain_text_config.split('\n')
        configuration["cnfg_json"] = {
            "cnfg_interfaces": self._get_interfaces(cnfg_txt),
            "cnfg_vlans": self._get_vlans(cnfg_txt)
        }

        return configuration

    def _get_mac_table(self, mac_add_txt):
        mac_db = []

        for line in mac_add_txt:
            try:
                mac_type, vlan_id, mac, interface = re.search(
                    r'([Dynamic]{7}|[Static]{6})\s+([0-9]+)\s+([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})\s+(Gi.+|10Gi.+)',
                    line).groups()

                if "," in interface and interface.startswith("Giga"):
                    multi_inter = (
                        interface.replace(
                            "GigabitEthernet 1/", "")).split(",")
                    for a in multi_inter:
                        mac_db.append(
                            dict(
                                mac_type=mac_type,
                                vlan_id=vlan_id,
                                mac=mac,
                                interface="".join(["GigabitEthernet 1/", a])
                            )
                        )
                elif "-" in interface and interface.startswith("Giga"):
                    multi_inter = (
                        interface.replace(
                            "GigabitEthernet 1/", "")).split("-")
                    for a in multi_inter:
                        mac_db.append(
                            dict(
                                mac_type=mac_type,
                                vlan_id=vlan_id,
                                mac=mac,
                                interface="".join(["GigabitEthernet 1/", a])
                            )
                        )
                elif "," in interface and interface.startswith("10Giga"):
                    multi_inter = (
                        interface.replace(
                            "10GigabitEthernet 1/", "")).split(",")
                    for a in multi_inter:
                        mac_db.append(
                            dict(
                                mac_type=mac_type,
                                vlan_id=vlan_id,
                                mac=mac,
                                interface="".join(["10GigabitEthernet 1/", a])
                            )
                        )
                elif "-" in interface and interface.startswith("10Giga"):
                    multi_inter = (
                        interface.replace(
                            "10GigabitEthernet 1/", "")).split("-")
                    for a in multi_inter:
                        mac_db.append(
                            dict(
                                mac_type=mac_type,
                                vlan_id=vlan_id,
                                mac=mac,
                                interface="".join(["10GigabitEthernet 1/", a])
                            )
                        )
                else:
                    mac_db.append(
                        dict(
                            mac_type=mac_type,
                            vlan_id=vlan_id,
                            mac=mac,
                            interface=interface
                        )
                    )
            except AttributeError:
                continue

        return mac_db

    def _get_ddmi_status(self, ddmi_status_txt):

        ddmi_status = []
        ddmi_info = {}
        interface_line = False

        for line in ddmi_status_txt:
            try:
                interface = re.search(r'([0-1a-zA-Z]+)\s+(1/.+)', line)
                if interface is not None:
                    ddmi_info["interface"] = interface.group(0)
                    interface_line = True

                if interface_line:
                    vendor = re.search(r'Vendor\s*:(.+)', line)
                    if vendor is not None:
                        ddmi_info["vendor"] = (vendor.group(1)).lstrip()

                    part_number = re.search(r'Part Number\s*:(.+)', line)
                    if part_number is not None:
                        ddmi_info["part_number"] = (
                            part_number.group(1)).lstrip()

                    serial_number = re.search(r'Serial Number\s*:(.+)', line)
                    if serial_number is not None:
                        ddmi_info["serial_number"] = (
                            serial_number.group(1)).lstrip()

                    revision = re.search(r'Revision\s*:(.+)', line)
                    if revision is not None:
                        ddmi_info["revision"] = (revision.group(1)).lstrip()

                    transceiver = re.search(r'Transceiver\s*:(.+)', line)
                    if transceiver is not None:
                        ddmi_info["transceiver"] = (
                            transceiver.group(1)).lstrip()

                if "DDMI Information" in line:
                    interface_line = False
                    ddmi_status.append(ddmi_info)
                    ddmi_info = {}
            except AttributeError:
                continue

        return ddmi_status

    def _get_interface_status(self, int_status_txt, ddmi_status):

        interface_status = []

        for line in int_status_txt:
            try:
                interface, num, admin_mode, speed_duplex, flow_control, mtu, excessive, link_state, link_medium = re.search(
                    r'([0-1a-zA-Z]+)\s+(1/.+)\s+([a-z]+)\s+([0-1A-Za-z]+)\s+([a-z]+)\s+([0-9]+)\s+([A-Za-z]+)\s+([0-1A-Za-z]+)\s+(.+)', line).groups()

                if link_medium == " ":
                    link_medium = None

                interface_status.append(
                    dict(
                        interface_type=interface,
                        interface_full_name=" ".join(
                            [interface, num.replace(" ", "")]),
                        interface_name=num.replace("1/", "").replace(" ", ""),
                        admin_mode=admin_mode,
                        speed_duplex=speed_duplex,
                        flow_control=flow_control,
                        mtu=mtu,
                        excessive=excessive,
                        link_state=link_state,
                        link_medium=link_medium
                    )
                )

            except AttributeError:
                continue

        for if_status in interface_status:
            for ddmi in ddmi_status:
                if if_status['interface_full_name'] == ddmi['interface']:
                    if_status['ddmi_information'] = ddmi
                    break

        return interface_status

    def _get_system_status(self, system_status_txt):
        system_info = {}

        for line in system_status_txt:
            try:
                serialnumber = re.search(r'Serial #\s*:(.+)', line)
                if serialnumber is not None:
                    system_info["serialnumber"] = (
                        serialnumber.group(1)).lstrip()

                system_name = re.search(r'System Name\s*:(.+)', line)
                if system_name is not None:
                    system_info["system_name"] = (system_name.group(1)).lstrip()

                system_location = re.search(r'System Location\s*:(.+)', line)
                if system_location is not None:
                    system_info["system_location"] = (
                        system_location.group(1)).lstrip()

                os_version = re.search(r'Software Version\s*:(.+)', line)
                if os_version is not None:
                    system_info["os_version"] = (
                        os_version.group(1)).lstrip()

                system_uptime = re.search(r'System Uptime\s*:(.+)', line)
                if system_uptime is not None:
                    system_info["system_uptime"] = (
                        system_uptime.group(1)).lstrip()

                mac_address = re.search(r'MAC Address\s*:(.+)', line)
                if mac_address is not None:
                    system_info["mac_address"] = (
                        mac_address.group(1)).lstrip()

            except AttributeError:
                continue

        return system_info

    def _get_uplink_ports(self, configuration):
        interfaces = configuration['cnfg_json']['cnfg_interfaces']
        uplink_ports = []

        for giga in interfaces['GigabitEthernet']:
            if giga['description']:
                interface_description = "".join(giga['description'])
                if (interface_description in "FC-UPLINK-PORT" or
                        "FC-UPLINK-PORT" in interface_description):
                    uplink_ports.append(giga['full_name'])

        for tengiga in interfaces['10GigabitEthernet']:
            if tengiga['description']:
                interface_description = "".join(tengiga['description'])
                if (interface_description in "FC-UPLINK-PORT" or
                        "FC-UPLINK-PORT" in interface_description):
                    uplink_ports.append(tengiga['full_name'])

        return uplink_ports

    def _serializer(self, sw_txt_information):
        # Realizamos un split de los output
        plain_text_config = sw_txt_information['cnfg_txt']
        # cnfg_txt = sw_txt_information['cnfg_txt'].split('\n')
        mac_add_txt = sw_txt_information['mac_add_txt'].split('\n')
        int_status_txt = sw_txt_information['int_status_txt'].split('\n')
        ddmi_status_txt = sw_txt_information['ddmi_status_txt'].split('\n')
        system_status_txt = sw_txt_information['system_status_txt'].split('\n')
        lp_status_txt = sw_txt_information['lp_status_txt'].split('\n')

        sw_data = {}

        configuration = self._get_configuration(
            plain_text_config)

        sw_data['configuration'] = {
            "cnfg_txt": configuration['cnfg_txt']
        }

        sw_data['serialized_configuration'] = {
            "cnfg_json": configuration['cnfg_json']
        }

        sw_data['mac_table_status'] = {
            'mac_table': self._get_mac_table(mac_add_txt)
        }

        ddmi_status = self._get_ddmi_status(ddmi_status_txt)

        sw_data['interface_status'] = {
            'interfaces': self._get_interface_status(
                            int_status_txt, ddmi_status)
        }

        sw_data['uplink_ports'] = self._get_uplink_ports(
            sw_data['serialized_configuration'])

        sw_data['system_status'] = self._get_system_status(system_status_txt)
        sw_data['loop_protect_status'] = self._get_loop_protect_status(
            lp_status_txt)

        sw_data['os_version'] = sw_data['system_status']['os_version']
        sw_data['hostname'] = sw_data['system_status']['system_name']
        sw_data['serialnumber'] = sw_data['system_status']['serialnumber']

        return sw_data

    def retrieve_information(self):
        try:
            access_switch = {
                'device_type': 'cisco_ios',
                'host': self.mgmt_ip,
                'username': self.credentials['username'],
                'password': self.credentials['password'],
                'global_delay_factor': 2
            }

            print("Conectando al equipo: "+self.mgmt_ip)
            net_connect = None
            net_connect = ConnectHandler(**access_switch)

            sw_txt_information = {}

            retry_flag = True
            count_retry = 0

            # Execute Show commands
            for command in self._get_commands():
                print(
                    command['msg'] + ": " +
                    command['command']
                )

                while retry_flag and count_retry < 4:
                    show_content = net_connect.send_command(
                        command['command']
                    )
                    if len(show_content.split("\n")) < 4:
                        print(
                            "Some error occurred: The show " +
                            "output is too short. Retrying..."
                        )
                        count_retry += 1
                    else:
                        sw_txt_information[command['information']] = \
                            show_content
                        retry_flag = False

                retry_flag = True
                count_retry = 0

            # Process the output of each show command
            node_information = self._serializer(sw_txt_information)
            node_information['device_model_id'] = self.device_model_id
            node_information['mgmt_ip'] = self.mgmt_ip
            print("Creando SCO ID basado en Hostname del dispositivo...")
            node_information['sco_id'] = [int(
                re.findall(r'\d+', node_information['hostname'])[0])]
            print("SCO ID:", node_information['sco_id'])
            print(
                "La informacion del equipo " +
                node_information['hostname'] + " fue tomada con exito."
            )
            return node_information
        except BaseException as e:
            print(e)
            print("No se pudo obtener/guardar"
                  " la informacion del equipo {}".format(
                        self.mgmt_ip))
        finally:
            if net_connect:
                net_connect.disconnect()

    def deploy_configuration(self, configuration: list = []):
        if configuration:
            print("Iniciando el envio de configuracion.")
            try:
                access_switch = {
                    'device_type': 'cisco_ios',
                    'host': self.mgmt_ip,
                    'username': self.credentials['username'],
                    'password': self.credentials['password'],
                    'global_delay_factor': 2
                }

                print(f"Conectando al equipo: {self.mgmt_ip}")
                net_connect = None
                net_connect = ConnectHandler(**access_switch)
                net_connect.find_prompt()
                output = net_connect.send_config_set(configuration)
                print(output)
            except BaseException as e:
                print(e)
                print(
                    f"No se logro aplicar la configuracion al equipo {self.mgmt_ip}")
            finally:
                if net_connect:
                    net_connect.disconnect()
        else:
            print("La configuracion esta vacia.")


class S4224(TransitionDevice):

    def _get_vlans(self, cnfg_txt):
        vlans_db = []
        vlan_cnfg = []
        list_vlan_cnfg = []
        flag = False
        vlan_id = None
        vlan_name = None

        # Buscamos en la configuracion TXT (linea por linea)
        # todas las VLAN y sus atributos, ejecutando un parser.
        # Ejemplo:
        #
        # vlan 677
        # name Cliente-A
        # !
        # vlan 678
        # name Cliente-B
        # !
        # vlan 700
        # name Cliente-C

        for line in cnfg_txt:
            if "vlan" in line:
                vlan_check = line.split()
                if len(vlan_check) == 2:
                    # Este flag nos permite appendear
                    # la siguiente linea de la config
                    # correspondiente al nombre de la
                    # vlan (si es que lo tiene).
                    flag = True

            if flag:
                vlan_cnfg.append(line)

            # La configuracion de la VLAN
            # finaliza con un "!".
            if flag and line == "!":
                flag = False
                list_vlan_cnfg.append(vlan_cnfg)
                vlan_cnfg = []

        for vlan in list_vlan_cnfg:
            if len(vlan) == 2:
                vlan_id = vlan[0]
                vlan_id = int(vlan_id.replace("vlan ", ""))
            if len(vlan) == 3:
                vlan_id = vlan[0]
                vlan_id = int(vlan_id.replace("vlan ", ""))
                vlan_name = vlan[1]
                vlan_name = vlan_name.replace(" name ", "")

            vlans_db.append(
                dict(
                    vlan_id=vlan_id,
                    vlan_name=vlan_name
                )
            )
            vlan_id = None
            vlan_name = None

        return vlans_db


class LIB4424(TransitionDevice):

    def _get_vlans(self, cnfg_txt):
        vlans_db = []
        vlan_cnfg = []
        list_vlan_cnfg = []
        flag = False
        vlan_id = None
        vlan_name = None

        # Creamos una lista con la informacion completa de cada vlan
        for line in cnfg_txt:
            if (
                "vlan" in line
            ):
                vlan_check = line.split()
                if len(vlan_check) == 2:
                    flag = True

            if flag:
                vlan_cnfg.append(line)

            if flag and line == "!":
                flag = False
                list_vlan_cnfg.append(vlan_cnfg)
                vlan_cnfg = []

        for vlan in list_vlan_cnfg:
            if len(vlan) == 2:
                vlan_id = vlan[0]
                if "," in vlan_id:
                    vlan_id = vlan_id.replace("vlan ", "")
                    vlan_id = vlan_id.split(",")
                    for vl in vlan_id:
                        if "-" in vl:
                            vl = vl.split("-")
                            vl = list(
                                range(
                                    int(vl[0]),
                                    int(vl[1])+1)
                            )

                            for vl_a in vl:
                                vlans_db.append(
                                    dict(
                                        vlan_id=int(vl_a),
                                        vlan_name=vlan_name
                                    )
                                )
                        else:
                            vlans_db.append(
                                dict(
                                    vlan_id=int(vl),
                                    vlan_name=vlan_name
                                )
                            )
                else:
                    if "-" in vlan_id:
                        vlan_id = vlan_id.replace("vlan ", "")
                        vl = vlan_id.split("-")
                        vl = list(
                            range(
                                int(vl[0]),
                                int(vl[1])+1)
                        )

                        for vl_a in vl:
                            vlans_db.append(
                                dict(
                                    vlan_id=int(vl_a),
                                    vlan_name=vlan_name
                                )
                            )
                    else:
                        vlan_id = int(vlan_id.replace("vlan ", ""))

                        vlans_db.append(
                            dict(
                                vlan_id=vlan_id,
                                vlan_name=vlan_name
                            )
                        )

            elif len(vlan) == 3:
                vlan_id = vlan[0]
                vlan_id = int(vlan_id.replace("vlan ", ""))
                vlan_name = vlan[1]
                vlan_name = vlan_name.replace(" name ", "")

                vlans_db.append(
                    dict(
                        vlan_id=vlan_id,
                        vlan_name=vlan_name
                    )
                )

            vlan_id = None
            vlan_name = None

        return vlans_db
