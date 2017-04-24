#!/usr/bin/env python

import netmiko
from bs4 import BeautifulSoup
from ncclient import manager
from netaddr import *
from pprint import pprint
import re
import logging



class n5k:
    """ Class de connexion aux n5k pour les requests"""

    labels=['Vlan', 'Network', 'Ip', 'Nic']

    def __init__(self, device):
        self.log = logging.getLogger(__name__)
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self.log.addHandler(ch)
        self.log.setLevel(logging.DEBUG)
        if not device['debug']:
            self.log.setLevel(logging.INFO)
        device.pop('debug')
        device.update({'device_type': 'cisco_nxos'})
        self.device = device
        netmikodev = dict(device)
        netmikodev.pop('type')
        netmikodev.pop('name')
        self.connect = netmiko.ConnectHandler(**netmikodev)
        self.ncclient = manager.connect(host=device['host'], port=22, username=device['username'],
                                        password=device['password'], hostkey_verify=False,
                                        device_params={'name':'nexus'}, allow_agent=False, look_for_keys=False)
        self._get_device_info()
        self.vlans_ids = self._get_vlans_name()
        self.vlans = self._get_vlans()
        self.log.debug('n5k init done')

    def get_from_ip(self, ip):
        cmd_result = self.connect.send_command('sh ip arp | in "' + ip + ' "')
        if ip in cmd_result:
            temp = re.split(' *', cmd_result)[2].replace('.', '')
            mac = ':'.join(temp[i:i + 2] for i in range(0, 12, 2))
            vlan_id = re.split(' *', cmd_result)[3].replace('Vlan', '')
            vlan_name = self.get_vlan_name(vlan_id)
            return {'Ip': {'name': ip}, 'Nic': {'name': mac}, 'Vlan': {'id': vlan_id, 'name': vlan_name + "-" + vlan_id, 'friendly' : vlan_name}}
        else:
            self.connect.send_command('ping ' + ip + ' count 1')
            cmd_result = self.connect.send_command('sh ip arp | in "' + ip + ' "')
            if ip in cmd_result:
                temp = re.split(' *', cmd_result)[2].replace('.', '')
                mac = ':'.join(temp[i:i + 2] for i in range(0, 12, 2))
                vlan_id = re.split(' *', cmd_result)[3].replace('Vlan', '')
                vlan_name = self.get_vlan_name(vlan_id)
                return {'Ip': {'name': ip}, 'Nic': {'name': mac}, 'Vlan': {'id': vlan_id, 'name': vlan_name + "-" + vlan_id, 'friendly' : vlan_name}}
            else:
                return {'Ip': {'name': ip}, 'Nic': {'name': ''}, 'Vlan': {'id': '', 'name': ''}}

    def _get_vlans_name(self):
        result = {}
        cmd_result = self.connect.send_command('show vlan brief | in "^[0-9]"')
        for line in cmd_result.split('\n'):
            field = re.split(' *', line)
            result[field[0]] = field[1]
        return result

    def _get_device_info(self):
        ncfilter = '''<show xmlns="http://www.cisco.com/nxos:1.0"><inventory></inventory></show>'''
        soup = BeautifulSoup(self.ncclient.get(('subtree', ncfilter)).data_xml, 'lxml-xml')
        i = soup.find('ROW_inv')
        return { 'productid' : i.productid.string, 'serialnum' : i.serialnum.string}

    def _get_vlans(self):
        # temp vlan ids table
        vlanids = {}
        networks = {}
        # result in form : [ ({'Vlan' : { 'name' : <name>, 'id':<id>}, { 'Label' : {'name':<name>}, ...) (...) ]
        result = []

        self.log.debug('_get_vlans : get vlans')
        ncfilter = '''<show xmlns="http://www.cisco.com/nxos:1.0"><vlan></vlan></show>'''
        soup = BeautifulSoup(self.ncclient.get(('subtree', ncfilter)).data_xml, 'lxml-xml')

        for i in soup.find_all('ROW_vlanbrief'):
                id = i.find('vlanshowbr-vlanid').string
                vlanname = i.find('vlanshowbr-vlanname').string
                vlanids.update({id: vlanname})

        self.log.debug('_get_vlans : get interface')
        ncfilter = '''<show xmlns="http://www.cisco.com/nxos:1.0"><interface></interface></show>'''
        soup = BeautifulSoup(self.ncclient.get(('subtree', ncfilter)).data_xml, 'lxml-xml')

        for i in soup.find_all('ROW_interface'):
            if 'Vlan' in i.interface.string:
                id = i.interface.string.replace('Vlan','')
                tumple = ({'Vlan': {'name': vlanids[id]+"-"+id, 'id': id, 'friendly' : vlanids[id]}},)
                try:
                    ip = i.svi_ip_addr.string
                    network = str(IPNetwork(ip+'/'+i.svi_ip_mask.string).cidr)
                    # keep the network aside for next step
                    networks.update({id : network})
                    tumple += ({'Network' : {'name': network, 'broadcast' : str(IPNetwork(network).broadcast)}},)
                    tumple += ({'Ip': {'name': ip}},)
                except AttributeError:
                    pass
                # try:
                #     mac = ':'.join(i.svi_mac.string.replace('.', '')[x:x + 2] for x in range(0, 12, 2))
                #     tumple += ({'Nic': {'name': mac}},)
                # except AttributeError:
                #     pass
                result.append(tumple)
            elif 'mgmt' in i.interface.string:
                ip = i.eth_ip_addr.string
                network = str(IPNetwork(ip + '/' + i.eth_ip_mask.string).cidr)
                mac = ':'.join(i.eth_hw_addr.string.replace('.', '')[x:x + 2] for x in range(0, 12, 2))
                tumple = ({'Network' : {'name': network}},)
                tumple += ({'Ip': {'name': ip, 'type' : 'mgmt'}},)
                tumple += ({'Nic' : {'name': mac}},)
                result.append(tumple)

        self.log.debug('_get_vlans : get hsrp')
        ncfilter = '''<show xmlns="http://www.cisco.com/nxos:1.0"><hsrp></hsrp></show>'''
        soup = BeautifulSoup(self.ncclient.get(('subtree', ncfilter)).data_xml, 'lxml-xml')

        for i in soup.find_all('ROW_grp_detail'):
            # result in form : [ ({'Vlan' : { 'name' : <name>, 'id':<id>}, { 'Label' : {'name':<name>}, ...) (...) ]
            # tumple is temp tuple
            vlanname = vlanids[i.sh_group_num.string]
            vlanid = i.sh_group_num.string
            vlan = ({'Vlan': {'name': vlanname+"-"+vlanid, 'id': vlanid, 'friendly' : vlanname}},)
            tumple = vlan
            if i.sh_vip.string:
                tumple += ({'Ip': {'name': i.sh_vip.string, 'type': 'hsrp'}},)
                tumple += ({'Gateway': {'name': i.sh_vip.string, 'type': 'hsrp', 'annotation': 'Nexus 5k Core Network'}},)
                tumple += ({'Network': {'name': networks[i.sh_group_num.string]}},)
                #ip=IPNetwork()
                if i.sh_vmac.string:
                    mac = ':'.join(i.sh_vmac.string.replace('.', '')[x:x + 2] for x in range(0, 12, 2))
                    tumple += ({'Nic': {'name': mac}},)
                result.append(tumple)
            tumple = vlan
            if i.sh_active_router_addr.string:
                tumple += ({'Ip': {'name': i.sh_active_router_addr.string, 'type': 'hsrp_active'}},)
                tumple += ({'Network': {'name': networks[i.sh_group_num.string]}},)
                result.append(tumple)
            tumple = vlan
            if i.sh_standby_router_addr.string:
                tumple += ({'Ip': {'name': i.sh_standby_router_addr.string, 'type': 'hsrp_standby'}},)
                tumple += ({'Network': {'name': networks[i.sh_group_num.string]}},)
                result.append(tumple)
        self.log.debug(str(result))
        return result

    def get_vlans(self):
        return self.vlans

    def get_vlan_id(self, name):
        return self.vlans_ids[name]

    def get_vlan_name(self, id):
        return self.vlans[id]

    def close(self):
        self.connect.disconnect()


def main(device, action, value):
    """ call des methods"""
    n = n5k(device)
    if action == "get_from_ip":
        a = n.get_from_ip(value)
        pprint(a)
    elif action == "get_from_range":
        range = IPNetwork(value)
        for ip in range.iter_hosts():
            a = n.get_from_ip(str(ip))
            pprint(a)
    n.close()


if __name__ == "__main__":
    # execute only if run as a script
    import argparse
    import textwrap

    parser = argparse.ArgumentParser(description="Nexus 5k interfaces",
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=textwrap.dedent('''Enjoy !'''))
    parser.add_argument('--username', dest="username", help="Account Username for n5K")
    parser.add_argument('--password', dest="password", help="Account Password for n5k")
    parser.add_argument('--host', dest="host", help="adresse du n5k")
    parser.add_argument('--port', dest="port", default=22, help="port du n5k")
    parser.add_argument('--action', dest="action", help="action ?")
    parser.add_argument('--value', dest="value", help="port du n5k")
    parser.add_argument('-v', dest="verbose", action='count', help="mode verbeux")

    options = parser.parse_args()
    device = {
        'device_type': 'cisco_nxos',
        'ip': options.host,
        'username': options.username,
        'password': options.password,
        'port': options.port,  # optional, defaults to 22
        'secret': '',  # optional, defaults to ''
        'verbose': False,  # optional, defaults to False
    }
    main(device=device, action=options.action, value=options.value)
