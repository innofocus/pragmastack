#!/bin/bash
./liveupdate.py -v --config live.yaml --target n5k1 --init
./update-from-json.py --config live.yaml --create --jsonfile probe/cisco/resultscan.json.filtered

./liveupdate.py --config live.yaml --target vcenter 
./liveupdate.py --config live.yaml --target paloalto1
./liveupdate.py --config live.yaml --target lc2
./liveupdate.py --config live.yaml --target adc2

# we link what's to be linked...
./liveupdate.py --config live.yaml --link Ip --to Network --by Cidr
./liveupdate.py --config live.yaml --link Server --to Ip --by Nic
./liveupdate.py --config live.yaml --link Server --to Vlan --by Nic
./liveupdate.py --config live.yaml --link Vlan --to Ip --by Network
./liveupdate.py --config live.yaml --link Server --to Vlan --by Ip
./liveupdate.py --config live.yaml --link Switch --to Network --by Ip

# we get static datas for adminsitrative informations
./update-from-csv.py --config live.yaml --file datas/updates/servers.csv --create --type VM,Server:Server -p type:hardware -r pnl:Pnl -r client:Client -r affaire:Affaire -r platform:Platform -r env:Environment -r datacenter:Datacenter -p annotation:annotation -p powerstate:powerstate -p cpu:cpu -p ram:ram -p diskGB:disk --addrel

# par defaut on prend le dernier update
file=`ls -1tr datas/updates/update-* | tail -1`
./update-from-csv.py --config live.yaml --file $file --type VM:Server -p type:hardware -r pnl:Pnl -r client:Client -r affaire:Affaire -r platform:Platform -r env:Environment -r datacenter:Datacenter -p role:role -p annotation:annotation --addrel

file='datas/updates/update-20170126.csv'
./update-from-csv.py --config live.yaml --file $file --type VM:Server -p type:hardware -r pnl:Pnl -r client:Client -r affaire:Affaire -r platform:Platform -r env:Environment --addrel


# on valorise les data fonctionnelles
./liveupdate.py --config live.yaml --link Server --to Client --by Platform
