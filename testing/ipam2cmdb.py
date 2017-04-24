#!/usr/bin/env python

import os, re
from py2neo import Graph, Node, Relationship
import csv
from lxml import etree
import requests
import argparse
import textwrap
import pprint


parser = argparse.ArgumentParser(description="IPAM to CMDB",
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=textwrap.dedent('''Enjoy !'''))
parser.add_argument('--neousername', dest="neousername", help="Account Username for neo4j Login")
parser.add_argument('--neopassword', dest="neopassword", help="Account Password for neo4j Login")
parser.add_argument('--neohost', dest="neohost", help="adresse du neo4j")
parser.add_argument('--neoport', dest="neoport", help="port du serveur neo4j")
parser.add_argument('--username', dest="username", help="Account Username for Ipam Login")
parser.add_argument('--password', dest="password", help="Account Password for Ipam Login")
parser.add_argument('--host', dest="host", help="adresse du Ipam")
parser.add_argument('--port', dest="port", default=80, help="port du Ipam")
parser.add_argument('--type', dest="type", help="soit host, net ou vlans")
parser.add_argument('--dump', dest="dump", action='count', help="only dump Ipam, do nothing")
parser.add_argument('--xlsfile', dest="xlsfile", default='datas/Ipam-CMDB.xlsx', help="fichier excel de sortie")
parser.add_argument('-v', dest="verbose", action='count', help="mode verbeux")

options = parser.parse_args()

# graph opening
url = os.environ.get('GRAPHENEDB_URL', 'http://' + options.neohost + ':' + options.neoport)
graph = Graph(url + '/db/data/', username=options.neousername, password=options.neopassword)

# export des reseaux et recup url du fichier csv
url="http://"+options.host+":"+str(options.port)+"/res/ip_export.cgi"
header={ "Cookie" : "GestioIPLang=en; EntriesRedPorPage=500" }
data={ "export_radio":"all","ipv4":"ipv4","export_type":options.type,"client_id":"1","B2":"export"}
f=requests.post(url, auth=(options.username, options.password), headers=header, data=data)
print ('Status :'+str(f.status_code))

root = etree.HTML(f.text)
cible = root.xpath('//*[@id="Inhalt"]/p[3]/span[1]/a[1]')
ipamcsvurl = cible[0].attrib['href']

# recherche du reseau network/prefix dans l'export
csvfile = requests.get(ipamcsvurl, auth=(options.username, options.password) )
encoding=csvfile.encoding

reader = csv.DictReader(csvfile.text.encode(encoding).split("\n"), delimiter=",")

if options.type == 'vlans' and not options.dump:
    for row in reader:
        neo_vlan=Node('Vlan', name=row['name'], id=row['number'], annotation=row['comment'])
        graph.merge(neo_vlan)

elif options.type == 'net' and not options.dump:
    for row in reader:
        neo_network = Node('Network', name=row['network'], cider=row['BM'], category=row['category'], annotation=row['comment'])
        graph.merge(neo_network)

        if re.match('[0-9]* - V-.*',row['vlan']):
            vlancell=row['vlan'].split(' - ')
            vlanname = vlancell[1]
            vlanid = vlancell[0]
        else:
            vlanname = ""
            vlanid = ""
        if (vlanname == "") and (re.match('V-',row['description'])):
            vlanname = row['description']
            vlanid = "unknown from ipam"
        if vlanname == "":
            print ('No vlan information for network : '+row['network'])
            neo_network['annotation']=row['comment']+' - '+row['description']
            continue
        neo_vlan = Node('Vlan', name = vlanname, id=vlanid)
        graph.merge(neo_vlan)
        link=Relationship(neo_network,'lives_on',neo_vlan)
        graph.merge(link)

elif options.type == 'host' and not options.dump:
    for row in reader:
        # un hostname est une instance d'OS
        # il est relie a une ip
        # pour le cas
        neo_hostname = Node('Hostname', name=row['hostname'], annotation=row['description']+' - '+row['comment'])
        graph.merge(neo_hostname)

        # on relie l'ip
        neo_ip = Node('ip', name=row['IP'], annotation=row['description']+' - '+row['comment'])
        graph.merge(neo_ip)
        link=Relationship(neo_hostname,'configures',neo_ip, primary=True)

        graph.merge(link)
        neo_network = graph.find_one('Network', 'name', row['network'])
        if neo_network == None:
            print (' Network inconnu :'+str(row['network']))
            neo_network = Node('Network', name=str(row['network']), cider=str(row['BM']))
            graph.merge(neo_network)
        if neo_network['cider'] == row['BM']:
            # le network est ok
            link=Relationship(neo_ip,'is_on',neo_network)
            graph.merge(link)
         else:
            # aye aye
            print (" Aye, le network de "+str(row['hostname'])+":"+str(row['network'])+" a deux cider differents:"+str(neo_network['cider'])+"::"+str(row['BM']))

        # on cherche a relier avec un server sur
        # 1 - le hostname
        # 2 - l ip
        print ('Lookup server on hostname : '+row['hostname']),
        # si il y a un . , on cherche le sur le shortname
        short=row['hostname'].split('.')[0]
        neo_srv = graph.run("match (s:Server) where upper(s.name)=~\".*"+short.upper()+".*\" return s limit 1").evaluate()
        if neo_srv:
            print ('found : ' + neo_srv['name'])
        else:
            print (' .. no server found from shortname'),
            neo_srv = graph.run("match (s:Server)-->(n:Nic)-->(i:ip) where i.name=\"" + row['IP'] + "\" return s").evaluate()
            if neo_srv :
                print ('found : ' + neo_srv['name'])
            else:
                print (' .. no ip found')



else:
    for row in reader:
        #pprint.pprint (row)
        for obj in row.keys():
            print (str(obj)+':'),
            print (str(row[obj])+','),
        print

