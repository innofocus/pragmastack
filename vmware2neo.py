#!/usr/bin/env python
#
# cpaggen - May 16 2015 - Proof of Concept (little to no error checks)
#  - rudimentary args parser
#  - GetHostsPortgroups() is quite slow; there is probably a better way
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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

def printdebug (txt):
    global DEBUG
    if DEBUG:
        print(txt)


def GetVMHosts(content):
    print("Getting all ESX hosts ...")
    host_view = content.viewManager.CreateContainerView(content.rootFolder,
                                                        [vim.HostSystem],
                                                        True)
    obj = [host for host in host_view.view]
    host_view.Destroy()
    return obj


def GetVMs(content):
    print("Getting all VMs ...")
    vm_view = content.viewManager.CreateContainerView(content.rootFolder,
                                                      [vim.VirtualMachine],
                                                      True)
    obj = [vm for vm in vm_view.view]

    vm_view.Destroy()
    return obj

def GetHostsPortgroups(hosts):
    print("Collecting portgroups on all hosts. This may take a while ...")
    hostPgDict = {}
    for host in hosts:
        pgs = host.config.network.portgroup
        hostPgDict[host] = pgs
        print("\tHost {} done.".format(host.name))
    print("\tPortgroup collection complete.")
    return hostPgDict


def PrintVmInfo(vm):
    vmPowerState = vm.runtime.powerState
    print("Found VM:", vm.name + "(" + vmPowerState + ")")
    GetVMInfo(vm)

def GetVMDisks(vm):
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

def GetVMNics(vm):
    global dvs_list
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
        printdebug ('No IP address')
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
                # print ('dvs_list :'),
                # pprint.pprint(dvs_list)
                # print ('dvsUuid :'+str(dvsUuid))
                # print ('portGroupKey :', str(portGroupKey))
                if (str(dvsUuid) in dvs_list) and (str(portGroupKey) in dvs_list[str(dvsUuid)]):
                        portGroup = dvs_list[str(dvsUuid)][str(portGroupKey)]['portGroup']
                        vlanId = dvs_list[str(dvsUuid)][str(portGroupKey)]['vlanId']
                        vSwitch = dvs_list[str(dvsUuid)][str(portGroupKey)]['vSwitch']
                else:
                    try:
                        dvs = content.dvSwitchManager.QueryDvsByUuid(dvsUuid)
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
                        dvs_list[str(dvsUuid)]={ str(portGroupKey) : { 'portGroup' : portGroup, 'vlanId' : vlanId, 'vSwitch' : vSwitch}}
            else:
                portGroup = dev.backing.network.name
                vmHost = vm.runtime.host
                # global variable hosts is a list, not a dict
                host_pos = hosts.index(vmHost)
                viewHost = hosts[host_pos]
                # global variable hostPgDict stores portgroups per host
                pgs = hostPgDict[viewHost]
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

def GetVMFolder(vm):
    foldername=''
    while hasattr(vm, 'parent'):
        try:
            foldername=vm.parent.name+'/'+foldername
            vm=vm.parent
        except AttributeError:
            foldername='/'
            break

    return { 'folder': foldername }

def GetVMInfo(vm):
    global numvm, content
    numvm+=1
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
    printdebug ('details done')
    details.update(GetVMNics(vm))
    printdebug('GetVMNics done')
    details.update(GetVMDisks(vm))
    printdebug('GetVMDisks done')
    details.update(GetVMFolder(vm))
    printdebug('GetVMFolder done')
    printdebug ("VM "+str(numvm))
    for name, value in details.items():
        print("  {0:{width}{base}}: {1}".format(name, repr(value), width=25, base='s'))

    # experimental
    if not re.match('windows',details['guest OS name'].lower()):
        print ('Testing Linux connect')


    return details


def GetChilds (parent, path):
    global numvm
    object_type = parent.__class__.__name__
    vmlist={}
    if (not (object_type == 'vim.VirtualMachine')) and hasattr(parent,'childEntity'):
        printdebug ('Folder '+ parent.name)
        for child in parent.childEntity:
            if child.__class__.__name__ == 'vim.VirtualMachine':
                numvm+=1
                vmlist.update({numvm : { 'vm' : child , 'folder' : path}})
                #print (child.__class__.__name__, " ", numvm, path+'/'+child.name)
            else:
                printdebug ('Folder '+child.name)
                vmlist.update(GetChilds(child, path+'/'+child.name))
    elif object_type == 'vim.VirtualMachine':
        numvm += 1
        if path == parent.name:
            vmlist.update({numvm: {'vm': parent, 'folder': '/'}})
            printdebug (object_type+ " "+str(numvm)+ ' /'+parent.name)
        else:
            printdebug (object_type + " " + str(numvm) + ' '+path+' /' + parent.name)
    return vmlist

def IsLinkedTo (labela, propa, labelb, propb):
    # return the node labela if labela is linked to labelb with propa and propb
    # return None if not linked or don't exists
    try:
        return list(graph.run('match (a:'+labela+' '+propa+' )--(b:'+labelb+' '+propb+' ) return a'))[0]['a']
    except IndexError:
        return None


def main():
    global content, hosts, hostPgDict, numvm, DEBUG, dvs_list, content

    # liste des ditributed vswitch pour eviter les multiples polls
    dvs_list = { 'dvsuuid' : { 'portgroupkey' : { 'vlanid' : '', 'porgroup' : '', 'vswitch' : ''}}}

    DEBUG = True
    parser = argparse.ArgumentParser(description="Tool to export vmware infra metadatas to neo4j",
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=textwrap.dedent('''Exemples : <tobedefined>'''))
    parser.add_argument('--username', dest="username", help="Account Username for vcenter Login")
    parser.add_argument('--password', dest="password", help="Account Password for vcenter Login")
    parser.add_argument('--host', dest="host", help="adresse du vcenter")
    parser.add_argument('--port', dest="port", help="port du serveur vcenter")
    parser.add_argument('--neousername', dest="neousername", help="Account Username for neo4j Login")
    parser.add_argument('--neopassword', dest="neopassword", help="Account Password for neo4j Login")
    parser.add_argument('--neohost', dest="neohost", help="adresse du neo4j")
    parser.add_argument('--neoport', dest="neoport", help="port du serveur neo4j")
    parser.add_argument('--reset', dest="reset", action='count', help="clear database")
    parser.add_argument('-v', dest="verbose", action='count', help="mode verbeux")


    options = parser.parse_args()

    pprint.pprint(options)

    context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    context.verify_mode = ssl.CERT_NONE
    serviceInstance = SmartConnect(host=options.host,
                                    user=options.username,
                                    pwd=options.password,
                                    port=int(options.port),
                                    sslContext=context)
    atexit.register(Disconnect, serviceInstance)
    content = serviceInstance.RetrieveContent()
    hosts = GetVMHosts(content)
    hostPgDict = GetHostsPortgroups(hosts)
    numvm=0

    exit(1)

    # http://pubs.vmware.com/vsphere-55/topic/com.vmware.wssdk.apiref.doc/vim.SearchIndex.html
    #search_index = serviceInstance.content.searchIndex
    #vms = GetVMs(content)
    v=None
    #v=search_index.FindByUuid(None, "501f02de-8f74-e50d-feff-f2ae5910f03c", True, True)
    #pprint.pprint(vm)

    vms={}

    for en in content.rootFolder.childEntity:
        print ("Datacenter ", en.name)
        vms.update({en.name : {}})
        for sf in en.vmFolder.childEntity:
            vms[en.name].update(GetChilds(sf,sf.name))

    #pprint.pprint(vms)
    printdebug ('search index done')

    # on insert tout dans neo
    url = os.environ.get('GRAPHENEDB_URL', 'http://'+options.neohost+':'+options.neoport)
    graph = Graph(url + '/db/data/', username=options.neousername, password=options.neopassword)

    if options.reset:
        graph.delete_all()

    printdebug ('graph init done')
    for dc in vms:
        pprint.pprint(vms[dc])
        neo_dc=Node('Datacenter', name=dc)
        graph.merge(neo_dc)
        for vm_obj in vms[dc]:
            pprint.pprint(vms[dc][vm_obj])
            folder=vms[dc][vm_obj]['folder']
            vm=GetVMInfo(vms[dc][vm_obj]['vm'])
            #pprint.pprint(vm)
            neo_vm=Node('Server', name=vm['name'], hardware='VM', cpu=vm['num cpu'], ram=vm['memory MB'],
                        disk=vm['Disks']['totalsizeKB'], powerstate=vm['power state'], annotation=unicode(vm['annotation']),
                        os=vm['guest OS name'], tools_version=vm['tools version'], tools_status=vm['tools status'], folder=unicode(folder))
            graph.merge(neo_vm)
            link=Relationship(neo_vm,'is_on',neo_dc, primary=True)
            graph.merge(link)
            # we get rid of totalsizeKB
            vm['Disks'].pop('totalsizeKB')

            for d in vm['Disks']:
                pprint.pprint(vm['Disks'][d]['fileName'])
                # no merge since disks are uniques
                if re.match('vim.vm.device.',vm['Disks'][d]['device type']):
                    disktype = vm['Disks'][d]['device type'].replace('vim.vm.device.','')
                else:
                    disktype = 'NoDiskType'
                fileName = vm['Disks'][d]['fileName'].split(' ')
                if len(fileName) != 2:
                    diskname = disktype+"-"+vm['name']
                    dsname = "None"
                else:
                    diskname=fileName[1]
                    dsname=fileName[0]
                neo_disk = Node('Disk', name=diskname, sizeKB=str(vm['Disks'][d]['sizeKB']), type=disktype)
                graph.merge(neo_disk)
                link=Relationship(neo_vm,'uses',neo_disk)
                graph.merge(link)
                dataStore = vm['Disks'][d]['fileName'].split(' ')[0]

                # on ajoute le datastore sur le DC possedant le disk
                # todo : cleanup this code !
                neo_ds = Node ('Datastore', name = dsname)
                graph.merge(neo_ds)
                link=Relationship(neo_disk, 'is_on', neo_ds, primary=True)
                graph.merge(link)
                link=Relationship(neo_ds,'is_on',neo_dc)
                graph.merge(link)

            # adding ESX Hostname and link it to it
            neo_host=Node('Host', name=vm['host name'])
            graph.merge(neo_host)
            link=Relationship(neo_vm,'is_on',neo_host)
            graph.merge(link)
            link=Relationship(neo_host,'is_on',neo_dc, primary=True)
            graph.merge(link)

            # recreate subfolders hierarchy
            parent=neo_dc
            # si le folder n'est pas encore enregistr'e
            for level in folder.split('/'):
                isnew=True
                for p in graph.find('Folder', 'name', level):
                    if graph.match(start_node=parent, end_node=p):
                       isnew=False
                       parent=p
                       break
                if isnew:
                    neo_pnode = Node('Folder', name=level)
                    # ici on fait un create car plusieurs folder de meme nom dans des folders differents ok
                    graph.create(neo_pnode)
                    graph.create(Relationship(neo_pnode, 'is_on', parent))
                    parent=neo_pnode

            # on link la VM sur le dernier niveau de folder
            graph.create(Relationship(neo_vm,'is_on',parent))

            for nic in vm['Nics']:
                neo_nic=Node('Nic', name=vm['Nics'][nic]['mac'])
                graph.merge(neo_nic)
                link=Relationship(neo_vm,'have',neo_nic)
                graph.merge(link)
                neo_switch=Node('Switch', name=vm['Nics'][nic]['vswitch'])
                graph.merge(neo_switch)
                link=Relationship(neo_switch,'is_on',neo_dc, primary=True)
                graph.merge(link)
                printdebug("Vlan : "+vm['Nics'][nic]['portgroup'])
                neo_vlan=Node('Vlan', name=vm['Nics'][nic]['portgroup'], id=vm['Nics'][nic]['vlanid'])
                graph.merge(neo_vlan)
                link=Relationship(neo_vlan,'is_on',neo_switch)
                graph.merge(link)
                link=Relationship(neo_nic,'is_on',neo_switch)
                graph.merge(link)
                link=Relationship(neo_nic,'is_on',neo_vlan)
                graph.merge(link)
                if 'addresses' in vm['Nics'][nic]:
                    printdebug("Ajout adresses IP")
                    for a in vm['Nics'][nic]['addresses']:
                        if re.match(".*:.*",vm['Nics'][nic]['addresses'][a]['ip']):
                            version='ipv6'
                        else:
                            version='ipv4'
                        neo_ip=Node('ip', name=vm['Nics'][nic]['addresses'][a]['ip'], prefix=vm['Nics'][nic]['addresses'][a]['prefix'], version=version)
                        graph.merge(neo_ip)
                        link=Relationship(neo_ip,'is_on',neo_vlan)
                        graph.merge(link)
                        link=Relationship(neo_ip,'uses',neo_nic)
                        graph.merge(link)


# Main section
if __name__ == "__main__":
    sys.exit(main())
