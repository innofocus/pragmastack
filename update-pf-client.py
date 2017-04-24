from py2neo import Graph, Node, Relationship
from passlib.hash import bcrypt
from datetime import datetime
import os
import uuid
import re
import csv
import pprint
import json
import argparse
import textwrap

parser = argparse.ArgumentParser(description="Tool to export vmware infra metadatas to neo4j",
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=textwrap.dedent('''Exemples : <tobedefined>'''))
parser.add_argument('--neousername', dest="neousername", help="Account Username for neo4j Login")
parser.add_argument('--neopassword', dest="neopassword", help="Account Password for neo4j Login")
parser.add_argument('--neohost', dest="neohost", help="adresse du neo4j")
parser.add_argument('--neoport', dest="neoport", help="port du serveur neo4j")
parser.add_argument('-v', dest="verbose", action='count', help="mode verbeux")

options = parser.parse_args()
url = os.environ.get('GRAPHENEDB_URL', 'http://' + options.neohost + ':' + options.neoport)
graph = Graph(url + '/db/data/', username=options.neousername, password=options.neopassword)


list={}
testcsv=open('pf-clients.csv','r')
csvreader=csv.reader(testcsv, delimiter=';')
# on saute le header
csvreader.next()
for i in csvreader:
    list.update({i[0] : i[1]})
testcsv.close()

pprint.pprint(list)

for pf in list:
    neo_client= Node('Compte', name=list[pf])
    graph.merge(neo_client)
    neo_pf=Node('Plateform', name=pf)
    graph.merge(neo_pf)
    link=Relationship(neo_client,'have',neo_pf)
    graph.merge(link)