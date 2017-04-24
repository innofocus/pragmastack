#!/usr/bin/env python

from py2neo import Graph, Node, Relationship
import os
import re
import csv
import json
import xlsxwriter
import argparse
import textwrap
import yaml
from CMgDB.CMgDB import CMgDB, liveupdate

parser = argparse.ArgumentParser(description="Agregation de CMDB et fichiers resources pour sortie Excel BillCloud",
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=textwrap.dedent('''Enjoy !'''))
parser.add_argument('--config', dest="config", help="Configuration file in Yaml format")
parser.add_argument('--backup', dest="backup", help="fichier backup.csv")
parser.add_argument('--nasvolumes', dest="nasvolumes", help="fichier nasvolumes.csv")
parser.add_argument('--percentiles', dest="percentiles", help="fichier percentiles.csv")
parser.add_argument('--dirref', dest="dirref", default='datas/referentiels/', help="dossier des referentiels")
parser.add_argument('--dirres', dest="dirres", default='datas/resources/', help="dossier des ressources")
parser.add_argument('--xlsfile', dest="xlsfile", default='billcloud.xlsx', help="fichier excel de sortie")
parser.add_argument('-v', dest="verbose", action='count', help="mode verbeux")

options = parser.parse_args()

n = CMgDB(options.config)

dirref=options.dirref
dirres=options.dirres
xlsfile=options.xlsfile

workbook = xlsxwriter.Workbook(xlsfile)
worksheet = workbook.add_worksheet('Prix')

tarifs = (
    ['Type', 'Production', 'Horsproduction'],
    ['Linux', 25, 15],
    ['Windows', 55, 45],
    ['vCPU',  15, 10],
    ['GoRam',  5,1],
    ['Disk SAN', 0.5, 0.3],
    ['Disk NAS', 0.5,0.3],
    ['Backup Go', 0.52,0.52],
    ['Net Mbps', 25, 25],
    ['Host Hardware', 0.4, 0.4]
)

# Start from the first cell. Rows and columns are zero indexed.
row = 0
col = 0

worksheet.write_row(0,0,tarifs[0])
row+=1

# Iterate over the data and write it out row by row.
for item, costp, costh in (tarifs[1:]):
    worksheet.write(row, col,     item)
    worksheet.write_number(row, col + 1, costp)
    worksheet.write_number(row, col + 2, costh)
    row += 1


cypher='''
match (server:Server)
optional match (server:Server)--(dc:Datacenter)
optional match (server:Server)--(pf:Platform)
optional match (server:Server)--(client:Client)
optional match (server:Server)--(env:Environment)
optional match (server:Server)--(pnl:Pnl)
optional match (server:Server)--(af:Affaire)

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
 case when server.os=~'.*icrosoft.*' or server.os=~'.*indows.*' then 'Windows' else 'Linux' end as os_type,
 (toInt(server.cpu)-1) as cpu_addon,
 round((toInt(server.ram)-2048)/1024) as ram_addon,
 case when env.name='Production' then
    case when server.os=~'.*icrosoft.*' or server.os=~'.*indows.*' then '=Prix!$B$3' else '=Prix!$B$2' end
 else
    case when server.os=~'.*icrosoft.*' or server.os=~'.*indows.*' then '=Prix!$C$3' else '=Prix!$C$2' end
 end as baseline,
 case when env.name='Production' then '=Prix!$B$4' else '=Prix!$C$4' end as base_cpu,
 case when env.name='Production' then '=Prix!$B$5' else '=Prix!$C$5' end as base_ram,
 case when env.name='Production' then '=Prix!$B$6' else '=Prix!$C$6' end as base_san,
 server.price as price,
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
 os_type,
 cpu_addon,
 ram_addon,
 baseline,
 base_cpu,
 base_ram,
 base_san,
 price,
 annotation,
 role
'''
list=n.graph.run(cypher).data()

vmws = workbook.add_worksheet('Extract')
header = ['pnl', 'client', 'affaire', 'platform', 'env', 'datacenter', 'type', 'name', 'role', 'annotation', 'powerstate', 'cpu', 'ram', 'diskGB', 'os_type',
          'baseline', 'cpu_addon', 'ram_addon',
          'base_cpu', 'base_ram', 'base_san', 'base_nas', 'base_bkp', 'net_Mbps', 'base_net', 'price']
vmws.write_row(0,0,header)
row=1
for i in list:
    r=str(row+1)
    if i['type'] == 'VM' or i['type'] == 'VM RDM':
        vmws.write_row(row, 0,
                       [i['pnl'], i['client'], i['affaire'], i['platform'], i['env'], i['datacenter'], i['type'], i['name'], i['role'], i['annotation'], i['powerstate'],
                        i['cpu'], i['ram'], i['diskGB'], i['os_type'],
                        i['baseline'], i['cpu_addon'], i['ram_addon'], i['base_cpu'], i['base_ram'], i['base_san'],
                        "", "", "", "",
                        "=P2+Q2*S2+R2*T2+N2*U2".replace('2',r)])
    else :
        # corrected_price=i['price'].replace(',','.')
        corrected_price = i['price']
        print (str(i))
        vmws.write_row(row, 0,
                       [i['pnl'], i['client'], i['affaire'], i['platform'], i['env'], i['datacenter'], i['type'], i['name'], i['role'], i['annotation'], i['powerstate'],
                        int(i['cpu']), int(i['ram']), i['diskGB'], i['os_type'],
                        corrected_price, "", "", "", "", i['base_san'],
                        "", "", "", "",
                        "=P2+N2*U2".replace("2",r)])
    row+=1


# en attendant de mettre les platforms et les client en database ....

# on pose le client correspondant `a la plateforme
pftoclient={}
testcsv=open(dirref+'pf-clients.csv','r')
csvreader=csv.reader(testcsv, delimiter=';')
# on saute le header
csvreader.next()
for i in csvreader:
    pftoclient.update({i[0] : i[1]})
testcsv.close()


# integration du backup
bkp={}
bkpcsv=open(options.backup,'r')
csvreader=csv.reader(bkpcsv, delimiter=';')
#on vire le header
csvreader.next()
for i in csvreader:
    r=str(row+1)
    vmws.write_row(row, 0,
                   [pftoclient[i[1]], "", "", i[1], i[2], "", i[3], i[4], "", "", "", "", "", i[5], "",
                    "", "", "", "", "", "",
                    "", '=Prix!$C$6', "", "",
                    '=W' + r + '*N' + r])
    row+=1
bkpcsv.close()

# volum`etrie NAS
# on ouvre le traducteur de nom de platform
with open(dirref+'NAS-pf.json', 'r') as NASpffile:
    NASpf = json.load(NASpffile)
    NASpffile.close()

NAS={}
#on recupere les premiers caract`eres avec -,_ ou;
reg=re.compile('-|_|;')

NASvol=open(options.nasvolumes,'r')
NASvolreader=csv.reader(NASvol, delimiter=';')
#pas de header
for i in NASvolreader:
    l=reg.split(i[0])
    pf=NASpf[l[0]].upper()
    r=str(row+1)
    if (i[1]=='Production'):
        price='=Prix!$B$7'
    else:
        price='=Prix!$C$7'
    vmws.write_row(row, 0,
                   [pftoclient[pf], "", "", pf, i[1], "", "NAS", i[0], "", "", "", "", "", float(i[3])/1024, "",
                    "", "", "", "", "", "",
                    price, "", "", "",
                    '=V' + r + '*N' + r])
    row+=1
bkpcsv.close()


#on recupere les percentiles
# on pose la plateforme  correspondant `a la sonde
sondetopf={}
pfsondecsv=open(dirref+'pf-sonde.csv','r')
csvreader=csv.reader(pfsondecsv, delimiter=';')
# on saute le header
csvreader.next()
for i in csvreader:
    sondetopf.update({i[1] : i[0]})
pfsondecsv.close()

#on recupere les premiers caract`eres avec -,_ ou;
PRTGvol=open(options.percentiles,'r')
PRTGvolreader=csv.reader(PRTGvol, delimiter=';')
#on saute le header
PRTGvolreader.next()
for i in PRTGvolreader:
    price='=Prix!$B$9'
    r = str(row + 1)
    sonde=i[1].replace("VIP LC ","")
    #print ("Row"+r+" Sonde "+sonde+" "+i[2]+" "+i[3])
    vmws.write_row(row, 0,
                   [pftoclient[sondetopf[sonde]], "", "", sondetopf[sonde], 'Production', "", "NETWORK", sonde, "", "", "", "", "", "", "",
                    "", "", "", "", "", "",
                    "", "", (float(i[2].replace(',','.'))+float(i[3].replace(',','.')))/1000, price,
                    '=X' + r + '*Y' + r])
    row+=1
bkpcsv.close()

workbook.close()