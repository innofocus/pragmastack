#!/usr/bin/env python
# coding=utf-8

import csv
import json
from CMgDB.CMgDB import CMgDB, liveupdate

def main(config_file, **options):



    nodetype = json.loads('{"'+options['type'].replace(':','":"')+'"}')
    fnodes = nodetype.keys()[0].split(',')
    vnode =  nodetype.values()[0]
    log.info('Node types : '+ str(fnodes) + ' to : ' + vnode)

    relationship={}
    if 'rel' in options and not options['rel'] == None:
        # recup des champs <field>:<Node>
        for i in options['rel']:
            j = '{"'+i.replace(':','":"')+'"}'
            relationship.update(json.loads(j))

        log.info('Relationships : '+str(relationship))

    property={}
    if 'prop' in options and not options['prop'] == None:
        for i in options['prop']:
            j = '{"'+i.replace(':','":"')+'"}'
            property.update(json.loads(j))

        log.info('Properties : '+str(property))

    if options['create']:
        print ("Becareful : option create enabled")
    else:
        print ("Becareful : option create disabled")

    n = CMgDB(config_file)

    # pour tous les fichiers updates
    for uf in options['file']:
        log.info ('Update from file :' + uf + ' . ')
        # raw_input('Please push Enter to go')
        cilist = {}
        filecsv = open(uf, 'r')
        csvreader = csv.reader(filecsv, delimiter=';')

        # on caputure le header dans hidx
        # par exemple client;platform;env;type;name;cpu;ram;diskGB;os_type;cpu_addon;ram_addon;base_vm;base_cpu;base_ram;base_san;base_nas;base_bkp;base_net;net_Mbps;base_net;price
        hidx = {}
        cnt = 0
        for i in csvreader.next():
            hidx.update({i: cnt})
            cnt += 1
        log.debug(' header : '+str(hidx))
        # csvreader.next()

        # on test si tous les champs donnes sont bien dans le fichier
        for i in relationship:
            if i not in hidx:
                log.info(' Erreur : champs '+i+' non reconnu')
                exit(1)
        for i in property:
            if i not in hidx:
                log.info(' Erreur : champs '+i+' non reconnu')
                exit(1)

        # on parse tout
        for i in csvreader:
            # le type est parmis server, VM, backup, ...
            typelist = i[hidx['type']]
            # si c'est dans la liste fnodes : par exemple --type VM,server:Server, soit une VM ou un server
            if typelist.split()[0] in fnodes:
                cilist.update({i[hidx['name']]: {}})
                # ensuite on prend tous les champs
                for j in hidx.keys():
                    value = i[hidx[j]].decode(options['encoding'], errors='ignore')
                    cilist[i[hidx['name']]].update({j: value})

        filecsv.close()

        log.debug( ' nombre de lignes : ' + str(len(cilist)))

        # compte de nombre de configuration item (ci)
        count = 0
        for ci in cilist:
            if ci == None:
                log.info(' Ligne vide !!')
                continue

            count += 1
            log.info('Asset ' + str(count) + ' : ' + ci),
            neo_ci = n.graph.find_one('Server', 'name', ci)

            # on fait rien si absent et pas mode create
            if (neo_ci == None) and not options['create']:
                log.info(' No create mode. Discarded')
                continue

            # si mode create et absent, on cree
            if (neo_ci == None):
                log.info ('Configuration item not found '),
                neo_ci = n.merge_node('Server', name=ci)
                log.debug(neo_ci)
                log.info ('Adding ... '),

            for p in property:
                value = cilist[ci][p]
                if p == 'diskGB': value = int(value) * 1024 * 1024
                if str(value).isdigit():
                    neo_ci[property[p]] = int(value)
                else:
                    neo_ci[property[p]] = value or 'unknown'

            # cas particulier des serveurs physiques
            if 'Server' in cilist[ci]['type'] and 'Server' in fnodes:
                neo_ci['price'] = cilist[ci]['baseline']

            log.debug(neo_ci),
            neo_ci.push()

            records = [neo_ci]
            # attention, ici si not addrel et new nodes -> link node supprimé
            for r in relationship:
                log.debug('relationship : '+r+' : '+relationship[r])
                # on supprime tout ancien lien
                query = "match (s:Server  { name : '" + ci + "' })-[l]-(:" + relationship[r] + " ) delete l"
                n.graph.run(query)

                # cilist le nom d'un node est donné
                if not cilist[ci][r] == "":
                    log.debug(' relationship to :'+relationship[r]+" : "+cilist[ci][r])
                    # on cherche le node a relier
                    neo_node = n.graph.find_one(relationship[r], 'name', cilist[ci][r])
                    # si on peut creer les nodes a relier
                    if options['addrel']:
                        # on cree le node s'il n'existe pas
                        if neo_node == None:
                            neo_node = n.merge_node(relationship[r], name=cilist[ci][r])
                    log.debug(' link to : '+relationship[r]+' : '+cilist[ci][r]),
                    # alors on l'ajoute à la ciliste des nodes à  relier
                    if not neo_node == None:
                        records.append(neo_node)
            # on relier effecitvement
            n.link_nodes(neo_ci, *records)
            log.debug (' OK')


if __name__ == "__main__":
    # execute only if run as a script
    import logging, warnings

    logging.captureWarnings(True)
    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)

    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    log.addHandler(ch)

    import argparse
    import textwrap
    import yaml


    parser = argparse.ArgumentParser(description="Tool to export vmware infra metadatas to neo4j",
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=textwrap.dedent('''en entree : fichier export extract CSV en iso-8859-1'''))
    parser.add_argument('--config', dest="config", help="Configuration file in Yaml format")
    parser.add_argument('--file', dest="file", nargs="*", help="Updates csv file")
    parser.add_argument('--encoding', dest="encoding", default="utf-8", help="Encoding csv file")
    parser.add_argument('--create', dest="create", action='count', help="Create CI if it is absent")
    parser.add_argument('--addrel', dest="addrel", action='count', help="Create nodes when relationship update")
    parser.add_argument('-t', '--type', dest="type", help="the type field to be updated ex : VM,server:Server")
    parser.add_argument('-r', '--relationship', dest="rel", action="append", help="update with field:Node relationship")
    parser.add_argument('-p', '--property', dest="prop", action="append", help="update with field:Property")
    parser.add_argument('-v', dest="verbose", action='count', help="mode verbeux")

    options = vars(parser.parse_args())

    main(options['config'], **options)
