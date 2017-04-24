./vmware2neo.py --host ctp-prd-vcenter2.canaltp.prod --username svc-rundeck@canaltp0 --password xxxxxxx --port 443 --neohost ctp-prd-rda.canaltp.prod --neousername neo4j --neopassword xxxx --neoport 7474
./update-from-csv.py --neousername neo4j --neopassword xxxxx --neohost ctp-prd-rda.canaltp.prod --neoport 7474 --file updates/update-20170103.csv
./update-from-csv.py --neousername neo4j --neopassword xxxxx --neohost ctp-prd-rda.canaltp.prod --neoport 7474 --file updates/cisco\ ucs.csv --create
./bill-cloud.py --neousername neo4j --neopassword xxxxx --neohost ctp-prd-rda.canaltp.prod --neoport 7474 --backup resources/backup-201612.csv --nasvolumes resources/nasvolumes-201610.csv --percentiles resources/percentiles-201612.csv
cp billcloud.xlsx /whereveryouwant/
# ensuite renommer le fichier dans excel, sinon, on perd les calculs relatifs
