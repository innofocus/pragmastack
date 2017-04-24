#!/usr/bin/env python

import os, re
from py2neo import Graph, Node, Relationship
import csv
from lxml import etree
import requests
import argparse
import textwrap
import pprint
import json
import yaml

from CMgDB.CMgDB import CMgDB, liveupdate

parser = argparse.ArgumentParser(description="json to CMDB",
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=textwrap.dedent('''Enjoy !'''))
parser.add_argument('--config', dest="config", help="Configuration file in Yaml format")
parser.add_argument('--neousername', dest="neousername", help="Account Username for neo4j Login")
parser.add_argument('--neopassword', dest="neopassword", help="Account Password for neo4j Login")
parser.add_argument('--neohost', dest="neohost", help="adresse du neo4j")
parser.add_argument('--neoport', dest="neoport", help="port du serveur neo4j")
parser.add_argument('--username', dest="username", help="Account Username for Ipam Login")
parser.add_argument('--password', dest="password", help="Account Password for Ipam Login")
parser.add_argument('--create', dest="create", action='count', help="create every line")
parser.add_argument('--jsonfile', dest="jsonfile", default='data.json', help="fichier json en entree")
parser.add_argument('-v', dest="verbose", action='count', help="mode verbeux")

options = parser.parse_args()

config_f = open(options.config)
config={}
try:
    config = yaml.safe_load(config_f)
except yaml.YAMLError as exc:
    print ("Error while parsing YAML file:")
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
    log.fatal(' Config file broken. Sorry.')
    exit(1)
config_f.close()

# config database or parameter database
config_neo_db = {'host': None, 'port': None, 'username': None, 'password': None}
if 'database' in config:
    config_neo_db = config['database']
# override config file if ever
neo_db = {'host': options.neohost or config_neo_db['host'],
          'port': options.neoport or str(config_neo_db['port']),
          'username': options.neousername or config_neo_db['username'],
          'password': options.neopassword or config_neo_db['password']
          }

n=CMgDB(neo_db)

file = open(options.jsonfile, 'r')
jsondata = json.load(file)
file.close()

for ip in jsondata:
    neo_ip = Node ('Ip', name=ip)
    n.graph.merge(neo_ip)
    neo_vlan = n.graph.run('match (v:Vlan) where v.id="'+jsondata[ip]['vlan']+'" return v limit 1').evaluate()
    if neo_vlan == None:
        neo_vlan = Node('Vlan', name=jsondata[ip]['vlan'], id=jsondata[ip]['vlan'])
        n.graph.merge(neo_vlan)
    neo_nic = Node ('Nic', name=jsondata[ip]['mac'])
    if options.create:
        n.graph.create(neo_nic)
    else:
        n.graph.merge(neo_nic)
    n.link_nodes(neo_ip, neo_vlan, neo_nic)



