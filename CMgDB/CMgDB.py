#!/usr/bin/env python
# coding=utf-8


from py2neo import Graph, Node, Relationship, watch
import os
import re
import yaml

from pprint import pprint
import  socket
import dns.resolver
import dns.reversename
from netaddr import *

import time, datetime

from probe.paloalto.fw import palo
from probe.cisco.n5k import n5k
from probe.vmware.vmware import vmware
from probe.F5.F5 import lc, adc
from probe.sheet.sheet import tablesheet

import logging
import warnings
warnings.filterwarnings('once', '.*KeyError.*',)

class CMgDB(object):
    """" class for updating neo4j database with live information gathered from infrastructure"""

    Models = [
        ('Datacenter', 'provides', 'Server'),
        ('Datacenter', 'provides', 'Host'),
        ('Datacenter', 'provides', 'Datastore'),
        ('Datacenter', 'provides', 'Folder'),
        ('Folder', 'uses', 'Folder'),
        ('Server', 'uses', 'Folder'),
        ('Datastore', 'provides', 'Disk'),
        ('Server', 'uses', 'Host'),
        ('Server', 'uses', 'Disk'),
        ('Server', 'provides', 'Os'),
        ('Server', 'abuses', 'Vlan'),
        ('Os', 'provides', 'Filesystem'),
        ('Filesystem', 'uses', 'Disk'),
        ('Filesystem', 'provides', 'Directory'),
        ('Os', 'provides', 'Software'),
        ('Software', 'uses', 'Directory'),
        ('Datacenter', 'provides', 'Switch'),
        ('Switch', 'provides', 'Vlan'),
        ('Vlan', 'provides', 'Network'),
        ('Datacenter', 'provides', 'Nic'),
        ('Nic', 'uses', 'Switch'),
        ('Nic', 'uses', 'Vlan'),
        ('Server', 'uses', 'Nic'),
        ('Os', 'provides', 'Ip'),
        ('Ip', 'uses', 'Nic'),
        ('Ip', 'uses', 'Network'),
        ('Ip', 'abuses', 'Vlan'),
        ('Router', 'provides', 'Gateway'),
        ('Switch', 'uses', 'Router'),
        ('Router', 'uses', 'Network'),
        ('Router', 'uses', 'Vlan'),
        ('Gateway', 'uses', 'Vlan'),
        ('Software', 'provides', 'Service'),
        ('Service', 'provides', 'Port'),
        ('Port', 'uses', 'Ip'),
        ('Dns', 'provides', 'Domain'),
        ('Domain', 'provides', 'Fqdn'),
        ('Fqdn', 'uses', 'Ip'),
        ('Os', 'uses', 'Domain'),
        ('Os', 'provides', 'Hostname'),
        ('Os', 'uses', 'Dns'),
        ('Os','provides','Os'),
        ('Port','uses','Port'),
        ('Hostname', 'uses', 'Ip'),
        ('Service', 'uses', 'Hostname'),
        ('Service', 'uses', 'Fqdn'),
        ('Service', 'uses', 'Ip'),
        ('Ip', 'uses', 'Fqdn'),
        ('Ip', 'uses', 'Domain'),
        ('Ip', 'uses', 'Hostname'),
        ('Ip', 'uses', 'Gateway'),
        ('Switch', 'uses', 'Ip'),
        ('Router', 'uses', 'Ip'),
        ('Server', 'uses', 'Ip'),
        ('Vcenter', 'uses', 'Ip'),
        ('Firewall', 'uses', 'Ip'),
        ('Network', 'uses', 'Gateway'),
        ('Network', 'uses','Switch'),
        ('Firewall', 'provides', 'Security'),
        ('Vlan', 'uses', 'Security'),
        ('Gateway', 'uses', 'Security'),
        ('Port','uses','Security'),
        ('Software','uses','Security'),
        ('Service','uses','Security'),
        ('Ip','uses','Security'),
        ('Vcenter','provides','Datacenter'),
        ('Site','provides','Datacenter'),
        ('Pnl','owns','Server'),
        ('Pnl','owns','Client'),
        ('Platform','owns','Server'),
        ('Platform','owns','Vlan'),
        ('Environment','owns','Server'),
        ('Environment','owns','Vlan'),
        ('Platform','owns','Environment'),
        ('Affaire','owns','Client'),
        ('Client', 'owns', 'Platform'),
        ('Client', 'owns', 'Server'),
        ('Role', 'provides', 'Server'),
        ]

    Groups =[
        ('Storage', 'groups', 'Datastore'),
        ('Storage', 'groups', 'Disk'),
        ('Storage', 'groups', 'Filesystem'),
        ('Storage', 'groups', 'Directory'),
        ('Compute', 'groups', 'Server'),
        ('Compute', 'groups', 'Os'),
        ('Compute', 'groups', 'Vcenter'),
        ('Network', 'groups', 'Ip'),
        ('Network', 'groups', 'Vlan'),
        ('Network', 'groups', 'Gateway'),
        ('Network', 'groups', 'Switch'),
        ('Network', 'groups', 'Router'),
        ('Network', 'groups', 'Firewall'),
        ('Network', 'groups', 'Nic'),
        ('Network', 'groups', 'Network'),
        ('Network', 'groups', 'Security'),
        ('Names', 'groups', 'Dns'),
        ('Names', 'groups', 'Hostname'),
        ('Names', 'groups', 'Fqdn'),
        ('Names', 'groups', 'Domain'),
        ('Application','groups','Platform'),
        ('Application', 'groups', 'Software'),
        ('Application', 'groups', 'Service'),
        ('Application', 'groups', 'Port'),
        ('Paperwork','groups','Pnl'),
        ('Paperwork', 'groups', 'Client'),
        ('Paperwork', 'groups', 'Affaire'),
        ('Paperwork', 'groups', 'Platform'),
        ('Paperwork', 'groups', 'Environment'),
        ('Site', 'groups', 'Site'),
        ('Site', 'groups', 'Datacenter')
        ]


    def __init__(self, config_file):
        self.log = logging.getLogger(__name__)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self.log.addHandler(ch)
        self.log.setLevel(logging.DEBUG)

        # config load
        self.config = self.load_config(config_file)

        if (self.config):
            neodevice = self.config['database']
            if not neodevice['debug']:
                self.log.setLevel(logging.INFO)

            self.url = os.environ.get('GRAPHENEDB_URL', 'http://' + neodevice['host'] + ':' + str(neodevice['port']))
            if neodevice['bolt']:
                self.graph = Graph(self.url + '/db/data/', username=neodevice['username'], password=neodevice['password'], bolt_port=neodevice['bolt'])
            else:
                self.graph = Graph(self.url + '/db/data/', username=neodevice['username'],
                                   password=neodevice['password'], bolt=false)
        else:
            return False

    def load_config(self,config_file):
        self.log.debug(' load_config : '+str(config_file))
        config_f = open(config_file)
        try:
            config = yaml.safe_load(config_f)
        except yaml.YAMLError as exc:
            print ("Error while parsing YAML file :")
            if hasattr(exc, 'problem_mark'):
                if exc.context != None:
                    print ('  parser says\n' + str(exc.problem_mark) + '\n  ' +
                           str(exc.problem) + ' ' + str(exc.context) +
                           '\nPlease correct data and retry.')
                else:
                    print ('  parser says\n' + str(exc.problem_mark) + '\n  ' +
                           str(exc.problem) + '\nPlease correct data and retry.')
            else:
                print ("Something went wrong while parsing yaml file")
            self.log.fatal(' Config file broken. Sorry.')
            config_f.close()
            return False
        config_f.close()
        return config

    def add_model(self, device, cleanup=False):
        """ Add probe's model entries to the main model"""
        self.log.debug( 'add_model :'+str(device))
        self.curdevice = dict(device.device)
        if not hasattr(device,'Models'):
            return False

        if cleanup:
            device.graph.delete_all()

        for (s, l, t) in device.Models:
            source = Node('Model', name=s)
            self.graph.merge(source)
            target = Node('Model', name=t)
            self.graph.merge(target)
            link = Relationship(source, l, target)
            self.graph.merge(link)

        if not hasattr(device, 'Groups'):
            return False

        for (s, l, t) in device.Groups:
            source = Node('Group', name=s)
            self.graph.merge(source)
            target = Node('Model', name=t)
            self.graph.merge(target)
            link = Relationship(source, l, target)
            self.graph.merge(link)

    def clean_nodes(self, nodes, source):
        """ Suppress nodes of labels in the list 'nodes' added by the 'source' """
        query="with "+str(list(set(nodes)))+" as list match (x)-[r]-() where labels(x) in list and x.source='"+source+"' delete x,r "
        self.graph.run(query)
        query = "with " + str(list(set(nodes))) + " as list match (x) where labels(x) in list and x.source='"+source+"' delete x "
        self.graph.run(query)

    def merge_node(self, label, **options):
        """ Add a node if new or update properties if exists"""

        self.log.debug(' merge node : '+label+' : '+str(options))
        node = Node(label, name=options.pop('name'))
        self.graph.merge(node)
        # we sets the rest of properties with push
        for p in options:
            node[p] = options[p]
        node.push()
        return node

    def link_nodes(self, *nodes, **options):
        """
        This is the pillars of the system.
        Link nodes following the Model scheme.
        :param nodes: a list of py2neo [Nodes]
        :param options: named options :
            primary=boolean to make the links as primary information (i.e. not deduced)
            create=boolean to force creation instead of merge (ex: for folder/folder)
        :return: the number of links created
        """
        labels = []
        if 'primary' in options: primary=options['primary']
        else: primary = False
        if 'create' in options : create=options['create']
        else: create = False
        # we manages all labels present in the list of nodes
        for node in nodes:
            labels.append(str(list(node.labels())[0]))
        # we search all oriented links between any of 2 nodes
        model_links = self.graph.data("with "+str(list(set(labels)))+" as list match (a:Model)-[r]->(b:Model) \
                            where a.name in list and b.name in list return a.name as labela, type(r) as rel, b.name as labelb")

        # we make all relationship in the model between each pair of nodes
        nblink = 0
        self.log.debug(' link_nodes : model_links :' + str(model_links))
        self.log.debug(' link_nodes : nodes : ' + str(nodes))
        for ml in model_links:
            for nodea in nodes:
                labela = list(nodea.labels())[0]
                for nodeb in nodes:
                    labelb = list(nodeb.labels())[0]
                    if labela == ml['labela'] and labelb == ml['labelb']:
                        nblink += 1
                        link=Relationship(nodea,ml['rel'],nodeb)
                        self.log.debug(' link_nodes : link : (' + labela + ")" + str(link) + "(" + labelb + ")")
                        if primary:
                            link['primary'] = True
                        if create:
                            self.graph.create(link)
                        else:
                            self.graph.merge(link)
        return nblink

    def unlink_label(self, label, *nodes):
        """
        Unlink the list of nodes from any node that have label label
        :param nodes: a list of py2neo [Nodes]
        :param label, the node label to unlink from
        :return: the number of links removed
        """
        self.log.debug(' unlink_label : label : nodes : '+label+' : '+str(nodes))
        # we manages all labels present in the list of nodes
        cnt=0
        for node in nodes:
            self.log.debug(' unlink_label node : '+label+' : '+str(node))
            # we search all oriented links between any of 2 nodes
            query = "match (a:"+list(node.labels())[0]+")-[r]-(b:"+label+") where a.name ='"+ node['name']+"' delete r"
            self.log.debug( ' unlink_label, query: '+query)
            self.graph.run(query)
            cnt += 1
        return cnt

    def link_networks_ip(self):
        """ Special case of the link_by """
        networks = self.graph.data("match (n:Network) return n as n")
        for net in networks:
            ipNet=IPNetwork(net['n']['name'])
            self.log.debug(' link_networks_ip : '+str(ipNet))
            self.log.debug(' link_networks_ip - ip version : IPv'+str(ipNet.version))
            if ipNet.version == 6:
                self.log.debug(" link_networks_ip - IPv6 : I would not do it")
                continue
            if ipNet.prefixlen == 0:
                self.log.debug(" link_networks_ip - prefix /0 !!!: I would not do it. no.")
                continue
            range=[]
            for i in ipNet:
                range.append(str(i))
            ips = self.graph.data("with "+str(range)+" as list match (i:Ip) where i.name in list return i")
            for i in ips:
                self.link_nodes(net['n'], i['i'])

    def link_by(self, typea, typeb, by=None):
        """ Create a relationship following the model scheme between two nodes if they are related through a third node
        If by==None, link the two nodes whatever we can find between
        """
        model = self.graph.data("match (x:Model)-[r]-(y:Model) where x.name='"+typea+"' and y.name='"+typeb+"' return x,r,y")
        for m in model:
            rel = str(m['r'].type())
            x = str(m['x']['name'])
            y = str(m['y']['name'])

            if by == None:
                n = ''
            else:
                n = ':'+by

            option=""
            if (x == 'Ip'):
                option = " where x.version='ipv4' "
            elif (y == 'Ip'):
                option = " where y.version='ipv4' "
            self.graph.run ("match (x:"+x+")--(n"+n+")--(y:"+y+") "+option+" create unique (x)-[r:"+rel+"]->(y) return r")

class liveupdate(CMgDB):
    """ class derived from CMDgDB for updating live information from devices """

    def __init__(self, config_file):
        super(liveupdate,self).__init__(config_file)
        self.curdevice = None
        self.timestamp = time.mktime(datetime.datetime.now().timetuple()) + float(datetime.datetime.now().microsecond) / 1000000

    def merge_node(self, label, **options):
        self.log.debug('label :'+label)
        self.log.debug('options :'+str(options))
        node = super(liveupdate,self).merge_node(label, **options)
        if hasattr(self,'curdevice') and not self.curdevice == None:
            node['source'] = self.curdevice['name']
        else:
            node['source'] = 'Manual'
        node['timestamp'] = self.timestamp
        node.push()
        return node

    def add_records(self, neo_dev, datas):
        """" Add to CMgDB a record ( Vlan : { name : ...}}, { Ip : { name :...}}, {}, .. )
        call to link_nodes to follow the configured Model through update_records"""
        return self.update_records(neo_dev, datas, unlink=False)

    def update_records(self, neo_dev, datas, unlink=''):
        """" Add to CMgDB a record ( Vlan : { name : ...}}, { Ip : { name :...}}, {}, .. )
        call to link_nodes to follow the configured Model
        :param:unlink = 'Empty' : unlink nodes from a null name's node, all links to nodes with its label are deleted
                      = 'All' : unlink all nodes in the record
                      = '<label>' : unlink nodes linked to node with label
                      = '' (default) dont unlink any node"""
        self.log.debug(' datas :'+str(datas))
        labelstodel=[]
        labels=[]
        unlinknode = None
        nblinks = 0
        for record in datas:
            RecordNodes = []
            self.log.debug('record :' + str(record))
            for obj in record:
                self.log.debug(' obj :' + str(obj))
                labels.append(obj.keys()[0])
                # si le node est sans nom, on zappe
                if obj.values()[0]['name'] == "":
                    labelstodel.append(obj.keys()[0])
                    continue
                for label in obj:
                    self.log.debug('   label :' + str(label))
                    self.log.debug('   name :' + str(obj[label]['name']))
                    neo_node = self.merge_node(label, name=str(obj[label]['name']))

                    for prop in obj[label]:
                        if prop != 'name':
                            self.log.debug('     prop :' + str(prop) + " : " + str(obj[label][prop]))
                            neo_node[prop] = obj[label][prop]
                    neo_node.push()

                    # on met de coté le node de unlink if ever
                    if obj.keys()[0] == unlink:
                        unlinknode = neo_node

                    RecordNodes.append(neo_node)
            self.log.debug('  update_records RecordNodes :' + str(RecordNodes))
            self.log.debug( ' update_records unlink value:'+str(unlink))
            if unlink == 'Empty':
                for l in labelstodel:
                    self.log.debug( ' update_records unlinking :'+l)
                    self.unlink_label(l,*RecordNodes)
            elif unlink == 'All':
                for l in labels:
                    self.log.debug( ' update_records unlinking :'+l)
                    self.unlink_label(l,*RecordNodes)
            elif unlink and not unlink == "":
                # we assume it is a label to unlink from
                for l in labels:
                    self.unlink_label(l, unlinknode)

            # now we link all not following the model
            # if no neo_dev, just link RecordsNodes
            if not neo_dev == None:
                nblinks = self.link_nodes(neo_dev, *RecordNodes)
            else:
                nblinks = self.link_nodes(*RecordNodes)
            self.log.debug('link_nodes :' + str(nblinks))
        return nblinks

    def from_device(self,target, cleanup=False):
        device = self.config[target]
        device['name']=target
        self.curdevice = dict(device)
        self.timestamp = time.mktime(datetime.datetime.now().timetuple()) + float(datetime.datetime.now().microsecond) / 1000000
        if device['type'] == 'n5k':
            return self.from_n5k(device,cleanup)
        elif device['type'] == 'palo':
            return self.from_pafw(device,cleanup)
        elif device['type'] == 'vmware':
            return self.from_vmware(device,cleanup)
        elif device['type'] == 'f5_lc':
            return self.from_f5lc(device,cleanup)
        elif device['type'] == 'f5_adc':
            return self.from_f5adc(device,cleanup)
        elif device['type'] == 'sheet':
            return self.from_sheet(device,cleanup)
        else:
            return None

    def from_sheet(self, device, cleanup ):
        key = device['key']
        fields = device['fields']
        table = device['table']
        create = device['create']
        pattern = device['pattern']
        sheetrecords = tablesheet(key, fields, table, create, pattern)
        return self.update_records(None, sheetrecords.get_records(), unlink=cleanup)

    def from_n5k(self,device,cleanup):
        dev_n5k = n5k(device)
        if cleanup:
            self.clean_nodes(dev_n5k.labels, device['host'])
        neo_device = self.add_device('Switch', dev_n5k)
        datas = dev_n5k.get_vlans()
        return self.add_records(neo_device, datas)

    def from_pafw(self, device,cleanup):
        fw = palo(device)
        if cleanup:
            self.clean_nodes(fw.labels, device['host'])
        neo_device = self.add_device('Firewall', fw)
        self.add_records(neo_device, fw.get_vlans())
        self.add_records(neo_device, fw.get_ips())

    def from_vmware(self,device,cleanup):
        vmw = vmware(device)
        if cleanup:
            self.clean_nodes(vmw.labels, device['host'])
        neo_device = self.add_device('Vcenter', vmw)

        # let's get a list of vms for each virtual datacenter
        vms = {}
        for en in vmw.content.rootFolder.childEntity:
            print ("Datacenter ", en.name)
            vms.update({en.name: {}})
            for sf in en.vmFolder.childEntity:
                vms[en.name].update(vmw.GetChilds(sf, sf.name))

        self.log.debug('search index done')

        # for each datacenter
        for dc in vms:
            self.log.debug(' Datacenter :'+dc)
            neo_dc = self.merge_node('Datacenter', name=dc)
            for vm_obj in vms[dc]:
                self.log.debug(str(vms[dc][vm_obj]))
                folder = vms[dc][vm_obj]['folder']
                vm = vmw.GetVMInfo(vms[dc][vm_obj]['vm'])
                neo_vm = self.merge_node('Server', name=vm['name'], hardware='VM', cpu=vm['num cpu'], ram=vm['memory MB'],
                              disk=vm['Disks']['totalsizeKB'], powerstate=vm['power state'],
                              annotation=unicode(vm['annotation']),
                              os=vm['guest OS name'], tools_version=vm['tools version'],
                              tools_status=vm['tools status'], folder=unicode(folder))
                self.link_nodes(neo_vm, neo_dc, primary=True)

                # we get rid of totalsizeKB
                vm['Disks'].pop('totalsizeKB')

                for d in vm['Disks']:
                    self.log.debug(str(vm['Disks'][d]['fileName']))
                    # no merge since disks are uniques
                    if re.match('vim.vm.device.', vm['Disks'][d]['device type']):
                        disktype = vm['Disks'][d]['device type'].replace('vim.vm.device.', '')
                    else:
                        disktype = 'NoDiskType'
                    fileName = vm['Disks'][d]['fileName'].split(' ')
                    if len(fileName) != 2:
                        diskname = disktype + "-" + vm['name']
                        dsname = "None"
                    else:
                        diskname = fileName[1]
                        dsname = fileName[0]
                    neo_disk = self.merge_node('Disk', name=diskname, sizeKB=str(vm['Disks'][d]['sizeKB']), type=disktype)
                    self.link_nodes(neo_vm, neo_disk)

                    # on ajoute le datastore sur le DC possedant le disk
                    neo_ds = self.merge_node('Datastore', name=dsname)
                    self.link_nodes(neo_disk, neo_ds, primary=True)
                    self.link_nodes(neo_ds, neo_dc)

                # adding ESX Hostname and link it to it
                neo_host = self.merge_node('Host', name=vm['host name'])
                self.link_nodes(neo_vm, neo_host)
                self.link_nodes(neo_host, neo_dc, primary=True)

                # recreate subfolders hierarchy
                parent = neo_dc
                # si le folder n'est pas encore enregistr'e
                for level in folder.split('/'):
                    if level == "": level = "/"
                    isnew = True
                    for p in self.graph.find('Folder', 'name', level):
                        if self.graph.match(start_node=parent, end_node=p):
                            isnew = False
                            parent = p
                            break
                    if isnew:
                        neo_pnode = Node('Folder', name=level)
                        # ici on fait un create car plusieurs folder de meme nom dans des folders differents ok
                        self.log.debug('register folders :'+str(neo_pnode)+" "+str(parent))
                        self.graph.create(neo_pnode)
                        self.link_nodes(neo_pnode, parent, create=True)
                        parent = neo_pnode

                # on link la VM sur le dernier niveau de folder
                self.link_nodes(neo_vm, parent, create=True)

                for nic in vm['Nics']:
                    neo_nic = self.merge_node('Nic', name=vm['Nics'][nic]['mac'])
                    self.link_nodes(neo_vm, neo_nic)
                    neo_switch = self.merge_node('Switch', name=vm['Nics'][nic]['vswitch'])
                    self.link_nodes(neo_switch, neo_dc, primary=True)
                    vlanname = vm['Nics'][nic]['portgroup']
                    vlanid = vm['Nics'][nic]['vlanid']
                    self.log.debug("Vlan : " + vlanname+"-"+vlanid)
                    if not vlanid == "NA":
                        neo_vlan = self.merge_node('Vlan', name=vlanname+"-"+vlanid, id = vlanid, friendly=vlanname)
                    else:
                        try:
                            self.log.debug("Vlan : get vlanid from graph for vlan "+vlanname)
                            neo_vlan = self.graph.find_one('Vlan', friendly=vlanname)
                            vlanid = neo_vlan['id']
                        except:
                            self.log.debug("Vlan : CANT get vlanid from graph for vlan "+vlanname)

                    if not vlanid == "NA":
                        self.link_nodes(neo_vlan, neo_switch, neo_nic)
                    else:
                        self.link_nodes(neo_switch, neo_nic)

                    if 'addresses' in vm['Nics'][nic]:
                        self.log.debug("Ajout adresses IP")
                        for a in vm['Nics'][nic]['addresses']:
                            if re.match(".*:.*", vm['Nics'][nic]['addresses'][a]['ip']):
                                version = 'ipv6'
                            else:
                                version = 'ipv4'
                            ipaddr = vm['Nics'][nic]['addresses'][a]['ip']
                            ipprefix = vm['Nics'][nic]['addresses'][a]['prefix']
                            neo_ip = self.merge_node('Ip', name= ipaddr, prefix = ipprefix, version = version)
                            neo_network = self.merge_node('Network', name=str(IPNetwork(ipaddr+"/"+str(ipprefix)).cidr))
                            if not vlanid == "NA":
                                self.link_nodes(neo_ip, neo_vlan, neo_nic, neo_network)
                            else:
                                self.link_nodes(neo_ip, neo_nic, neo_network)

    def from_f5lc(self,device,cleanup):
        f5 = lc(device)
        if cleanup:
            self.clean_nodes(f5.labels, device['host'])
        neo_device = self.add_device('F5lc', f5)
        self.add_records(neo_device, f5.get_config())
        self.log.debug(' from_f5lc : end of method')

    def from_f5adc(self,device,cleanup):
        f5 = adc(device)
        if cleanup:
            self.clean_nodes(f5.labels, device['host'])
        neo_device = self.add_device('F5adc', f5)
        self.add_records(neo_device, f5.get_config())
        self.log.debug(' from_f5adc : end of method')

    def add_device(self, devtype, device):
        """ Add device's model to the model scheme and add a node representing the device"""

        self.add_model(device)

        self.curdevice = device.device
        try:
            dev_ip = dns.resolver.query(device.device['host'])[0].address
            dev_fqdn = str(dns.resolver.query(dns.reversename.from_address(dev_ip), 'PTR')[0])
            self.log.debug('add_device devfqdn : '+str(dev_fqdn))
            #dev_name = dev_fqdn.split('.',1)[0]
            dev_name = device.device['name']
            dev_domain = dev_fqdn.split('.',1)[1]
        except:
            self.log.info('add_device devfqdn : erreur de resolution de nom')
            dev_ip = device.device['host']
            dev_name = device.device['name']
            dev_domain = 'unresolved.domain'
            dev_fqdn = dev_name+"."+dev_domain

        self.log.debug(vars())

        neo_dev = Node(devtype, name=dev_name)
        self.graph.merge(neo_dev)
        for (key,value) in device._get_device_info().items():
            neo_dev[key] = value
        neo_dev.push()

        neo_ip = Node('Ip', name=dev_ip)
        self.graph.merge(neo_ip)

        neo_fqdn = Node('Fqdn', name=dev_fqdn)
        self.graph.merge(neo_fqdn)

        neo_domain = Node('Domain', name=dev_domain)
        self.graph.merge(neo_domain)

        self.link_nodes(neo_dev, neo_ip, neo_fqdn, neo_domain)

        return neo_dev

