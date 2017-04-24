#!/bin/bash

export neohost=
export neoport=7474
export neouser=
if [[ "x$neopass" == "x" ]]; then neopass=$1; fi

export username=
if [[ "x$password" == "x" ]]; then password=$2; fi

./liveupdate.py --neousername $neouser --neopassword $neopass --neohost $neohost --neoport $neoport --devtype n5k --devhost 10.93.64.21  --devport 22 --devusername $username --devpassword $password --init
./update-from-json.py --neousername $neouser --neopassword $neopass --neohost $neohost --neoport $neoport --create --jsonfile probe/cisco/resultscan.json.filtered

./liveupdate.py --neousername $neouser --neopassword $neopass --neohost $neohost --neoport $neoport --devtype vmware --devhost ctp-prd-vcenter2.canaltp.prod --devport 443 --devusername $username@canaltp0 --devpassword $password
./liveupdate.py --neousername $neouser --neopassword $neopass --neohost $neohost --neoport $neoport --devtype n5k --devhost 10.93.64.21  --devport 22 --devusername $username --devpassword $password --linkall
./liveupdate.py --neousername $neouser --neopassword $neopass --neohost $neohost --neoport $neoport --devtype palo --devhost 10.93.64.4 --devport 443 --devusername $username --devpassword $password
./liveupdate.py --neousername $neouser --neopassword $neopass --neohost $neohost --neoport $neoport --devtype f5_lc --devhost pa4-lc2-prd.canaltp.prod  --devport 443 --devusername $username --devpassword $password
./liveupdate.py --neousername $neouser --neopassword $neopass --neohost $neohost --neoport $neoport --devtype f5_adc --devhost pa4-adc2-prd.canaltp.prod  --devport 443 --devusername $username --devpassword $password



./update-from-csv.py --neousername $neouser --neopassword $neopass --neohost $neohost --neoport $neoport --file datas/updates/servers.csv --create --type VM,Server:Server -p type:hardware -r pnl:Pnl -r client:Client -r affaire:Affaire -r platform:Platform -r env:Environment -r datacenter:Datacenter -p annotation:annotation -p powerstate:powerstate -p cpu:cpu -p ram:ram -p diskGB:disk --addrel

# par defaut on prend le dernier update
file=`ls -1tr datas/updates/update-* | tail -1`
./update-from-csv.py --neousername $neouser --neopassword $neopass --neohost $neohost --neoport $neoport --file $file --type VM:Server -p type:hardware -r pnl:Pnl -r client:Client -r affaire:Affaire -r platform:Platform -r env:Environment -r datacenter:Datacenter -p role:role -p annotation:annotation --addrel

# Attention, on supprime la cible avant
ls datas/billcloud.xlsx  && rm datas/billcloud.xlsx
./bill-cloud.py --neousername $neouser --neopassword $neopass --neohost $neohost --neoport $neoport --backup datas/resources/backup-201612.csv --nasvolumes datas/resources/nasvolumes-201610.csv --percentiles datas/resources/percentiles-201612.csv --xlsfile datas/billcloud.xlsx
ls datas/billcloud.xlsx  && rm datas/Extract-CMDB.xlsx
./Extract-CMDB.py --neousername $neouser --neopassword $neopass --neohost $neohost --neoport $neoport
