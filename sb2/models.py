# coding=utf-8
#from .models import *
from sb2 import app
from CMgDB.CMgDB import CMgDB,liveupdate

from datetime import datetime
import os
import uuid
try:
    from flask import request, json, session, send_from_directory, render_template
except ImportError:
    import json
from flask_restful import reqparse, abort, Api, Resource
import socket
import re
import requests
from requests.auth import HTTPBasicAuth
from netaddr import *
import logging

# config file
app.config['config_file'] = 'live.yaml'
lu = liveupdate(app.config['config_file'])
for i in lu.config['app'].keys():
    app.config[i]=lu.config['app'][i]


app.debug = app.config['debug']

if app.config['debug']:
    app.logger.setLevel(logging.DEBUG)

if app.config['debug']:
    app.logger.debug(' Models in Debug Mode !')

# sheets models
reports={ 'server' :
              { 'cypher' : '''
                            match (server:Server)
                            optional match (server:Server)--(dc:Datacenter)
                            optional match (server:Server)--(pf:Platform)
                            optional match (server:Server)--(client:Client)
                            optional match (server:Server)--(env:Environment)
                            optional match (server:Server)--(pnl:Pnl)
                            optional match (server:Server)--(af:Affaire)
                            optional match (server:Server)--(ip:Ip { version:'ipv4'})
                            optional match (ip:Ip)--(vlan:Vlan)
                            with
                                collect (distinct pnl.name) as Pnl,
                                collect (distinct client.name) as Client,
                                collect (distinct af.name) as Affaire,
                                collect (distinct pf.name) as Platform,
                                env.name as env,
                                dc.name as datacenter,
                                server.hardware as type,
                                server.name as name,
                                server.powerstate as powerstate,
                                server.cpu as cpu,
                                server.ram as ram,
                                round(toInt(server.disk)/1024/1024) as diskGB,
                                server.os as os,
                                case when server.os=~'.*icrosoft.*' or server.os=~'.*indows.*' then 'Windows' else 'Linux' end as os_type,
                                server.price as price,
                                server.annotation as annotation,
                                server.role as role,
                                collect (distinct vlan.name) as vlan,
                                collect (distinct ip.name) as ip
                            return distinct
                            ''',
                'query' : '''
                             Pnl,
                             Client,
                             Affaire,
                             Platform,
                             env,
                             datacenter,
                             type,
                             name,
                             ip,
                             vlan,
                             powerstate,
                             cpu,
                             ram,
                             diskGB,
                             os,
                             os_type,
                             annotation,
                             role
                            ''',
                'editor' : "Pnl, Client, Affaire, Platform, role, annotation".replace(' ','').split(','),
                'fields' : {'name' : {'Server':'name'}, 'Pnl':'Pnl', 'Client':'Client',
                            'Affaire':'Affaire', 'Platform':'Platform',
                            'annotation' : {'Server':'annotation'}, 'role':{'Server':'role'}},
                'key' : 'name',
                'create' : True,
                'pattern' : { 'type' : 'VM,Server'.split(',')}
              },
          'adcvip':
              { 'cypher' : '''
                            match (vs:Adc_vs)-[:provides]->(vipp:Ipport)<-[:uses]-(pool:Adc_pool)-[:uses]->(nipp:Ipport)
                            match (pool:Adc_pool)-[provides]->(node:Adc_node)-[:provides]->(nipp:Ipport)
                            optional match (pool:Adc_pool)--(m:Adc_monitor)
                            with
                                vs.name as name,
                                vipp.name as vipp_name,
                                pool.name as pool_name,
                                collect (distinct node.name) as node_name,
                                collect (distinct nipp.name) as nipp_name,
                                m.name as monitor,
                                m.type as mon_type,
                                m.STYPE_SEND as m_STYPE_SEND,
                                m.STYPE_GET as m_STYPE_GET,
                                m.STYPE_RECEIVE as m_STYPE_RECEIVE,
                                m.STYPE_USERNAME as m_STYPE_USERNAME,
                                m.STYPE_PASSWORD as m_STYPE_PASSWORD
                            return distinct ''',
                'query' : '''
                            name, vipp_name, pool_name, node_name, nipp_name,
                            monitor, mon_type, m_STYPE_SEND,
                            m_STYPE_GET, m_STYPE_RECEIVE, m_STYPE_USERNAME, m_STYPE_PASSWORD
                        ''',
                'editor' : None,
                'fields' : None,
                'key': 'name',
                'create': False,
                'pattern': None
              },
          'network':
              {'cypher': '''with ['Network','Gateway','Vlan','Domain','Nic'] as exclude
                            match (mi:Model {name:'Ip'})--(m:Model) where not m.name in exclude with collect (distinct m.name) as list
                            match (n:Network)--(i:Ip) where n.name = {networkname}
                            optional match (i:Ip)--(s) where labels(s) in list
                            with  i.name as network, s.name as name, labels(s)[0] as type
                            return distinct ''',
               'query': "network, name, type",
               'selector' : 'networkname',
               'editor': ['name','type'],
               'fields': {'name': 'name' ,'type':'type' },
               'key': 'network',
               'create': False,
               'pattern': None
               }
         }


def querygraph(query):
    header = {"Content-type": "application/json"}
    auth = HTTPBasicAuth(lu.config['database']['username'],lu.config['database']['password'])
    uri = lu.url+'/db/data/transaction/commit'
    data = { "statements":[{"statement": query, "resultDataContents":["graph"]}] }
    r = requests.post(uri, auth=auth, json=data)
    nodes = {}
    edges = {}
    result = { 'nodes':[], 'edges':[] }
    app.logger.debug('Query from querygraph : '+query)
    if r.status_code == 200:
        for i in r.json()['results']:
            for j in i['data']:
                for k in j['graph']['relationships']:
                    edges.update({ k['startNode']+'-'+k['endNode'] : {'from': k['startNode'],
                                                                      'to': k['endNode'],
                                                                      'label': k['type'],}
                                   })
                for k in j['graph']['nodes']:
                    props=""
                    for l in sorted(k['properties']):
                        props+=l+': '+str(k['properties'][l])+'<br>'
                    nodes[k['id']]= { 'group': k['labels'][0],
                                      'id': k['id'],
                                      'label': k['labels'][0]+'='+k['properties']['name'],
                                      'name': k['properties']['name'],
                                      'title': props}
        for i in nodes.values():
            result['nodes'].append(i)
        for i in edges.values():
            result['edges'].append(i)

        return json.jsonify(data=result)
    else:
        return json.jsonify([ 'Error in querygraph'])

class User:
    def __init__(self, username):
        self.username = username

    def free_search(self, query):
        return lu.graph.data(query)

    def get_node(self,name,label):
        query = "match (x:"+label+") where x.name=~\""+name+"\" return x"
        result = lu.graph.data(query)
        if len(result)>0:
            if 'x' in result[0]:
                return result[0]['x']
        return None

    def get_fields(self,label):
        query = "match (x:"+label+") return distinct keys(x) as x"
        result = lu.graph.data(query)
        s=set()
        if len(result) > 0:
            if 'x' in result[0]:
                for i in result[0]['x']:
                    s.add(i)
        return s

    def update(self,label,name,properties):
        neo_ci=Node(label,name)
        for i in properties.keys():
            neo_ci[i]=properties[i]
        try:
            neo_ci.push()
            return True
        except:
            return False

def existence (label,ci):
    if lu.graph.find_one(label,'name',ci) == None:
        abort(404, message="Ci {} doesn't exist".format(ci))

class Server(Resource):
    def get(self, server_id):
        app.logger.debug(server_id)
        query = "match (Server:Server) where Server.name =~ '{}' return ".format(server_id)
        if request.method == 'GET':
            app.logger.debug (str(request.form))
            if len(request.form.keys()) == 0:
                query += "Server"
            else:
                count=0
                for i in request.form.keys():
                    count+=1
                    if count > 1:
                        query += ","
                    query+= "Server."+i
        else:
            query+= "Server"
        app.logger.debug(query)
        result=lu.graph.data(query)
        if result == []:
            abort(404, message="Ci {} doesn't exist here".format(server_id))
        return result

    def put(self, server_id):
        neo_ci=Node('Server', name=server_id)
        lu.graph.merge(neo_ci)
        if request.method == 'PUT':
            for i in request.form.keys():
                neo_ci[i]=request.form[i]
            neo_ci.push()
        return 'OK', 200

    def delete(selfself, server_id):
        neo_ci=lu.graph.find_one('Server', 'name', server_id)
        if neo_ci == None:
            abort(404, message="Ci {} doesn't exist".format(server_id))
        else:
            query = "match (server:Server)-[r]-() where server.name = '{}' delete server, r".format(server_id)
            lu.graph.run(query)
            if lu.graph.find_one('Server', 'name', server_id) == None:
                return 'OK', 200
            else:
                query = "match (server:Server) where server.name = '{}' delete server".format(server_id)
                lu.graph.run(query)
                if lu.graph.find_one('Server', 'name', server_id) == None:
                    return 'OK', 200
                else:
                    abort(400, message="Ci {} not deleted".format(server_id))

    def post(self, server_id):
        return { 'message':server_id+' is OK but not implemented yet. use /post instead'+json.dumps(request.get_json()) }

class Link(Resource):
    def get(self, nodea,nodeb):
        query='match (a)-[l]-(b) where a.name="'+nodea+'" and b.name="'+nodeb+'" return a,l,b'
        app.logger.debug(query)
        result = lu.graph.data(query)
        if result == []:
            abort(404, message="Ci {} doesn't exist here".format(server_id))
        return result

class Post(Resource):
    def post(self):
        if request.method == 'POST':
            if re.match('application/json',request.headers['Content-Type']):
                app.logger.debug ('json detected')
                post=request.get_json()
            else:
                app.logger.debug ('no json detected')
                post=request.values

            if ('Label' in post) and ('name' in post):
                label = post.pop('Label')
                name = post.pop('name')
                if User(session['username'].update(label,name,post)):
                    return "OK", 200
            else:
                abort(400, message="I Needed {Label : value, name:value}. Not Found")

        else:
            abort (400, message="Posted datas error")

def getlist(datatype,selector=None):
    app.logger.debug(' getlist : datatype / selector '+datatype+'/'+str(selector))
    cypher = reports[datatype]['cypher']
    query = reports[datatype]['query']
    editor = reports[datatype]['editor'] or []

    result=[]
    if not 'selector' in reports[datatype]:
        app.logger.debug(' getlist : no selector in reports')
        nodelist = lu.graph.run(cypher+query+' order by name').data()
    else:
        app.logger.debug(' getlist : selector : type '+str(selector)+':'+str(type(selector)))
        if selector == None:
            return json.jsonify(' Error, selector needed.')
        params =  {reports[datatype]['selector']:selector}
        nodelist = lu.graph.run(cypher + query + ' order by name',parameters=params).data()
    #app.logger.debug(' getlist : nodelist : '+str(nodelist))
    header=query.replace('\n',' ').replace(' ','').split(',')
    result.append(header)

    # lists d'autocomplete par colonne/field
    # dict of sets
    autocomplete={}
    iplist=[]
    if datatype=='network': iplist=[]
    for i in nodelist:
        tmp=[]
        for j in header:
            cell = ""
            if isinstance(i[j],list):
                cell = ',\n'.join(i[j]).decode('utf-8', errors='ignore')
            elif isinstance(i[j], int) or isinstance(i[j], float):
                cell = str(i[j])
            elif not i[j] == None:
                #app.logger.debug(' cell i,j : '+','.join(list((i[j]))))
                try:
                    cell = i[j].decode('utf-8', errors='ignore')
                except UnicodeEncodeError:
                    cell = i[j]

            tmp.append(cell)

            # construction de la list autocomplete
            if j in editor:
                if j in autocomplete:
                    autocomplete[j].add(cell)
                else:
                    autocomplete[j]=set((cell,))
            if datatype == 'network' and j == reports[datatype]['key']:
                iplist.append(i[j])

        result.append(tmp)
    if datatype == 'network':
        app.logger.debug(' getlist : selector '+str(selector))
        for i in list(IPNetwork(str(selector))):
            if not i in iplist:
                result.append([str(i),'','',''])
    # colonnes de handsontable (autocomplete = dropdown)
    columns = []
    for i in header:
        # si la colonne est editable, creer la liste des options
        if i in editor:
            columns.append({  'type': 'autocomplete', 'source': list(autocomplete[i]), 'readOnly': False})
        else:
            columns.append({  'editor': False,  'readOnly': True})
    #app.logger.debug(' getlist : result : '+str(result))
    return { 'data':result, 'columns': columns}

class JsonData(Resource):
    def post(self, datatype):
        app.logger.debug(' JsonData : datatype '+datatype)
        selector = None
        if hasattr(request, 'json'):
            app.logger.debug (' request.json : ' + str(request.json))
        else:
            app.logger.debug(' No JSON Data')

        if not datatype in reports:
            return json.jsonify(' bad datatype')
        if 'selector' in reports[datatype]:
            app.logger.debug(' selector in reports ')
            if hasattr(request, 'json') and 'selector' in request.json:
                selector = str(request.json['selector'])
                app.logger.debug(' selector detected : selector : '+str(selector))
        return json.jsonify(getlist(datatype, selector))


class HOTSave(Resource):
    def post(self,datatype):
        # sauvegarde des elements
        # si delta = false retourne le delta des datas
        # si delta = true applique les modifications (ie datas = delta)
        data = request.json['data']
        header = request.json['header']
        delta = request.json['delta']
        deltadata = []
        if not delta:
            # on renvoie le delta avec la base
            app.logger.debug(datatype)
            app.logger.debug(str(header))
            app.logger.debug(str(data[0]))
            actualdata=getlist(datatype)
            actualheader = actualdata['data'].pop(0)
            if not header == actualheader:
                return json.jsonify("Header disorder. please let the columns untouched !")
            for i in data:
                if i not in actualdata['data']:
                    deltadata.append(i)

            app.logger.debug(str(header))
            app.logger.debug(str(deltadata))
            return json.jsonify(header=header, deltadata=deltadata)
        else:
            # c'est le delta à modifier dans la base
            app.logger.debug(datatype)
            app.logger.debug(str(header))
            app.logger.debug(str(data))
            device = dict(reports[datatype])
            device.pop('cypher')
            device.pop('query')
            device.pop('editor')
            data.insert(0,header)
            device['table']=list(data)
            # on cleanup tous les liens mis à jour
            return lu.from_sheet(device, cleanup='Server')

class Whatsup(Resource):
    def get(self):
        query = "match (n)-[r]->(m) return distinct labels(n) as source,type(r) as rel,labels(m) as target, count(*) as count"
        data=lu.graph.data(query)
        l=[]
        for i in data:
            l.append("(s:"+" ".join(i['source'])+")-[r:"+i['rel']+"]->(t:"+" ".join(i['target'])+"):("+str(i['count'])+")")
        return l


# WAWA : Who and Where Am I : taking the caller header information to tell Who and Where
class Wawa(Resource):
    def get(self, label):
        if 'username' not in session:
            session['username'] = uuid.uuid4()
        params = {}
        if request.method == 'GET':
            app.logger.debug(str(request.values))
            for i in request.values.keys():
                params[i] = (request.values[i] or "<empty>")
            for i in request.headers.keys():
                params[i] = (request.headers[i] or "<empty>")
            params['client_addr']=socket.getfqdn(request.remote_addr)
            params['url']=request.url
            params['host']=request.host
            params['session']=session['username']
            if len(request.values) == 0:
                query="match (x:"+label+") return x"
            else:
                query="match (x:"+label+") return x"
            result = lu.graph.data(query)
            return json.jsonify(result)
        else:
            return question

class show(Resource):
    def get(self, labela, valuea):
        result = []
        if 'username' not in session:
            session['username'] = uuid.uuid4()
        if request.method == 'GET':
            query = "match (x:" + labela + ") where x.name =~\"" + valuea + "\" return x"
            restmp = lu.graph.data(query)
            for i in restmp:
                node = dict(i['x'])
                result.append({ node.pop('name') : node })
        if result == []:
            abort(404, message="Ci {} doesn't exist here".format(labela))
        return json.jsonify(result)

# class list(Resource):
#     def get(self):
#         if 'username' not in session:
#             session['username'] = uuid.uuid4()
#         params = {}
#         if request.method == 'GET':
#             query = "match (x) return distinct labels(x) as x"
#             result = ()
#             restmp = lu.graph.data(query)
#             for i in restmp:
#                 for j in i['x']:
#                     result+=(j,)
#             return json.jsonify(result)
#         else:
#             return question

class list_label(Resource):
    def get(self, labela):
        if 'username' not in session:
            session['username'] = uuid.uuid4()
        params = {}
        if request.method == 'GET':
            query="match (x:"+labela+") return x"
            result=[]
            restmp = lu.graph.data(query)
            for i in restmp:
                result.append(i['x']['name'])
            return json.jsonify(result)
        else:
            return question

class list_label_value(Resource):
    def get(self, labela, valuea):
        if 'username' not in session:
            session['username'] = uuid.uuid4()
        params = {}
        if request.method == 'GET':
            query = "match (x:" + labela + ")--(y) where x.name =~\"" + valuea + "\" return distinct labels(y) as y"
            result = ()
            restmp = lu.graph.data(query)
            for i in restmp:
                for j in i['y']:
                    result+=(j,)
            return json.jsonify(result)
        else:
            return question

class list_label_value_label(Resource):
    def get(self, labela, valuea, labelb):
        if 'username' not in session:
            session['username'] = uuid.uuid4()
        params = {}
        if request.method == 'GET':
            query = "match (x:" + labela + ")--(y:" + labelb + ") where x.name =~\"" + valuea + "\" return y as y"
            result = []
            restmp = lu.graph.data(query)
            for i in restmp:
                result.append(i['y']['name'])
            return json.jsonify(result)
        else:
            return question



class jsontest(Resource):
    def get(self):
        query = "match (s:Server)-[r]->(c:Client) return distinct s,id(s) as ids,r, id(r) as idr,c, id(c) as idc limit 20"
        result = lu.graph.data(query)
        app.logger.debug(str(result))
        nodesdict={}
        edges=[]
        for i in result:
            nodesdict.update({ i['ids'] : { "id": i['ids'], "group": list(i['s'].labels())[0], "label" : i['s']['name']}})
            nodesdict.update({ i['idc'] : { "id": i['idc'], "group": list(i['c'].labels())[0], "label" : i['c']['name']}})
            edges.append({ "from" : i['ids'], "to" : i['idc'], "label": i['r'].type()})
        nodes=[]
        for i in nodesdict:
            nodes.append(nodesdict[i])
        return json.jsonify(data={ "nodes" : nodes, "edges" : edges,  })

class catcher(Resource):
    def get(self, Rlabel, Rname, ProviderOrConsumer, label,name):
        message="search "+Rlabel+":"+Rname+" from "+ProviderOrConsumer+" "+label+":"+name
        return message

def timestamp():
    epoch = datetime.utcfromtimestamp(0)
    now = datetime.now()
    delta = now - epoch
    return delta.total_seconds()

def date():
    return datetime.now().strftime('%Y-%m-%d')
