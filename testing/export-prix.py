from py2neo import Graph, Node, Relationship
from passlib.hash import bcrypt
from datetime import datetime
import os
import uuid
import re
import csv
import pprint
import json

url = os.environ.get('GRAPHENEDB_URL', 'http://localhost:7474')
username = 'neo4j'
password = 'neo4j2'
graph = Graph(url + '/db/data/', username=username, password=password)

with open('vmlist.json', 'r') as oldvmlistfile:
    oldvmlist = json.load(oldvmlistfile)
    oldvmlistfile.close()

#pprint.pprint(oldvmlist)

cypher='''
match (server:Server)--(pf:Plateform),(server:Server)--(client:Compte),(server:Server)--(env:Env)
with client.name as client,
 pf.name as platform,
 env.name as env,
 server.name as server,
 server.cpu as cpu,
 server.ram as ram,
 round(server.disk/1024/1024) as diskGB,
 case when server.os=~'.*icrosoft.*' then 'Windows' else 'Linux' end as os_type,
 (toInt(server.cpu)-1) as cpu_addon,
 round((toInt(server.ram)-2048)/1024) as ram_addon,
 case when env.name='Production' then 35 else 25 end as base_vm,
 case when env.name='Production' then 15 else 10 end as base_cpu,
 case when env.name='Production' then 5 else 1 end as base_ram,
 case when env.name='Production' then 0.5 else 0.3 end as base_san,
 case when server.os=~'.*icrosoft.*' then 10 else 0 end as base_license
return distinct client,
 platform,
 env,
 server,
 cpu,
 ram,
 diskGB,
 os_type,
 cpu_addon,
 ram_addon,
 base_vm,
 base_cpu,
 base_ram,
 base_san,
 base_license,
 base_vm+cpu_addon*base_cpu+ram_addon*base_ram+diskGB*base_san+base_license as price
'''
list=graph.run(cypher).data()

testcsv=open('prix_vm.csv','w')
csvwriter=csv.writer(testcsv, delimiter=';', quotechar='"')

count = 0
for i in list:
      #print(i)
      if count == 0:
             header = ['client', 'platform', 'env', 'server', 'cpu', 'ram', 'diskGB', 'os_type', 'cpu_addon', 'ram_addon', 'base_vm', 'base_cpu', 'base_ram', 'base_san', 'base_license', 'price']
             #print (header)
             csvwriter.writerow(header)
             count += 1
      csvwriter.writerow([i['client'], i['platform'], i['env'], i['server'], i['cpu'], i['ram'], i['diskGB'], i['os_type'], i['cpu_addon'], i['ram_addon'], i['base_vm'], i['base_cpu'], i['base_ram'], i['base_san'], i['base_license'], i['price']])
testcsv.close()

exit(0)

neo_vm = graph.find_one('Server', 'name', "ADAM-CUS-NJS1")
pprint.pprint(neo_vm)



for vm in oldvmlist:
    #neo_dc = Node('Datacenter', name=oldvmlist[vm]['site'])
    #graph.merge(neo_dc)
    neo_env= Node('Env', name=oldvmlist[vm]['env'])
    graph.merge(neo_env)
    #link=Relationship(neo_env,'is_on',neo_dc)
    #graph.merge(link)
    neo_client=Node('Compte', name=oldvmlist[vm]['compte'])
    graph.merge(neo_client)
    neo_pf=Node('Plateform', name=oldvmlist[vm]['PF'])
    graph.merge(neo_pf)
    link=Relationship(neo_client,'have',neo_pf)
    graph.merge(link)
    neo_vm=graph.find_one('Server','name',vm)
    if neo_vm != None:
        pprint.pprint(neo_vm)
        link=Relationship(neo_vm,'is_on',neo_env)
        graph.merge(link)
        link=Relationship(neo_vm,'is_on',neo_pf)
        graph.merge(link)
        link=Relationship(neo_vm,'is_on',neo_client)
        graph.merge(link)

