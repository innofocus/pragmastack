#!/usr/bin/env python

from __future__ import print_function
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
import subprocess
from pyVim import connect
import atexit
import ssl
import sys
import pprint
from py2neo import Graph, Node, Relationship
import os
import re
import argparse
import textwrap

import logging

class vmware:
    """ Class de connexion au vcenter pour les requests"""

    labels = ['Vlan', 'Network', 'Ip', 'Nic', 'Gateway', 'Server', 'Datacenter', 'Host', 'Switch', 'Disk', 'Datastore']

    def __init__(self, device):
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

        self.log.debug(str(device))

        context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        context.verify_mode = ssl.CERT_NONE
        self.serviceInstance = SmartConnect(host=device['host'],
                                       user=device['username'],
                                       pwd=device['password'],
                                       port=int(device['port']),
                                       sslContext=context)
        atexit.register(Disconnect, self.serviceInstance)
        self.content = self.serviceInstance.RetrieveContent()
        self.hosts = self.GetVMHosts()
        self.hostPgDict = self.GetHostsPortgroups()

        # other variables
        self.dvs_list = {'dvsuuid': {'portgroupkey': {'vlanid': '', 'porgroup': '', 'vswitch': ''}}}
        self.numvm = 0

    def _get_device_info(self):
        return { 'mock' : 'fake info'}

    def GetVMHosts(self):
        self.log.debug("Getting all ESX hosts ...")
        host_view = self.content.viewManager.CreateContainerView(self.content.rootFolder,
                                                            [vim.HostSystem],
                                                            True)
        obj = [host for host in host_view.view]
        host_view.Destroy()
        return obj


    def GetVMs(self):
        self.log.debug("Getting all VMs ...")
        vm_view = self.content.viewManager.CreateContainerView(self.content.rootFolder,
                                                          [vim.VirtualMachine],
                                                          True)
        obj = [vm for vm in vm_view.view]

        vm_view.Destroy()
        return obj

    def GetHostsPortgroups(self):
        print("Collecting portgroups on all hosts. This may take a while ...")
        hostPgDict = {}
        for host in self.hosts:
            pgs = host.config.network.portgroup
            hostPgDict[host] = pgs
            print("\tHost {} done.".format(host.name))
        print("\tPortgroup collection complete.")
        return hostPgDict


    def PrintVmInfo(self,vm):
        vmPowerState = vm.runtime.powerState
        print("Found VM:", vm.name + "(" + vmPowerState + ")")
        GetVMInfo(vm)

    def GetVMDisks(self,vm):
        dev_details={'Disks':{}}
        totalsize=0
        for device in vm.config.hardware.device:
            if device.backing is None:
                continue
            if hasattr(device.backing, 'fileName'):
                if (device.backing.datastore):
                    datastore = device.backing.datastore
                else:
                    datastore = "None"
                #get size in KB
                devicetype=type(device).__name__
                if devicetype == 'vim.vm.device.VirtualDisk':
                    size=int(re.sub("(,)|(KB)| ",'',device.deviceInfo.summary))
                else:
                    size=0
                totalsize += size
                dev_details['Disks'].update({ device.deviceInfo.label : {
                                'key': device.key,
                                'sizeKB': size,
                                'datastore': datastore,
                                'device type': devicetype,
                                'backing type': type(device.backing).__name__,
                                'fileName': device.backing.fileName,
                                'device ID': device.backing.backingObjectId }})
        dev_details['Disks'].update({'totalsizeKB' : totalsize})
        return dev_details

    def GetVMNics(self,vm):
        # on recupere les ip derniere les macs
        VMmacips={}
        try:
            for nic in vm.guest.net:
                addresses = nic.ipConfig.ipAddress
                #pprint.pprint(addresses)
                macaddr = nic.macAddress
                VMmacips.update({macaddr: {}})
                addrcount=0
                for addr in addresses:
                    addrcount+=1
                    VMmacips[macaddr].update({
                                        addrcount : {
                                        'ip' : addr.ipAddress,
                                        'prefix': addr.prefixLength,
                                        'origin': addr.origin,
                                        'state': addr.state}})
        # si les vm tools non configures
        except AttributeError:
            self.log.debug ('No IP address')
            pass
        #pprint.pprint(VMmacips)

        # on parse les nics
        VMNics = {'Nics': {}}
        for dev in vm.config.hardware.device:
            if isinstance(dev, vim.vm.device.VirtualEthernetCard):
                portGroup = None
                vlanId = None
                vSwitch = None
                if hasattr(dev.backing, 'port'):
                    portGroupKey = dev.backing.port.portgroupKey
                    dvsUuid = dev.backing.port.switchUuid
                    if (str(dvsUuid) in self.dvs_list) and (str(portGroupKey) in self.dvs_list[str(dvsUuid)]):
                            portGroup = self.dvs_list[str(dvsUuid)][str(portGroupKey)]['portGroup']
                            vlanId = self.dvs_list[str(dvsUuid)][str(portGroupKey)]['vlanId']
                            vSwitch = self.dvs_list[str(dvsUuid)][str(portGroupKey)]['vSwitch']
                    else:
                        try:
                            dvs = self.content.dvSwitchManager.QueryDvsByUuid(dvsUuid)
                        except:
                            portGroup = "** Error: DVS not found **"
                            vlanId = "NA"
                            vSwitch = "NA"
                        else:
                            pgObj = dvs.LookupDvPortGroup(portGroupKey)
                            portGroup = pgObj.config.name
                            try:
                                vlanId = str(pgObj.config.defaultPortConfig.vlan.vlanId)
                            except:
                                vlanId = "NA"
                            try:
                                vSwitch = str(dvs.name)
                            except:
                                vSwitch = "NA"
                            self.dvs_list[str(dvsUuid)]={ str(portGroupKey) : { 'portGroup' : portGroup, 'vlanId' : vlanId, 'vSwitch' : vSwitch}}
                else:
                    portGroup = dev.backing.network.name
                    vmHost = vm.runtime.host
                    # global variable hosts is a list, not a dict
                    host_pos = self.hosts.index(vmHost)
                    viewHost = self.hosts[host_pos]
                    # global variable hostPgDict stores portgroups per host
                    pgs = self.hostPgDict[viewHost]
                    for p in pgs:
                        if portGroup in p.key:
                            vlanId = str(p.spec.vlanId)
                            vSwitch = str(p.spec.vswitchName)
                if portGroup is None:
                    portGroup = 'NA'
                if vlanId is None:
                    vlanId = 'NA'
                if vSwitch is None:
                    vSwitch = 'NA'
                VMNics['Nics'].update( {dev.deviceInfo.label : { 'mac' : dev.macAddress,
                           'vswitch' : vSwitch,
                           'portgroup' : portGroup,
                           'vlanid' : vlanId}
                            })
                #pprint.pprint (VMmacips)
                if dev.macAddress in VMmacips:
                    VMNics['Nics'][dev.deviceInfo.label].update({'addresses': VMmacips[dev.macAddress]})


        return VMNics

    def GetVMFolder(self,vm):
        foldername=''
        while hasattr(vm, 'parent'):
            try:
                foldername=vm.parent.name+'/'+foldername
                vm=vm.parent
            except AttributeError:
                foldername='/'
                break

        return { 'folder': foldername }

    def GetVMInfo(self,vm):
        self.numvm+=1
        if hasattr(vm.config, 'numCoresPerSocket'):
            ncps = vm.config.numCoresPerSocket
        else:
            ncps = 1
        details = {'name': vm.summary.config.name,
                   'instance UUID': vm.summary.config.instanceUuid,
                   'bios UUID': vm.summary.config.uuid,
                   'path to VM': vm.summary.config.vmPathName,
                   'is template': vm.summary.config.template,
                   'guest OS id': vm.summary.config.guestId,
                   'guest OS name': vm.summary.config.guestFullName,
                   'memory MB': vm.summary.config.memorySizeMB,
                   'num cpu': vm.summary.config.numCpu,
                   'numCoresPerSocket': ncps,
                   'annotation': vm.summary.config.annotation,
                   'last modif': vm.config.modified.strftime("%Y-%m-%d %H:%M:%S"),
                   'hard vm version': vm.config.version,
                   'host name': vm.runtime.host.name,
                   'last booted timestamp': vm.runtime.bootTime,
                   'tools version': vm.guest.toolsVersion,
                   'tools running': vm.guest.toolsRunningStatus,
                   'tools status': vm.guest.toolsVersionStatus2,
                   'power state': vm.runtime.powerState}
        self.log.debug ('details done')
        details.update(self.GetVMNics(vm))
        self.log.debug('GetVMNics done')
        details.update(self.GetVMDisks(vm))
        self.log.debug('GetVMDisks done')
        details.update(self.GetVMFolder(vm))
        self.log.debug('GetVMFolder done')
        self.log.debug ("VM "+str(self.numvm))
        for name, value in details.items():
            print("  {0:{width}{base}}: {1}".format(name, repr(value), width=25, base='s'))

        # experimental
        # if not re.match('windows',details['guest OS name'].lower()):
        #     print ('Testing Linux connect')


        return details


    def GetChilds (self, parent, path):
        object_type = parent.__class__.__name__
        vmlist={}
        if (not (object_type == 'vim.VirtualMachine')) and hasattr(parent,'childEntity'):
            self.log.debug ('Folder '+ parent.name)
            for child in parent.childEntity:
                if child.__class__.__name__ == 'vim.VirtualMachine':
                    self.numvm+=1
                    vmlist.update({self.numvm : { 'vm' : child , 'folder' : path}})
                    #print (child.__class__.__name__, " ", self.numvm, path+'/'+child.name)
                else:
                    self.log.debug ('Folder '+child.name)
                    vmlist.update(self.GetChilds(child, path+'/'+child.name))
        elif object_type == 'vim.VirtualMachine':
            self.numvm += 1
            if path == parent.name:
                vmlist.update({self.numvm: {'vm': parent, 'folder': '/'}})
                self.log.debug (object_type+ " "+str(self.numvm)+ ' /'+parent.name)
            else:
                self.log.debug (object_type + " " + str(self.numvm) + ' '+path+' /' + parent.name)
        return vmlist

    def IsLinkedTo (self, labela, propa, labelb, propb):
        # return the node labela if labela is linked to labelb with propa and propb
        # return None if not linked or don't exists
        try:
            return list(self.graph.run('match (a:'+labela+' '+propa+' )--(b:'+labelb+' '+propb+' ) return a'))[0]['a']
        except IndexError:
            return None
