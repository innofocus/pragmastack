#!/usr/bin/python
import urllib
from xml.etree import ElementTree
from netaddr import *
result=[]
tumple=()

urllistinterface = "https://pa4-fw1-prd.canaltp.prod/api/?type=config&action=get&xpath=/config/devices/entry[@name=%27localhost.localdomain%27]/network/interface/aggregate-ethernet/entry[@name=%27ae1%27]/layer3/units&key=************************"
contentinterface = urllib.request.urlopen(urllistinterface)
el=ElementTree.parse(contentinterface)
root=el.getroot()
val=root.findall(".//units")
for node in val:
 try:
 #print node.attrib('name').text
 #print node.tag
 #print node.attrib
  for subnode in node.findall('entry'):
   try:
    #################
    interface= subnode.get('name')
#    print interface
    #################
    comment= (subnode.find("comment")).text
#    print comment
    ################
   except:
    comment="vide"
   ###############
   for ip in subnode.find('ip'):
    try:
    #############
     gateway=ip.get('name')
     network=str(IPNetwork(gateway).cidr)
 #    print network
     gw=str(IPNetwork(gateway).ip)
 #    print gw
    #############
    except:
     gw="vide"
    ###############
    tag= (subnode.find("tag")).text
#    print tag 
    ###############
    urllistmacaddress = ("https://pa4-fw1-prd.canaltp.prod/api/?type=op&cmd=%3Cshow%3E%3Carp%3E%3Centry+name+%3D+%27ae1."+tag+"%27%2F%3E%3C%2Farp%3E%3C%2Fshow%3E&key=**************")
    contentarp = urllib.request.urlopen(urllistmacaddress)
    macel=ElementTree.parse(contentarp)
    rootmac=macel.getroot()
    valmac=rootmac.findall(".//entry")
    for mac in valmac:
     #############
     macipaddr=(mac.find('ip')).text
#     print macipaddr
     #############
     macaddr=(mac.find('mac')).text
#     print macaddr
     #############
     
#     print "--------------"  
#     print interface
#     print comment  
#     print network
#     print gw
#     print tag
#     print macipaddr
#     print macaddr
#     print "---------------"
     tumple=({'Vlan':{'name':comment,'id':tag}},
             {'Ip':{'name':macipaddr}},
             {'Nic': {'name':macaddr,'version':'ipv4'}},
             {'Network':{'name':network}},)
     result.append(tumple)
 except:
  print "Le champ interface est vide ou une erreur dans le flux. verifier l'url"

print (result)

