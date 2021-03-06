__author__ = 'drichner'
"""
 docklr -- views.py
Copyright (C) 2014  Dan Richner

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License along
with this program; if not, write to the Free Software Foundation, Inc.,
51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""
import os
from flask import Blueprint, render_template, request
from models import Config
from forms import AddConfig, NewConfig,ConfigForm
from appinit import db
from urlparse import urlparse
from common.DiscoveryClient import DiscoveryClient
import json
import etcd
import requests
from jinja2 import TemplateNotFound

home_page = Blueprint('home_page', __name__,
                      template_folder='templates',
                      static_folder='static')


# helpers
def getAllConfigs():
    return Config.query.all()


def ping(host):
    hostname = host
    response = os.system("ping -c 1 -t 1 " + hostname)

    # and then check the response...
    if response == 0:
        return True
    else:
        return False


# remderers

@home_page.route('/')
def index():
    mform = AddConfig()
    newconfigfrm = NewConfig()
    return render_template('index.html', configs=getAllConfigs(), addconfigform=mform, newconfigform=newconfigfrm)


@home_page.route('clusterinfo/<id>')
def get_cluster_info(id):
    conf = Config.query.get(id)
    r = requests.get(conf.cluster_etcd_locator_url)
    return r.text


@home_page.route('clusterlayout/<id>')
def get_cluster_layout(id):
    conf = Config.query.get(id)
    r = requests.get(conf.cluster_etcd_locator_url)
    cluster_info = json.loads(r.text)
    hosts = []
    try:
        for node in cluster_info['node']['nodes']:
            host = {}
            u = urlparse(node['value'])
            host['name'] = u.hostname
            host['status'] = 'down'
            print u.hostname
            print u.port
            status = ping(u.hostname)
            host['durl'] = node['key'].replace('/_etcd/registry/', '')
            if status:
                host['status'] = 'up'
                # check if node is master
                client = etcd.Client(host=u.hostname, port=4001)
                try:
                    t = client.leader
                    if urlparse(t).hostname == u.hostname:
                        host['status'] = 'master'
                except Exception:
                    pass

            hosts.append(host)
    except KeyError:
        pass
    return render_template('cluster_layout.html', hosts=hosts)

@home_page.route('clusterconfig/<id>', methods=['GET', 'PUT','DELETE'])
def clusterconfig(id):
    conf = Config.query.get(id)
    if request.method == 'PUT':
        conf.cluster_etcd_locator_url = request.form['cluster_etcd_locator_url']
        conf.cluster_name = request.form['cluster_name']
        conf.private_key = request.form['private_key']
        db.session.add(conf)
        db.session.commit()
        return json.dumps({'status': 'OK', 'cluster': {'id': conf.id, 'cluster_name': conf.cluster_name,
                                                       'cluster_etcd_locator_url': conf.cluster_etcd_locator_url}})
    return json.dumps({'status': 'Failure', 'message': 'Method not supported'})

@home_page.route('addclusterconfig', methods=['GET', 'POST'])
def addclusterconfig():
    print request
    if request.method == 'POST':
        # save a new config
        nc = Config()
        nc.cluster_name = request.form['cluster_name']
        nc.cluster_etcd_locator_url = request.form['cluster_etcd_locator_url']
        nc.private_key = request.form['primary_key']
        db.session.add(nc)
        db.session.commit()
        return json.dumps({'status': 'OK', 'cluster': {'id': nc.id, 'cluster_name': nc.cluster_name,
                                                       'cluster_etcd_locator_url': nc.cluster_etcd_locator_url}})
    else:
        print request


@home_page.route('newclusterconfig', methods=['GET', 'POST'])
def newclusterconfig():
    print request
    tokenUrl = "https://discovery.etcd.io/new"
    if request.method == 'POST':
        # save a new config
        nc = Config()
        nc.cluster_name = request.form['cluster_name']
        try:
            # create the new token
            r = requests.get(tokenUrl)
            cluster_etcd_locator_url = r.text
            nc.cluster_etcd_locator_url = cluster_etcd_locator_url
            db.session.add(nc)
            db.session.commit()
        except Exception:
            pass
        return json.dumps({'status': 'OK','cluster': {'id': nc.id, 'cluster_name': nc.cluster_name,
                                                       'cluster_etcd_locator_url': nc.cluster_etcd_locator_url}})
    else:
        return json.dumps({'status': 'Fail'})


@home_page.route('removenode/<path:ident>')
def removenode(ident):
    client = DiscoveryClient(host="discovery.etcd.io", port=443, protocol='https')
    client.delete("/" + ident)
    return json.dumps({'status': 'OK'});


# CRUD Test
@home_page.route('frm/config', methods=['GET', 'POST'])
@home_page.route('frm/config/<id>', methods=['GET', 'POST'])
def config(id=None):
    print id
    action='/frm/config'
    if request.method == 'GET' and not id:
        # just get the new form for adding
        form = ConfigForm()
        method='POST'
        template_name='frm-config.html'
        return render_template(template_name, form=form, action=action,method=method,id=id)
    if request.method == 'GET' and id:
        # get the config
        conf = Config.query.get(id)
        form = ConfigForm()
        form.process(obj=conf)
        action+="/%s" % id
        method='POST'
        template_name='frm-config.html'
        return render_template(template_name, form=form, action=action,method=method,id=id)
    if request.method == 'POST' and not id:
        # new record
        conf=Config()
        form = ConfigForm(request.form)
        form.populate_obj(conf)
        db.session.add(conf)
        db.session.commit()
        return json.dumps({'status': 'OK','cluster': conf.dict})

    if request.method == 'POST' and id:
        conf=Config.query.get(id)
        form = ConfigForm(request.form)
        form.populate_obj(conf)
        db.session.add(conf)
        db.session.commit()
        return json.dumps({'status': 'OK','cluster': conf.dict})


