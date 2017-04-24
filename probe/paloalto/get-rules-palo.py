#!/usr/bin/python
from bs4 import BeautifulSoup
from urllib.request import urlopen, Request
import netaddr
import lxml

# Fonction pour l'appel de l'API REST via l'url
def xmlcall (uri):                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      
    xmlcontent = Request(uri,"r")
    responses = urlopen(xmlcontent)
    return responses.read()

# Fonction pour la suppresion des champs vide dans la liste
def list_members (list):
    arr=[]
    if list != None:
        for member in list:

            if member != '\n':
                #print member
                arr.append(member.string)
    return arr

# Fonction pour le matching nom (object) --> ip
def get_ipaddr():
    urli = ("https://pa4-fw2-prd.canaltp.prod/api/?type=config&action=get&xpath=/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/address/entry&key=" + key)
    xmlip = xmlcall(urli)
    x = BeautifulSoup(xmlip, features="xml")
    #print x
    ip = x.findAll("entry")
    #print ip
    for i in ip:
        ip=({'Address': {'name': i['name']}}, {'Ip': {'ip': (i.find("ip-netmask").string)}})
        #print i['name']
        #print i.find("ip-netmask").text
    return ip


# Variable Initial
key = "*******************"
url = ("https://pa4-fw2-prd.canaltp.prod/api/?type=config&action=get&xpath=/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/rulebase&key="+key)
array=[]
ctp=0
# Appel de l'api pour le listing des regles sur le firewall
xml = xmlcall(url)
soup=BeautifulSoup(xml, features="xml")


#Appel de l'api pour le listing des objet et de leur IP
urli = ("https://pa4-fw2-prd.canaltp.prod/api/?type=config&action=get&xpath=/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/address/entry&key=" + key)
xmlip = xmlcall(urli)
x = BeautifulSoup(xmlip, features="xml")
ip = x.findAll("entry")

# Boucle for pour le dico des objects
for i in ip:
    tumple = ()
    try:
        ip = ({'Address': {'name': i['name']}}, {'Ip': {'ip': (i.find("ip-netmask").string)}})
        array.append(ip)
    except:
        try:
            ip = ({'Address': {'name': i['name']}}, {'Ip': {'ip': (i.find("fqdn").string)}})
            array.append(ip)
        except:
            ip = ({'Address': {'name': i['name']}}, {'Ip': {'ip': (i.find("ip-range").string)}})
            array.append(ip)

# Pour chacune des regles present sur le firewall
for rule in soup.findAll('entry'): #,attrs={'name':"Blacklist"}):
    tumple=()
    ctp+=1

    name= rule["name"]
    desc= rule.description
    fro = list_members(rule.find('from'))
    src=list_members(rule.source)
    to=list_members(rule.to)
    dst=list_members(rule.destination)
    app=list_members(rule.application)
    svc=list_members(rule.service)
    act=rule.action

    for zonesrc in fro:
        tumple=({'Rule':{'name':ctp,'title':name}},
                {'Source':{'name':ctp}},
                {'Zone':{'name':zonesrc}})
        array.append(tumple)

    for source in src:
        tumple = ({'Rule': {'name': ctp}},
                  {'Source': {'name': ctp}},
                  {'Address': {'name': source}})
        array.append(tumple)

    for zonedst in to:
        tumple = ({'Rule': {'name': ctp}},
                  {'Destination': {'name': ctp}},
                  {'Zone': {'name': zonedst}})
        array.append(tumple)

    for destination in dst:
        tumple = ({'Rule': {'name': ctp}},
                  {'Destination': {'name': ctp}},
                  {'Address': {'name': destination}})
        array.append(tumple)

    tumple = ({'Rule': {'name': ctp}},
              {'Application': {'name': app}},
              {'Service': {'name': svc}})
    array.append(tumple)

print array

