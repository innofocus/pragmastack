#!/usr/bin/env python


from py2neo import Graph, Node, Relationship, watch
from CMgDB.CMgDB import CMgDB, liveupdate

import warnings
warnings.filterwarnings('once', '.*KeyError.*',)

def main(config_file, target, **options):
    """ call des methods"""
    log.info('Start main')
    #watch('neo4j')

    n = liveupdate(config_file)
    link_link = options['links']['link']
    link_to = options['links']['to']
    link_by = options['links']['by']
    if link_link or link_to or link_by:
        if link_link and  link_to and link_by:
            log.info('linking '+link_link+' and '+link_to+' by '+link_by)

            if link_link == "Ip" and link_to == "Network" and link_by == "Cidr":
                n.link_networks_ip()
                log.info(" End of linking IP on Networks")
                exit(0)
            else:
                n.link_by(link_link, link_to, by=link_by)
                log.info(" End of linking")
                exit(0)
        else:
            log.fatal (" Error : please provide --link Node --to Node --by Node to complete linking order !")
            exit(1)

    # for testing purpose
    #n.graph.run('match (m)-[r]-() delete m,r')
    #n.graph.run('match (m) delete m')

    if 'init' in options and options['init']:
        log.info('init mode : delete all entries from database')
        # setting up model and groups
        n.graph.delete_all()
        for (s,l,t) in n.Models:
            #log.debug('s,l,t :'+s+','+l+','+t)
            source=Node('Model',name=s)
            n.graph.merge(source)
            tgt=Node('Model',name=t)
            n.graph.merge(tgt)
            link=Relationship(source,l,tgt)
            n.graph.merge(link)

        for (s,l,t) in n.Groups:
            #log.debug('s,l,t :' + s + ',' + l + ',' + t)
            source=Node('Group',name=s)
            n.graph.merge(source)
            tgt=Node('Model',name=t)
            n.graph.merge(tgt)
            link=Relationship(source,l,tgt)
            n.graph.merge(link)

        log.debug ('Model settled')

    log.info(' Liveupgrade target : '+target)
    n.from_device(target,options['cleanup'])

    exit(0)

if __name__ == "__main__":
    # execute only if run as a script
    import logging, warnings
    import argparse
    import textwrap
    import yaml

    parser = argparse.ArgumentParser(description='Tool for updating neo4j database with live information gathered from infrastructure',
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=textwrap.dedent(''' Enjoy !'''))
    parser.add_argument('--config', dest="config", help="Configuration file in Yaml format")
    parser.add_argument('--target', dest="target", help="Target name if configuration file contains its name entry")
    parser.add_argument('--init', dest="init", action='count', help="Init all")
    parser.add_argument('--cleanup', dest="cleanup", action='count', help=" Delete devices related nodes")
    parser.add_argument('--link', dest="link", help="Link <Node> To <Node> By <Node>")
    parser.add_argument('--to', dest="to", help="Link <Node> To <Node> By <Node>")
    parser.add_argument('--by', dest="by", help="Link <Node> To <Node> By <Node> - Special by='Cidr' for Network and Ip.")
    parser.add_argument('-v', dest="verbose", action='count', help="mode verbeux")

    options = parser.parse_args()

    # get eventuel linking command order
    links = { 'link': options.link,
              'to': options.to,
              'by': options.by}


    logging.captureWarnings(True)
    log = logging.getLogger(__name__)
    log.setLevel(logging.INFO)

    # create console handler and set level to debug
    ch = logging.StreamHandler()
    if options.verbose == 1:
        print ('verbose : ' + str(options.verbose))
        log.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    log.addHandler(ch)
    log.debug(' starting : verbose mode'+str(options.verbose))


    main(config_file=options.config, target=options.target, init=options.init, cleanup=options.cleanup, links=links)

