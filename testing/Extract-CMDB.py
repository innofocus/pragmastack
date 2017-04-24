#!/usr/bin/env python

from py2neo import Graph
import os
import xlsxwriter
import argparse
import textwrap
import yaml

parser = argparse.ArgumentParser(description="Agregation de CMDB et fichiers resources pour sortie Excel BillCloud",
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=textwrap.dedent('''Enjoy !'''))
parser.add_argument('--config', dest="config", help="Configuration file in Yaml format")
parser.add_argument('--neousername', dest="neousername", help="Account Username for neo4j Login")
parser.add_argument('--neopassword', dest="neopassword", help="Account Password for neo4j Login")
parser.add_argument('--neohost', dest="neohost", help="adresse du neo4j")
parser.add_argument('--neoport', dest="neoport", help="port du serveur neo4j")
parser.add_argument('--backup', dest="backup", help="fichier backup.csv")
parser.add_argument('--nasvolumes', dest="nasvolumes", help="fichier nasvolumes.csv")
parser.add_argument('--percentiles', dest="percentiles", help="fichier percentiles.csv")
parser.add_argument('--dirref', dest="dirref", default='datas/referentiels/', help="dossier des referentiels")
parser.add_argument('--xlsfile', dest="xlsfile", default='datas/Extract-CMDB.xlsx', help="fichier excel de sortie")
parser.add_argument('-v', dest="verbose", action='count', help="mode verbeux")

options = parser.parse_args()

config_f = open(options.config)
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
          'port': options.neoport or config_neo_db['port'],
          'username': options.neousername or config_neo_db['username'],
          'password': options.neopassword or config_neo_db['password']
          }

url = os.environ.get('GRAPHENEDB_URL', 'http://' + neo_db['host'] + ':' + str(neo_db['port']))
graph = Graph(url + '/db/data/', username=neo_db['username'], password=neo_db['password'])

dirref=options.dirref
xlsfile=options.xlsfile

workbook = xlsxwriter.Workbook(xlsfile)

cypher='''
match (server:Server)
match (server:Server)
optional match (server:Server)--(dc:Datacenter)
optional match (server:Server)--(pf:Platform)
optional match (server:Server)--(client:Client)
optional match (server:Server)--(env:Environment)
optional match (server:Server)--(pnl:Pnl)
optional match (server:Server)--(af:Affaire)
optional match (server:Server)-[*1..2]->(vlan:Vlan)
with
 pnl.name as pnl,
 client.name as client,
 af.name as affaire,
 pf.name as platform,
 env.name as env,
 dc.name as datacenter,
 server.hardware as type,
 server.name as name,
 server.powerstate as powerstate,
 server.cpu as cpu,
 server.ram as ram,
 round(toInt(server.disk)/1024/1024) as diskGB,
 server.os as os,
 server.folder as folder,
 case when server.os=~'.*icrosoft.*' then 'Windows' else case when server.os=~'.*nux.*' then 'Linux' else 'Other' end end as os_type,
 vlan.name as vlan,
 server.annotation as annotation,
 server.role as role
return distinct
 pnl,
 client,
 affaire,
 platform,
 env,
 datacenter,
 type,
 name,
 powerstate,
 cpu,
 ram,
 diskGB,
 os,
 os_type,
 folder,
 vlan,
 annotation,
 role
'''
list_ci=graph.run(cypher).data()

worksheet = workbook.add_worksheet('Extract')
header = ['pnl', 'client', 'affaire', 'platform', 'env', 'datacenter', 'type', 'name', 'annotation', 'powerstate', 'cpu', 'ram', 'diskGB', 'os_type',
          'os','folder', 'vlan', 'role']

worksheet.write_row(0,0,header)
row=1
for i in list_ci:
    r=str(row+1)
    #print (i['name'])
    worksheet.write_row(row, 0,
                       [i['pnl'], i['client'], i['affaire'], i['platform'], i['env'], i['datacenter'], i['type'], i['name'], i['annotation'], i['powerstate'],
                        i['cpu'], i['ram'], i['diskGB'], i['os_type'], i['os'], i['folder'], i['vlan'], i['role']])
    row+=1