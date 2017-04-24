# coding=utf-8
#from sb2 import app

from .models import *
import os
import uuid

try:
    from flask import Flask, Response, request, json, session, send_from_directory, render_template, make_response
except ImportError:
    import json
from flask_restful import reqparse, abort, Api, Resource
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user

import logging

from flask import Flask, url_for
from flask_ldap3_login import LDAP3LoginManager
from flask_login import LoginManager, login_user, UserMixin, current_user
from flask import render_template_string, redirect
from flask_ldap3_login.forms import LDAPLoginForm

from wtforms import TextField, Form
import urllib
from netaddr import *




login_manager = LoginManager(app)  # Setup a Flask-Login Manager
ldap_manager = LDAP3LoginManager(app)  # Setup a LDAP3 Login Manager.

users = {}

api = Api(app)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
app.logger.addHandler(ch)


# global variables for templates
labellist = []

# silly user model
class User(UserMixin):
    def __init__(self, dn, username, data):
        self.dn = dn
        self.id = username
        self.username = data['name']
        self.mail = data['mail']
        self.department = data['department']
        self.company = data['company']
        self.description = data['description']
        self.data = data

    def __repr__(self):
        return self.id

    def get_id(self):
        return self.id


# suite
# Declare a User Loader for Flask-Login.
# Simply returns the User if it exists in our 'database', otherwise
# returns None.
@login_manager.user_loader
def load_user(id):
    if id in users:
        return users[id]
    return None


# Declare The User Saver for Flask-Ldap3-Login
# This method is called whenever a LDAPLoginForm() successfully validates.
# Here you have to save the user, and return it so it can be used in the
# login controller.
@ldap_manager.save_user
def _save_user(dn, username, data, memberships):
    user = User(dn, username, data)
    users[username] = user
    return user

# Declare some routes for usage to show the authentication process.
@app.route('/dashboard')
def dashboard():
    # Redirect users who are not logged in.
    if not current_user or current_user.is_anonymous:
        return redirect(url_for('login'))

    return render_template('dashboard.html')


@app.route('/manual_login')
def manual_login():
    # Instead of using the form, you can alternatively authenticate
    # using the authenticate method.
    # This WILL NOT fire the save_user() callback defined above.
    # You are responsible for saving your users.
    app.ldap3_login_manager.authenticate('username', 'password')


@app.route('/login.html')
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Instantiate a LDAPLoginForm which has a validator to check if the user
    # exists in LDAP.
    form = LDAPLoginForm()

    if form.validate_on_submit():
        # Successfully logged in, We can now access the saved user object
        # via form.user.
        login_user(form.user)  # Tell flask-login to log them in.
        session['username'] = form.user.username
        session['infos'] = form.user.mail + " - " + form.user.department

        return redirect('/')

    return render_template('pages/login.html', form=form, title="Login")

# test autocomplete
@app.route('/search', methods=['GET', 'POST'])
def search():
    form = SearchForm(request.form)
    return render_template("search.html", form=form)

# autocompletion for search query
@app.route('/autocomplete', methods=['GET'])
def autocomplete():
    search = request.args.get('term')
    app.logger.debug(search)
    if not search:
        return json.jsonify([])
    json_list = []
    result = lu.graph.data(
        'match (x) where upper(x.name) =~ ".*' + search.upper() + '.*" and not labels(x) in ["Model", "Group"] return labels(x) as labels, x.name as x order by x limit 50')
    for i in result:
        json_list.append(i['labels'][0] + "=" + i['x'])
    return json.jsonify(json_list)


class SearchForm(Form):
    autocomplete = TextField('autocomplete', id='autocomplete')


# @app.route("/test")
# def testpage():
#     return render_template("sheet.html")
#

@app.route("/logout")
def logout():
    logout_user()
    session['username'] = None
    return redirect('/login.html')


class Ping(Resource):
    def get(self):
        if not current_user.is_authenticated and not 'application/json' in request.headers['Accept']:
            return redirect(url_for('login') + "?next=/api/get")
        if 'username' not in session and ('application/json' not in request.headers['Accept']):
            session['session'] = uuid.uuid4()
            return redirect(url_for('find'))
        if request.method == 'GET':
            ip = request.args.get('ip')
            if os.system("ping -c 1 " + str(ip)) == 0:
                return json.jsonify([ip + ' is allready used'])
            else:
                return json.jsonify([ip + ' is free to use'])
        return json.jsonify([])

class Pick(Resource):
    def get(self):
        if not current_user.is_authenticated and not 'application/json' in request.headers['Accept']:
            return redirect(url_for('login') + "?next=/api/get")
        if 'username' not in session and ('application/json' not in request.headers['Accept']):
            session['session'] = uuid.uuid4()
            return redirect(url_for('find'))
        node_label = None
        node_name = None
        if request.method == 'GET':
            req = []
            for i in request.query_string.split("&"):
                if "=" in i:
                    node_label = urllib.unquote(i.split('=')[0])
                    node_name = urllib.unquote(i.split('=')[1])
                    req.append({node_label or None: node_name or None})
                else:
                    if i:
                        next_label = i
                        req.append({i: None})
            if node_label and node_name:
                if node_label == 'Network':
                    range = list(IPNetwork(node_name))

                    # on remove du range les ip du net, du broad cast et des passerelles
                    ids = [-5, -4, -3, -2, -1, 0]
                    for i in ids:
                        range.remove(IPNetwork(node_name)[i])

                    # on recup les ip dans la base
                    ips = lu.graph.data("match (i:Ip)--(n:Network {name:'" + node_name + "'}) return i.name as ip")
                    # on les remove de la list
                    for i in ips:
                        if IPAddress(i['ip']) in range:
                            range.remove(IPAddress(i['ip']))
                    result = []
                    for i in range:
                        # on fait pas de ping , c'est trop lent !
                        # if os.system("ping -c 1 " + str(i)) != 0:
                        result.append(str(i))
        return json.jsonify(result)

class Show(Resource):
    def get(self):
        if not current_user.is_authenticated and not 'application/json' in request.headers['Accept']:
            return redirect(url_for('login') + "?next=/api/get")
        if 'username' not in session and ('application/json' not in request.headers['Accept']):
            session['session'] = uuid.uuid4()
            return redirect(url_for('find'))
        if request.method == 'GET':
            result = []
            for i in request.query_string.split("&"):
                if "=" in i:
                    node_label = urllib.unquote(i.split('=')[0])
                    node_name = urllib.unquote(i.split('=')[1])
                    result.append({node_label or None: node_name or None})
                else:
                    if i:
                        next_label = i
                        result.append({i: None})
        infos = []
        if node_label and node_name:
            for i in lu.graph.data("match (x:" + node_label + " { name:'" + node_name + "'}) return properties(x) as p"):
                for j in i['p']:
                    infos.append(j + ":" + str(i['p'][j]))
        app.logger.debug (str(infos))

        return json.jsonify(infos)

class Graph(Resource):
    def post(self):
        # exemple d'appel
        # curl -H 'Content-type: application/json' -H 'Accept: application/json' -X POST 'http://localhost:5000/api/graph' -d ' {"query" : "match p=(n)--(m) return p limit 1"}'
        if not current_user.is_authenticated and not 'application/json' in request.headers['Accept']:
            return redirect(url_for('login'))
        if 'username' not in session and ('application/json' not in request.headers['Accept']):
            session['session'] = uuid.uuid4()
            return redirect(url_for('Graph'))

        query=""
        req = request.get_json()
        if 'query' in req:
            query = req['query']
        return querygraph(query)

class Find(Resource):
    def post(self):
        app.logger.debug (str(request.form))
        if not current_user.is_authenticated and not 'application/json' in request.headers['Accept']:
            app.logger.debug ('redirect')
            return redirect(url_for('login') + "?next=" + url_for('find'))

        session['mode'] = request.form.get('mode')
        return redirect(url_for('find') + "?" + request.form.get('query'))


    def get(self):
        app.logger.debug (request.script_root)
        if not current_user.is_authenticated and not 'application/json' in request.headers['Accept']:
            return redirect(url_for('login') + "?next=/api/find")
        if 'username' not in session and ('application/json' not in request.headers['Accept']):
            session['session'] = uuid.uuid4()
            return redirect(url_for('find'))
        if request.method == 'GET':
            if 'mode' not in session:
                session['mode'] = 'Circular'

            labellist = []
            labellisttmp = lu.graph.data('match (x) return distinct labels(x) as x')
            for i in labellisttmp:
                labellist.append(i['x'][0])

            app.logger.debug (' Request : ' + (request.query_string))
            node_label = ""
            node_name = ""
            next_label = ""
            result = []
            for i in request.query_string.split("&"):
                if "=" in i:
                    node_label = urllib.unquote(i.split('=')[0])
                    node_name = urllib.unquote(i.split('=')[1])
                    result.append({node_label or None: node_name or None})
                else:
                    if i:
                        next_label = i
                        result.append({i: None})
            # mode circular (default) ou linear
            # circular : find for mutual interlinked
            # linear : find all links
            mode = "Circular"
            if 'mode' in session:
                mode = session['mode']

            # format de recherche libre query="label=value"
            if (len(result) > 0) and ('query' in result[0]):
                # si aucun argument, redirect sur find
                if result[0]['query'] == None:
                    return result_html(labellist,
                                       200,
                                       query="",
                                       node_label=node_label,
                                       node_name=node_name,
                                       next_label=next_label,
                                       infos=[],
                                       mode=mode,
                                       labels=labellist)

                # si query non type
                resultquery = []
                if "=" not in result[0]['query']:
                    tmpres = lu.graph.data('match (x) where upper(x.name) =~ ".*' + result[0][
                        'query'].upper() + '.*" and not labels(x) in ["Model", "Group"] return labels(x) as label, x.name as x')
                    for i in tmpres:
                        resultquery.append(i['label'][0] + '=' + i['x'])
                    return result_html(resultquery,
                                       200,
                                       query="",
                                       node_label=node_label,
                                       node_name=node_name,
                                       next_label=next_label,
                                       infos=[],
                                       mode=mode,
                                       labels=labellist)

                # si query de type label=value
                else:
                    q = result[0]['query'].split('=')
                    label = urllib.unquote(q[0])
                    if len(q) < 2:
                        name = ""
                    else:
                        name = urllib.unquote(q[1])
                    return redirect(url_for('find') + "?" + label + "=" + name)

            # Ppour rundeck, on peut formatter le resultat avec &mapto=<property> or &mapto=<Node>:<property>
            # exemple avec /api/find?Vlan&mapto=friendly on obtient le json :
            # {
            #   "V-INFRA-PRD-403":"V-INFRA-PRD",
            #   "V-ADCPALO-PRD-410":"V-ADCPALO-PRD",
            #   "V-INL-PRD-FRONT-600":"V-INL-PRD-FRO", ...
            # exmple avec /api/find?Server&mapto=Ip:name on obtient le json :
            # {
            #   "CTP-PRD-XXXX":"10.93.45.67",...

            # format de recherche libre query="label=value"
            mapto_label = None
            mapto_prop = None
            if (len(result) > 0) and ('mapto' in result[len(result) - 1]):
                mapto = result.pop(len(result) - 1)['mapto']
                if ':' in mapto:
                    mapto_label = mapto.split(':')[0]
                    mapto_prop = mapto.split(':')[1]
                else:
                    mapto_label = None
                    mapto_prop = mapto
            app.logger.debug(str(result))
            # else we get a query
            # use cases
            # A list? -> list les labels des nodes
            # A match (x0) return distinct labels(x0)

            # B list?Vlan -> liste les nodes Vlans
            # B match (x0:Vlan) return x0

            # C list?Vlan=v-abc -> liste les labels relies au Vlan=v-abc
            # C match (x0:Vlan { name:'V-INFRA-PRD'})--(x1) return distinct labels(x1)

            # D list?Vlan=v-abc&Server -> list les servers relies au vlan
            # D match (x0:Vlan { name:'V-INFRA-PRD'})--(x1:Server) return x1

            # E list?Vlan=v-abc&Server=xyz -> list les labels relies au server
            #  E : match (x0:Vlan { name:'V-INFRA-PRD'})--(x1:Server { name:'CTP-PRD-RDA'})
            #      optional match (x0:Vlan { name:'V-INFRA-PRD'})--(x2) return labels(x2)
            # etc...

            # on parcourt les arguments
            query = ""
            query_match = ""
            query_match_end = "(x0) "
            query_return = " not labels(x0) in ['Model', 'Group'] unwind labels(x0) as x return distinct x"
            labels = 0
            for i in result:
                key = i.keys()[0]
                val = i.values()[0]
                # Cas : C, E
                if val:
                    # si val contient une property sous forme : Label=property:value
                    if ':' in val:
                        nodeprop = val.split(':')[0]
                        if re.match('^[a-zA-Z].*', nodeprop):
                            check = lu.graph.data(
                                'match (x:' + key + ') where exists(x.' + nodeprop + ') return x limit 1')
                        else:
                            check = None
                        if check and len(check) > 0:
                            value = val.split(':')[1]
                        else:
                            nodeprop = 'name'
                            value = node_name
                    else:
                        nodeprop = 'name'
                        value = val
                    query_match += "(x" + str(labels) + ":" + key + " { " + nodeprop + ":'" + value + "'})--"
                    labels += 1
                    query_match_end = "(x" + str(labels) + ")"
                    query_return = " not labels(x" + str(labels) + ") in ['Model', 'Group'] unwind labels(x" + str(
                        labels) + ") as x return distinct x"
                # cas : B, D
                else:
                    if key:
                        query_match_end = "(x" + str(labels) + ":" + key + ")"
                    else:
                        query_match_end = "(x" + str(labels) + ")"
                    query_return = " return distinct x" + str(labels) + ".name as x"

            # contraintes mode
            #  circular (default) : x0--x1 and x1--x2 and x2--x0
            #  linear : x0--x1--x2
            query_constraint = ""
            if mode == "Circular":
                for i in range(0, labels + 1):
                    for j in range(0, i):
                        app.logger.debug ('i :' + str(i) + ' j :' + str(j))
                        query_constraint += "(x" + str(i) + ")--(x" + str(j) + ") "
                        app.logger.debug ('query_constraint : ' + query_constraint)
                        if not ((i == (labels)) and (j == (labels - 1))):
                            query_constraint += "and "
            elif mode == "Linear":
                if labels > 0:
                    for i in range(0, labels):
                        query_constraint += "(x" + str(i) + ")--"
                    query_constraint += "(x" + str(labels) + ")"

            else:
                pass

            # si on recherche les labels,
            if 'unwind labels' in query_return:
                href_query = "&"
            else:
                href_query = "="
            # if labels == 0:
            #     href_query=""

            if not query_constraint == "":
                if href_query == "&":
                    query_constraint = " where " + query_constraint + " and "
                else:
                    query_constraint = " where " + query_constraint
            else:
                if href_query == "&":
                    query_constraint = " where "

            if mapto_prop:
                if mapto_label:
                    query_match_mapto = '--(mapto_label:' + mapto_label + ')'
                    query_mapto_return = ', mapto_label.' + mapto_prop + ' as mapto'
                else:
                    query_match_mapto = ''
                    query_mapto_return = ', x' + str(labels) + '.' + mapto_prop + ' as mapto'
            else:
                query_match_mapto = ''
                query_mapto_return = ''

            query_order = " order by x"
            query = "match " + query_match + query_match_end + query_match_mapto + query_constraint + query_return + query_mapto_return + query_order
            visuquery = "match p=" + query_match + query_match_end + query_match_mapto + query_constraint + query_return + ", p limit 50"
            visuquery = visuquery.replace("'","\\'")
            app.logger.debug('Query : ' + query)
            app.logger.debug('VisuQuery : ' + visuquery)

            restmp = lu.graph.data(query)
            if mapto_prop:
                result = {}
                for i in restmp:
                    result.update({i['x']: i['mapto']})
            else:
                result = []
                for i in restmp:
                    if type(i['x']) == type([]):
                        for j in i['x']:
                            result += (j,)
                    else:
                        result += (i['x'],)
                if result == []:
                    result = [""]
                    # abort(404, message="Request {} doesn't work here".format(request.query_string))

            # return json.jsonify(result)

            infos = []
            if node_label and node_name:
                # si val contient une property sous forme : Label=property:value
                if ':' in node_name:
                    nodeprop = node_name.split(':')[0]
                    if re.match('^[a-zA-Z].*', nodeprop):
                        check = lu.graph.data(
                            'match (x:' + node_label + ') where exists(x.' + nodeprop + ') return x limit 1')
                    else:
                        check = None
                    if check and len(check) > 0:
                        value = node_name.split(':')[1]
                    else:
                        nodeprop = 'name'
                        value = node_name
                        # on verifie que prop est bien un propriete de node_label
                else:
                    nodeprop = 'name'
                    value = node_name
                node_name = value
                for i in lu.graph.data("match (x:" + node_label + " { " + nodeprop + ":'" + value + "'}) return properties(x) as p"):
                    for j in i['p']:
                        infos.append(j + ":" + str(i['p'][j]))
            app.logger.debug (str(infos))

            if 'application/json' in request.headers['Accept']:
                return json.jsonify(result)
            else:
                return result_html(result,
                                   200,
                                   query=request.query_string + href_query,
                                   node_label=node_label,
                                   node_name=node_name,
                                   next_label=next_label,
                                   mode=mode,
                                   infos=infos,
                                   labels=labellist,
                                   visuquery=visuquery)


@api.representation('text/html')
@api.representation('application/html')
def result_html(data, code, headers=None, query="", node_label="", node_name="", next_label="", mode="Circular",
                infos=[], labels=[], visuquery=""):
    resp = make_response(render_template("pages/find.html",
                                         query=query,
                                         list=data,
                                         node_label=node_label,
                                         node_name=node_name,
                                         next_label=next_label,
                                         mode=mode,
                                         infos=infos,
                                         labels=labels,
                                         visuquery=visuquery), code)
    resp.headers.extend(headers or {})
    return resp


api.add_resource(Server, '/api/server/<server_id>')
api.add_resource(Post, '/api/post')
api.add_resource(Link, '/api/nodea/<nodea>/nodeb/<nodeb>')
api.add_resource(Wawa, '/api/wawa/<label>')
api.add_resource(Whatsup, '/api/whatsup')
api.add_resource(jsontest, '/api/jsontest')
api.add_resource(catcher, '/api/catcher/<Rlabel>/<Rname>/from/<ProviderOrConsumer>/<label>/<name>')

api.add_resource(Find, '/api/find', endpoint='apifind')
api.add_resource(Find, '/find', endpoint='find')
api.add_resource(Show, '/api/show')
api.add_resource(Pick, '/api/pick')
api.add_resource(Ping, '/api/ping')
api.add_resource(JsonData, '/api/data/<datatype>')
api.add_resource(HOTSave, '/api/hots/<datatype>')
api.add_resource(Graph, '/api/graph')


# @app.route('/login.html')
# def login():
#     return render_template('pages/login.html', title="Login")

# on ajoute des variables disponibles à toutes les pages templates
@app.context_processor
def template_variables():
    if labellist == []:
        labellisttmp = lu.graph.data('match (x) unwind labels(x) as l return distinct l order by l')
        for i in labellisttmp:
            labellist.append(i['l'])
    return dict(labellist=labellist)


# todo : eventually make proc for tables of info
@app.route('/')
@app.route('/index.html')
def index():
    if not current_user.is_authenticated and not 'application/json' in request.headers['Accept']:
        return redirect(url_for('login'))
    if 'username' not in session and ('application/json' not in request.headers['Accept']):
        session['session'] = uuid.uuid4()
        return redirect(url_for('/'))

    tablelist={}

    # VM-METRICS
    query = '''
        match (d:Datacenter)--(s:Server)--(e:Environment)
        where s.hardware=~ "VM.*"
        and s.powerstate = "poweredOn"
        and d.name in ['CTP-PA3-EQX','CTP-PA4-EQX']
        return
            e.name as Environment, d.name as Datacenter, count(s) as nbVM,
            sum(toInt(s.cpu)) as vCpu, sum(toInt(s.ram))/1024 as vRamGB, sum(toInt(s.disk))/1024/1024 as vDiskGB
            '''
    result = lu.graph.data(query)
    table={}
    table['id'] = 'vm-metrics'
    table['comment'] = query
    table['header'] = ['Environment','Datacenter','nbVM','vCpu','vRamGB','vDiskGB']
    table['lines'] = []
    for i in result:
        tmpline=[]
        for j in table['header']:
            tmpline.append(i[j])
        table['lines'].append(tmpline)
    nbVM = 0
    vCpu = 0
    vRamGB = 0
    vDiskGB = 0

    for i in result:
        nbVM+=i['nbVM']
        vCpu += i['vCpu']
        vRamGB += i['vRamGB']
        vDiskGB += i['vDiskGB']
    table['stats'] = {'nbVM' : nbVM , 'vCpu': vCpu, 'vRamGB':vRamGB, 'vDiskGB':vDiskGB}
    tablelist[table['id']]=dict(table)

    # INFRA-METRICS
    query = '''
        match (d:Datacenter)--(h:Server)
        where h.name =~ ".*ESX.*" and h.hardware =~ "Server.*"
        return
            d.name as Datacenter,
            count(h) as nbESX, sum(toInt(h.cpu)) as CPU, sum(toFloat(h.ram))/1024/1024 as RAMTB
            '''
    result = lu.graph.data(query)
    table={}
    table['id'] = 'infra-metrics'
    table['comment'] = query
    table['header'] = ['Datacenter', 'nbESX', 'CPU', 'RAMTB']
    table['lines'] = []
    for i in result:
        tmpline=[]
        for j in table['header']:
            tmpline.append(i[j])
        table['lines'].append(tmpline)
    tablelist[table['id']] = dict(table)

    # NETWORK-METRICS
    query = ''' match (v:Vlan) return labels(v) as name, count(v) as nb
            union match (as:Adc_vs) return labels(as) as name, count(as) as nb
            union match (ls:Lc_vs) return labels(ls) as name, count(ls) as nb'''
    result = lu.graph.data(query)
    table = {}
    table['id'] = 'network-metrics'
    table['comment'] = query
    table['stats'] = {}
    for i in result:
        table['stats'].update({i['name'][0] : i['nb']})

    app.logger.debug ('Hello :')
    app.logger.debug (str(table))

    tablelist[table['id']] = dict(table)

    return render_template('pages/index.html', title="Infrastructure Metrics", header="Infrastructure Metrics", tablelist=tablelist)


@app.route('/blank.html')
def blank():
    return render_template('pages/blank.html', title="Blank", header="Blank", nav="Blank Page")


@app.route('/flot.html')
def flot():
    return render_template('pages/flot.html', title="Flot", header="Flot Charts", nav="Flot Page")


@app.route('/morris.html')
def morris():
    return render_template('pages/morris.html', title="Morris", header="Morris.js Charts", nav="Morris Page")


@app.route('/tables.html')
def tables():
    return render_template('pages/tables.html', title="Tables", header="Tables", nav="Tables Page")

@app.route('/sheetedit-server.html')
def editserver():
    return render_template('pages/sheetedit.html', title="Server", header="Server", nav="Servers Edition", source="server")

@app.route('/sheetedit-adcvip.html')
def editadcvip():
    return render_template('pages/sheetedit.html', title="ADCvip", header="ADCvip", nav="Adc VS List", source="adcvip")

@app.route('/networks.html')
def networks():
    tablelist={}

    # VM-METRICS
    query = '''
        match (n:Network)--(v:Vlan) where not n.name =~".*::.*"
        optional match (n:Network)--(i:Ip) where not n.name =~".*::.*"
        optional match (n:Network)--(g:Gateway) where not n.name =~".*::.*"
        optional match (n:Network)--(d:Datacenter) where not n.name =~".*::.*"
        with
            n.name as Network,
            count (distinct i.name) as UsedIp,
            collect (distinct g.name+"("+g.type+")") as Gateways,
            collect (distinct v.name) as Vlans,
            d.name as DC
        return
            Network, UsedIp, Gateways, Vlans, DC
            '''
    result = lu.graph.data(query)
    app.logger.debug((' netswork result :'+str(result)))
    table={}
    table['id'] = 'networks'
    table['comment'] = query
    table['header'] = ['Network','Brodcast','UsedIp','FreeIp','Gateways','Vlans', 'DC']
    table['lines'] = []
    for i in result:
        tmpline=[]
        for j in table['header']:
            val=''
            if j in i:
                if isinstance(i[j],list):
                    val = ",<br/>".join(i[j])
                else:
                    val = i[j]
            elif j == 'FreeIp':
                app.logger.debug('networks : ' + str(i['Network']))
                val = IPNetwork(i['Network']).size-i['UsedIp']-2
                #val = '<a href="'+url_for('pick')+'?Network='+i['Network']+'">'+str(val)+'</a>'
            # if j == 'Network':
            #     val = '< a href="#" onclick = "funcopenmodaledit(\'' + val + '\');" data-toggle="modal" data-target="#modaledit">' + val + '</a>'
            elif j == 'Brodcast':
                val = str(IPNetwork(i['Network']).broadcast)
            tmpline.append(val)
        table['lines'].append(tmpline)
    #stats
    nbnetworks = 0
    nbip = 0
    nbvlans = 0
    for i in result:
        nbnetworks += 1
        nbip += int(i['UsedIp'])
    nbvlans = lu.graph.data('match (v:Vlan) return count(distinct v) as nbvlan')[0]['nbvlan']
    table['stats'] = {'nbnetworks' : nbnetworks , 'nbip': nbip, 'nbvlans':nbvlans}
    tablelist[table['id']]=dict(table)

    app.logger.debug('networks : '+str(tablelist))

    return render_template('pages/networks.html', title="Networks", header="Networks", nav="Networks", source="Networks", tablelist=tablelist)

@app.route('/test.html')
def test():
    return render_template('pages/test.html', title="test", header="test", nav="test Page")

@app.route('/testalone.html')
def testalone():
    return render_template('pages/testalone.html', title="test", header="test", nav="test Page")

@app.route('/forms.html')
def forms():
    return render_template('pages/forms.html', title="Forms", header="Forms", nav="Forms Page")


@app.route('/panels-wells.html')
def panels_wells():
    return render_template('pages/panels-wells.html', title="Panels and Wells", header="Panels and Wells",
                           nav="Panels and Wells Page")


@app.route('/buttons.html')
def buttons():
    return render_template('pages/buttons.html', title="Buttons", header="Buttons", nav="Buttons Page")


@app.route('/notifications.html')
def notifications():
    return render_template('pages/notifications.html', title="Notifications", header="Notifications",
                           nav="Notifications Page")


@app.route('/typography.html')
def typography():
    return render_template('pages/typography.html', title="Typography", header="Typography", nav="Typography Page")


@app.route('/icons.html')
def icons():
    return render_template('pages/icons.html', title="Icons", header="Icons", nav="Icons Page")


@app.route('/grid.html')
def grid():
    return render_template('pages/grid.html', title="Grid", header="Grid", nav="Grid Page")
