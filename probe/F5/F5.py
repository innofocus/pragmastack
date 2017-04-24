#!/usr/bin/env python
# coding=utf-8

from netaddr import *
from pprint import pprint
import re
import bigsuds
import logging



class f5(object):
    """ Class de connexion aux f5 pour les requests"""
    def __init__(self, device):
        self.log = logging.getLogger(__name__)
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self.log.addHandler(ch)
        self.log.setLevel(logging.DEBUG)
        if not device['debug']:
            self.log.setLevel(logging.INFO)
        self.device = device
        self.connect = bigsuds.BIGIP(hostname=device['host'],username=device['username'],password=device['password'])
        self._get_device_info()
        self.log.debug('F5 connect done')

    def _get_device_info(self):
        # Todo : code this !
        return ({ 'mock' : 'fake info'})

class lc(f5):
    """ Class de connexion au lc"""
    Models = [
        ('Lc_vs', 'uses', 'Lc_pool'),
        ('Lc_pool', 'provides', 'Lc_node'),
        ('Lc_vs', 'uses', 'Ip'),
        ('Lc_node', 'uses', 'Ip'),
        ('Lc_vs', 'uses', 'Port'),
        ('Lc_pool', 'uses', 'Port'),
    ]
    def __init__(self, device):
        super(lc,self).__init__(device)
        # on recupere la liste des vs
        self.vs_list = self.get_vs()
        self.labels = []
        for i in self.Models:
            self.labels.append(i[0])
        self.log.debug(' lc init done ')

    def get_vs(self):
        return self.connect.GlobalLB.VirtualServerV2.get_list()

    def get_config(self):
        # Declaration variable
        result = []
        lctumple = ()
        adctumple = ()

        # LC - Boucle for sur chacun des VS
        for lc_vs_name in self.vs_list:
            try:
                lc_pool_name = self.connect.LocalLB.VirtualServer.get_default_pool_name(virtual_servers=[[lc_vs_name['name']]])[0]
                lc_node_list = (self.connect.LocalLB.Pool.get_member_v2([lc_pool_name]))
                # Lc- Boucle for sur chacun des Node present dans le pool rattache au VS
                for lc_node in lc_node_list:
                    for node in lc_node:
                        # nom du VS
                        lcvsname = lc_vs_name["name"]
                        # Adresse Public du VS
                        lcvsippub = self.connect.LocalLB.VirtualServer.get_destination([lc_vs_name['name']])[0]["address"]
                        # Port du VS
                        lcvsportpub = self.connect.LocalLB.VirtualServer.get_destination([lc_vs_name['name']])[0]["port"]
                        # Nom du node
                        lcvsnode = node["address"]
                        # IP du node
                        lcvsipnode = self.connect.LocalLB.NodeAddressV2.get_address([node["address"]])[0]
                        # Liste des elements au format JSON
                        lctumple = ({'Lc_vs': {'name': lcvsname, 'port' : str(lcvsportpub)}},
                                    {'Ip': {'name': lcvsippub}},
                                    {'Lc_pool': {'name': lc_pool_name}},)
                        result.append(lctumple)
                        self.log.debug(' lc get_config : '+str(lctumple))

                        lctumple = ({'Lc_node': {'name': lcvsnode}},
                                    {'Ip': {'name': lcvsipnode}},
                                    {'Lc_pool': {'name': lc_pool_name, 'port' : str(lcvsportpub)}},)
                        result.append(lctumple)
                        self.log.debug(' lc get_config : '+str(lctumple))
                        # print lctumple
            except:
                lctumple = ({'Lc_vs': {'name': lcvsname}},)
                result.append(lctumple)
                self.log.info ("il n'y a pas de vip public" + lc_vs_name["name"])
        return result

class adc(f5):
    """ Class de connexion a Adc"""
    Models = [
        ('Adc_vs', 'provides', 'Ipport'),
        ('Adc_pool', 'uses', 'Ipport'),
        ('Adc_pool', 'uses', 'Adc_monitor'),
        ('Adc_pool', 'uses', 'Adc_node'),
        ('Adc_node', 'provides', 'Ipport'),
        ('Ipport','uses','Server'),
        ('Adc_monitor', 'uses', 'Ipport'),
        ('Adc_monitor', 'uses', 'Adc_node'),
    ]

    def __init__(self, device):
        super(adc,self).__init__(device)
        self.vs_list = self.get_vs()
        self.labels = []
        for i in self.Models:
            self.labels.append(i[0])
        self.log.debug(' adc init done ')

    def get_vs(self):
        return self.connect.LocalLB.VirtualServer.get_list()

    def get_config(self):
        # Declaration variable
        result = []
        lctumple = ()
        adctumple = ()

        # we get monitor template type
        proptypes=['STYPE_SEND','STYPE_GET','STYPE_RECEIVE','STYPE_USERNAME','STYPE_PASSWORD']
        for mon in self.connect.LocalLB.Monitor.get_template_list():
            mondesc = self.connect.LocalLB.Monitor.get_description([mon['template_name']])[0]
            tmpres = ({'Adc_monitor': {'name': mon['template_name'], 'type' : mon['template_type'], 'description' : mondesc}},)

            for t in proptypes:
                try:
                    monprop = None
                    monprop = self.connect.LocalLB.Monitor.get_template_string_property([mon['template_name']], [t])[0]['value']
                    if monprop and t == 'STYPE_PASSWORD':
                        monprop = "XXXXXXXX"
                    self.log.debug(' property string type : '+t+' ; prop : '+str(monprop))
                    tmpres[0]['Adc_monitor'][t]=monprop
                except:
                    self.log.debug(' No property string : '+t+' ')
                    pass

            self.log.debug(tmpres)
            result.append(tmpres)


        
        # ADC - Boucle for sur chacun des VS
        for adc_vs_name in self.vs_list:
        #for adc_vs_name in ['/Common/MUT-PRD-NAV']:
                self.log.debug(' get_config : adc_vs_name :'+adc_vs_name)
                for adc_pool_name in self.connect.LocalLB.VirtualServer.get_default_pool_name(virtual_servers=[[adc_vs_name]]):
                    try:
                        adc_pool_description = unicode(self.connect.LocalLB.Pool.get_description([adc_pool_name])[0], 'utf-8')
                    except:
                        adc_pool_description = ' Bigsuds Internal Text Error (BIT.)'
                        self.log.info(adc_pool_description+"... on : "+adc_vs_name)
                    # instance monitor
                    for mon in self.connect.LocalLB.Pool.get_monitor_instance([adc_pool_name]):
                        for monit in mon:
                            adc_pool_tuple = ({'Adc_pool': {'name': adc_pool_name, 'description' : adc_pool_description}},)
                            self.log.debug(' monit : '+str(monit))
                            adcvsmonitortemplate = monit['instance']['template_name']
                            adcvsmonitorenable = monit['enabled_state']
                            adcvsmonitoradress = monit['instance']['instance_definition']['ipport']['address']
                            adcvsmonitorport = monit['instance']['instance_definition']['ipport']['port']

                            adc_pool_tuple += ({'Adc_monitor': {'name': adcvsmonitortemplate, 'state': adcvsmonitorenable}},)
                            adc_pool_tuple += ({'Ipport': {'name': adcvsmonitoradress+':'+str(adcvsmonitorport), 'type' : 'tcp'}},)
                            result.append(adc_pool_tuple)
                            self.log.debug(' monitor : '+adc_pool_name+" - "+adcvsmonitortemplate+" - "+adcvsmonitoradress)

                    # Liste des Nodes present
                    adc_node_list = (self.connect.LocalLB.Pool.get_member_v2([adc_pool_name]))
                    # Pour chaque node apartenent a un pool
                    for adc_node in adc_node_list:
                        for node in adc_node:
                            # Nom du node
                            adcvsnode = node["address"]
                            adcvsnodeport = node["port"]
                            for adcvsdest in self.connect.LocalLB.VirtualServer.get_destination([adc_vs_name]):
                                # Ip du vs
                                adcvsippriv = adcvsdest["address"]
                                # Port du vs
                                adcvsportpriv = adcvsdest["port"]
                                for adcvsipnode in self.connect.LocalLB.NodeAddressV2.get_address([adcvsnode]):
                                    # Address IP du Node
                                    # Liste des elements au format JSON
                                    adctumple = ({'Adc_vs': {'name': adc_vs_name}},
                                                 {'Ipport' : {'name' : adcvsippriv+':'+str(adcvsportpriv), 'type' : 'tcp'}},
                                                 {'Adc_pool': {'name': adc_pool_name, 'description' : adc_pool_description}},)
                                    result.append(adctumple)
                                    self.log.debug(' lc get_config : ' + str(adctumple))

                                    adctumple = ({'Adc_node': {'name': adcvsnode}},
                                                 {'Adc_pool': {'name': adc_pool_name, 'description' : adc_pool_description}},
                                                 {'Ipport' : { 'name' : adcvsipnode+':'+str(adcvsnodeport), 'type' : 'tcp'}},)
                                    result.append(adctumple)
                                    self.log.debug(' lc get_config : ' + str(adctumple))
                                    # print adctumple
        return result