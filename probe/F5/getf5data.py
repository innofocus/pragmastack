#!/usr/bin/python
import bigsuds, os, sys,string
login='************'
password='**********'
# Connection sur les equipements
lc_connect=bigsuds.BIGIP(hostname='pa4-lc2-prd.canaltp.prod',username=login,password=password)
adc_connect=bigsuds.BIGIP(hostname='pa4-adc2-prd.canaltp.prod',username=login,password=password)

#Chargement de la liste des VS sur chacun des equipements
lc_vs_list=lc_connect.GlobalLB.VirtualServerV2.get_list()
adc_vs_list=adc_connect.LocalLB.VirtualServer.get_list()

#Declaration variable
result=[]
lctumple=()
adctumple=()

# LC - Boucle for sur chacun des VS
for lc_vs_name in lc_vs_list:
    try:
        lc_pool_name=lc_connect.LocalLB.VirtualServer.get_default_pool_name(virtual_servers=[[lc_vs_name['name']]])[0]
        lc_node_list= (lc_connect.LocalLB.Pool.get_member_v2([lc_pool_name]))
        # Lc- Boucle for sur chacun des Node present dans le pool rattache au VS
        for lc_node in lc_node_list:
            for node in lc_node:
                #nom du VS
                lcvsname= lc_vs_name["name"]
                #Adresse Public du VS
                lcvsippub= lc_connect.LocalLB.VirtualServer.get_destination([lc_vs_name['name']])[0]["address"]
                #Port du VS
                lcvsportpub = lc_connect.LocalLB.VirtualServer.get_destination([lc_vs_name['name']])[0]["port"]
                #Nom du node
                lcvsnode= node["address"]
                #IP du node
                lcvsipnode =lc_connect.LocalLB.NodeAddressV2.get_address([node["address"]])[0]
                #Liste des elements au format JSON
                lctumple = ({'Lc_vs': {'name': lcvsname}},
                            {'Ip':{'name': lcvsippub}},
                            {'Port':{'name':lcvsportpub}},
                            {'Lc_pool': {'name': lc_pool_name}},)
                result.append(lctumple)

                lctumple = ({'Lc_node': {'name': lcvsnode}},
                            {'Ip': {'name': lcvsipnode}},
                            {'Port':{'name': lcvsportpub}},
                            {'Lc_pool': {'name': lc_pool_name}},)
                result.append(lctumple)
                #print lctumple
    except:
        print ("il n'y a pas de vip public" + lcvsname)

#ADC - Boucle for sur chacun des VS
for adc_vs_name in adc_vs_list:
    try:
        # Nom du VS
        adc_pool_name=adc_connect.LocalLB.VirtualServer.get_default_pool_name(virtual_servers=[[adc_vs_name]])[0]
        # Liste des Nodes present
        adc_node_list= (adc_connect.LocalLB.Pool.get_member_v2([adc_pool_name]))
        # Pour chaque node apartenent a un pool
        for adc_node in adc_node_list:
            for node in adc_node:
                # nom du vs
                adcvsname= adc_vs_name
                # Ip du vs
                adcvsippriv= adc_connect.LocalLB.VirtualServer.get_destination([adc_vs_name])[0]["address"]
                # Port du vs
                adcvsportpriv = adc_connect.LocalLB.VirtualServer.get_destination([adc_vs_name])[0]["port"]
                # Nom du node
                adcvsnode =node["address"]
                # Address IP du Node
                adcvsipnode= adc_connect.LocalLB.NodeAddressV2.get_address([node["address"]])[0]
                # Liste des elements au format JSON
                adctumple = ({'Lc_vs': {'name': adcvsname}},
                            {'Ip': {'name': adcvsippriv}},
                            {'Port': {'name': adcvsportpriv}},
                            {'Lc_pool': {'name': adc_pool_name}},)
                result.append(adctumple)

                adctumple = ({'Lc_node': {'name': adcvsnode}},
                            {'Ip': {'name': adcvsipnode}},
                            {'Port': {'name': adcvsportpriv}},
                            {'Lc_pool': {'name': adc_pool_name}},)
                result.append(adctumple)
                #print adctumple
    except:
        print ("il n'y a pas de vip prive" + adcvsname)
print result