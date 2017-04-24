#!/usr/bin/env python

from pprint import pprint
import re
from urllib.request import urlopen
from netaddr import *
import xmltodict
from xml.etree import ElementTree
import ssl
import logging


class palo:
    """ Class de connexion aux n5k pour les requests"""

    labels = ['Vlan', 'Network', 'Ip', 'Nic', 'Gateway']

    def __init__(self,device):
        self.log = logging.getLogger(__name__)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self.log.addHandler(ch)
        self.log.setLevel(logging.DEBUG)
        if not device['debug']:
            self.log.setLevel(logging.INFO)
        device.pop('debug')
        self.device = device
        urlkeygen = "https://"+device['host']+":"+str(device['port'])+"/api/?type=keygen&user="+device['username']+"&password="+device['password']
        context = ssl._create_unverified_context()
        response = xmltodict.parse(urlopen(urlkeygen,context=context).read())
        if response['response']['@status'] == 'error':
            print ('Bad credential')
            exit(1)
        self.apikey = response['response']['result']['key']
        urlconfig = "https://"+device['host']+":"+str(device['port'])+"/api/?type=export&category=configuration&key="+self.apikey
        self.paloconfig = xmltodict.parse(urlopen(urlconfig,context=context).read())
        self.interfaces = self.paloconfig['config']['devices']['entry']['network']['interface']['aggregate-ethernet']['entry']['layer3']['units']['entry']
        self.vlans = self.get_vlans()


    def get_ips(self):
        result = []
        tumple = ()
        for interface in self.interfaces:
            # le nom du vlan est dans le comment
            if 'comment' in interface:
                vlan_name = re.sub('\s+', ' ', interface['comment'])
                vlan_name = re.sub(' $', '', vlan_name)
            else:
                vlan_name = 'None'

            if 'ip' in interface:
                if '@name' in interface['ip']['entry']:
                    gateway = interface['ip']['entry']['@name']
                    network = str(IPNetwork(gateway).cidr)
            else:
                gateway = ''
                network = ''
            tag = interface['tag']

            urllistmacaddress = "https://"+self.device['host']+"/api/?type=op&cmd=%3Cshow%3E%3Carp%3E%3Centry+name+%3D+%27ae1." + interface['tag'] + "%27%2F%3E%3C%2Farp%3E%3C%2Fshow%3E&key="+self.apikey
            contentarp = urlopen(urllistmacaddress, context=ssl._create_unverified_context())
            macel = ElementTree.parse(contentarp)
            rootmac = macel.getroot()
            valmac = rootmac.findall(".//entry")
            for mac in valmac:
                ipaddr = (mac.find('ip')).text
                macaddr = (mac.find('mac')).text
                tumple = ({'Vlan' : { 'name' : vlan_name+"-"+str(tag), 'id' : str(tag), 'friendly' : vlan_name}},
                          {'Ip': {'name': ipaddr, 'version': 'ipv4'}},
                          {'Nic': {'name': macaddr}},
                          {'Network': {'name': network, 'broadcast' : str(IPNetwork(network).broadcast)}},)
                self.log.debug(tumple)
                result.append(tumple)
        return result


    def get_vlans(self):
        self.log.debug('get_vlans...')
        # result in form: [ ({'Vlan': {'name': < name >, 'id': < id >}, {'Label': {'name': < name >}, ...), (...)]
        result = []
        tumple = ()
        for interface in self.interfaces:
            # le nom du vlan est dans le comment
            if 'comment' in interface:
                vlan_name = re.sub('\s+',' ',interface['comment'])
                vlan_name = re.sub(' $','',vlan_name)
            else:
                vlan_name = 'None'

            if 'ip' in interface:
                if '@name' in interface['ip']['entry']:
                    gateway = interface['ip']['entry']['@name']
                    network = str(IPNetwork(gateway).cidr)
                    gateway = str(IPNetwork(gateway).ip)
            else:
                gateway = ''
                network = ''

            it_tag = re.sub('ae1.','',interface['@name'])
            tag = interface['tag']
            if tag != it_tag:
                vlan_name = 'Tag configuration error on '+vlan_name+' :'+tag+"/"+it_tag
            tumple = ( {'Vlan' : { 'name' : vlan_name+"-"+str(tag), 'id' : str(tag), 'friendly' : vlan_name}},
                       {'Network' : { 'name' : network, 'broadcast' : str(IPNetwork(network).broadcast)}},
                       {'Gateway' : { 'name' : gateway}},
                       {'Ip' : { 'name' : gateway, 'version' : 'ipv4'}},)
            result.append(tumple)
        return result

    def get_vlans_infos(self,id):
        return self.vlans[id]

    def _get_device_info(self):
        return { 'mock' : 'fake info'}

def main(device,action, value):
    """ call des methods"""
    n=palo(device)
    if action=="get_vlans":
        pprint (n.vlans)

if __name__ == "__main__":
    # execute only if run as a script
    import argparse
    import textwrap
    parser = argparse.ArgumentParser(description="Nexus 5k interfaces",
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=textwrap.dedent('''Enjoy !'''))
    parser.add_argument('--username', dest="username", help="Account Username for fw")
    parser.add_argument('--password', dest="password", help="Account Password for fw")
    parser.add_argument('--host', dest="host", help="adresse du fw")
    parser.add_argument('--port', dest="port", default=443, help="port du fw")
    parser.add_argument('--action', dest="action", help="action ?")
    parser.add_argument('--value', dest="value", help="port du fw")
    parser.add_argument('-v', dest="verbose", action='count', help="mode verbeux")

    options = parser.parse_args()
    device= {
        'host':   options.host,
        'username': options.username,
        'password': options.password,
        'port' : options.port or 443,          # optional, defaults to 443
    }
    main(device=device, action=options.action, value=options.value)