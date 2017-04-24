#!/usr/bin/env python
# coding=utf-8

from netaddr import *
from pprint import pprint
import re
import bigsuds
import logging



class tablesheet(object):
    """ Class de lecture de tables type CVS, handsontables, etc (header + lines)
        :param key, the field and type of nodes to update, { 'name':'Server' }
        :param fields, the corresponding fields/Nodes or nodes'properties. { 'client':'Client', 'cpu': {'Server': 'cpu'}, ...}
        :param table: a list of records, first line with header corresponding to Nodes and properties
        :param create flag to make new nodes if needed
        :param pattern filter on key field values, default to all, syntax: { 'fieldname' : [ p1,p2,...] , 'fieldname2' : [ ...}
        """
    def __init__(self, key, fields, table, create=False, pattern=''):
        self.log = logging.getLogger(__name__)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self.log.addHandler(ch)
        self.log.setLevel(logging.DEBUG)
        self.device = { 'name' : 'sheet', 'device':'manual'}
        self.curdevice = self.device
        self.key = key
        self.fields = fields
        self.table = table
        self.create = create
        self.pattern = pattern
        self.records = self._get_records()
        self._get_device_info()
        self.log.debug('Sheet init done')

    def _get_device_info(self):
        # Todo : code this !
        return ({ 'mock' : 'fake info'})

    def _get_records(self):
        """ return records to add to database from the table sheet
        :return: list of dict of Nodes : { 'name' : xx}"""

        records=[]

        # on collecte les labels
        labels = set()

        for attr in dir(self):
            print "obj.%s = %s" % (attr, getattr(self, attr))

        # on caputure le header
        # par exemple client;platform;env;type;name;cpu;ram;diskGB;os_type;cpu_addon;ram_addon;base_vm;base_cpu;base_ram;base_san;base_nas;base_bkp;base_net;net_Mbps;base_net;price
        # permet d'avoir le num de colonne avec le nom de field
        header = {}
        cnt=0
        for i in self.table.pop(0):
            header.update({i: cnt})
            cnt += 1
        self.log.debug(' update_from_sheet header : ' + str(header))

        # on test si tous les champs donnes sont bien dans le sheet
        for i in self.fields.keys():
            labels.add(i)
            if i not in header:
                self.log.info(' update_from_sheet:  Erreur : champs ' + i + ' non reconnu')
                return False

        # on test si key est dans header
        if not self.key in header:
            self.log.info(' update_from_sheet: key not in header !' + self.key + ' : ' + str(header))
            return False

        # on test si les proprietes sont coherentes (same Node label)
        for f in self.fields:
            # si c'est les propietes du node key
            if isinstance(f, dict):
                # test coherence
                if f.values()[0].keys()[0] != self.key.values()[0]:
                    self.log.info(
                        ' update_from_sheet: sub field to property error! ' + f.values()[0].keys()[0] + " : " +
                        self.key.values()[0])
                    return False

        # on parse tout
        for i in self.table:
            name = i[header[self.key]]
            tumple = ()

            # check le pattern correspond
            pattern_fit = True
            if isinstance(self.pattern,dict):
                # pour chaque field de pattern
                for f in self.pattern:
                    # pour chaque pattern p dans le field f
                    for p in self.pattern[f]:
                        # si le pattern est dans le field self.pattern.keys()[0]
                        if p in i[header[self.pattern.keys()[0]]]:
                            pattern_fit=True
                            break

            # si pattern match
            if pattern_fit:
                properties = {}
                for f in self.fields.keys():
                    # si c'est les propietes du node key
                    if isinstance(self.fields[f], dict):
                        # on stock les properties
                        self.log.debug(" isinstance "+str(f))
                        properties.update({self.fields[f].values()[0]: i[header[self.fields[f].values()[0]]].decode('utf-8', errors='ignore')})
                    else:
                        # sinon c'est un node
                        nodes = i[header[f]].replace(' ','').split(',\n')
                        for nde in nodes:
                            tumple += ({self.fields[f]: { 'name': nde }},)

                properties.update({self.key: name})
                tumple += ({self.fields[self.key].keys()[0]: properties},)
                records.append(tumple)

        # we get labels of the sheet instance
        self.labels=list(labels)
        self.log.debug(' Records :'+str(records))
        return records

    def get_records(self):
        """ return records to add to database from the table sheet
        :return: list of dict of Nodes : { 'name' : xx}"""
        return self.records