# BillCloud

# Description
BillCloud génère un fichier excel comprenant :
- l'inventaire des machines virtuelles et physiques
- les prix des machines et des ressources consommées CPU, RAM, Disk SAN, Disk NAS, Backup, Débits réseaux

BillCloud repose sur :
- Neo4j : une base de données de type graphe hébergée sur ctp-prd-rda
- vmware2neo.py : script d'extraction des infos du vCenter vers Neo4j
- update-from-csv.py : script d'actualisation de Neo4j par les modifications dans Excel
- bill-cloud.py : script d'aggrégation pour génération du fichier Excel
- Make_Bill_Cloud.sh : All in one

Ressources :
- 
