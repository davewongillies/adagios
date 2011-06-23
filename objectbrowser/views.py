# -*- coding: utf-8 -*-
#
# Copyright 2010, Pall Sigurdsson <palli@opensource.is>
#
# This script is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This script is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from django.shortcuts import render_to_response, redirect
from django.core import serializers
from django.http import HttpResponse, HttpResponseServerError
from django.utils import simplejson
from django.core.context_processors import csrf

import sys
from adagios.okconfig.forms import AddHostForm
sys.path.insert(1, '/opt/pynag')
import configurator.okconfig

from pynag.Model import *
from pynag import Model
from forms import *

def test(request):
        return index(request)

def home(request):
        return redirect('adagios')

def index(request):
	return list_hosts(request)

## DEPRECATED for list_objects
def list_hosts(request):
    c = {}
    c['hosts'] = Host.objects.all
    return render_to_response('hosts.html', c)

## Deprecated for list_objects
def list_contacts(request):
    c = {}
    c['contacts'] = Contact.objects.all
    
    return render_to_response('configurator/list_contacts.html', c)


def list_objects( request, object_type=None, display_these_objects=None ):
    c = {}
    c['messages'] = m = []
    c['objects'] = objects = []
    
    search = tmp = {}
    for k,v in request.GET.items():
        k,v = str(k), str(v)
        if k == 'object_type':
            object_type = v
        if v == 'None':
            search[k] = None
        else:
            search[k] = v
    # If a non-existent object_type is requested, lets display a warning
    if not Model.string_to_class.has_key(object_type):
            m.append('Model does not have any objects of type %s, valid types are %s' % (object_type, Model.string_to_class.keys()))
            #return list_object_types(request)
            #return render_to_response('objectbrowser/list_object_types.html', c)
    else:
        myClass = Model.string_to_class[object_type]
    # Lets decide if we want to get everything or apply a filter
    if display_these_objects is not None:
        c['objects'] = display_these_objects
    elif len(search) == 0:
        c['objects'] = myClass.objects.all
    else:
        c['objects'] = myClass.objects.filter(**search)
        m.append("I used the filter %s=%s" % (search.keys(), search.values()))
    m.append( "Found %s objects of type %s" % (len(c['objects']), object_type))
    c['object_type'] = object_type
    return render_to_response('list_objects.html', c)

def list_object_types(request):
    c = {}
    c['object_types'] = t = []
    for name,Class in Model.string_to_class.items():
        if name != None:
            active = inactive = 0
            all_instances = Class.objects.all
            for i in all_instances:
                if i['register'] == "0":
                    inactive += 1
                else:
                    active += 1
            c['object_types'].append( (name, active, inactive) )
    return render_to_response('list_object_types.html', c)


def view_object( request, object_id=None, object_type=None, shortname=None):
    ''' Allows one to one specific object definition '''
    c = {}
    c.update(csrf(request))
    c['messages'] = m = []
    c['errors'] = []
    # Get our object
    if object_id != None:
        o = ObjectDefinition.objects.get_by_id(id=object_id)
    elif object_type != None and shortname != None:
        # TODO: if multiple objects are found, display a list
        otype = Model.string_to_class[object_type]
        o = otype.objects.get_by_shortname(shortname)
    else:
        raise ValueError("Object not found")
    
    if request.method == 'GET' or request.POST.has_key('definition'):
        c['form'] = PynagForm( pynag_object=o, initial=o._original_attributes )
        c['defined_attributes'] = PynagForm(pynag_object=o, initial=o._original_attributes, show_undefined_attributes=False)
        c['undefined_attributes'] = PynagForm(pynag_object=o, initial=o._original_attributes, show_defined_attributes=False, show_inherited_attributes=False)
    
    if request.method == 'POST':
        if request.POST.has_key('definition'):
            'Manual edit of the form'
            o.rewrite( str_new_definition=request.POST.get('definition')  )
            m.append("Object Saved manually to '%s'" % o['filename'])
        else:
            "this is the 'advanced_edit' form "
            c['form'] = PynagForm( pynag_object=o, data=request.POST )
            if c['form'].is_valid():
                c['form'].save()
                m.append("Object Saved to %s" % o['filename'])
            else:
                c['errors'].append( "Problem reading form input")
            #c['defined_attributes'] = PynagForm(pynag_object=o, data=o._original_attributes, show_undefined_attributes=False)
            #c['undefined_attributes'] = PynagForm(pynag_object=o, data=o._original_attributes, show_defined_attributes=False, show_inherited_attributes=False)

    c['my_object'] = o
    c['attr_val'] = o.get_attribute_tuple()
    c['manual_edit'] = ManualEditObjectForm(initial={'definition':o['meta']['raw_definition'], })
    if o['object_type'] == 'host':
        return _view_host(request, c)
    try: c['command_line'] = o.get_effective_command_line()
    except: pass
    try: c['object_macros'] = o.get_all_macros()
    except: pass
    try: c['effective_hostgroups'] = o.get_effective_hostgroups()
    except: pass
    try: c['effective_contacts'] = o.get_effective_contacts()
    except: pass
    c['effective_contactgroups'] = o.get_effective_contact_groups()
    try: c['effective_members'] = o.get_effective_members()
    except: pass
    return render_to_response('view_object.html', c)

def _view_host( request, c):
    ''' This is a helper function to view_object '''
    host = c['my_object']
    if not c.has_key('errors'): c['errors'] = []
    
    try: c['effective_services'] = host.get_effective_services()
    except: c['errors'].append( "Configuration error while looking up services")
    
    try: c['command_line'] = host.get_effective_command_line()
    except: c['errors'].append( "Configuration error while looking up command_line")
    
    try: c['effective_hostgroups'] = host.get_effective_hostgroups()
    except: c['errors'].append( "Configuration error while looking up hostgroups")
    
    try: c['effective_contacts'] = host.get_effective_contacts()
    except: c['errors'].append( "Configuration error while looking up contacts")
    
    try: c['effective_contactgroups'] = host.get_effective_contact_groups()
    except: c['errors'].append( "Configuration error while looking up contact_groups")
    
    try: c['object_macros'] = host.get_all_macros()
    except: c['errors'].append( "Configuration error while looking up macros")
    
    return render_to_response('view_host.html', c)

def confighealth( request  ):
    c = {}
    c['messages'] = m = []
    c['objecthealth'] = s = {}
    c['booleans'] = {}
    services_no_description = Service.objects.filter(register="1", service_description=None)
    hosts_without_contacts = []
    hosts_with_invalid_contacts = []
    hosts_without_services =[]
    objects_with_invalid_parents = []
    services_without_contacts = []
    services_using_hostgroups = []
    services_without_icon_image = []
    for i in ObjectDefinition.objects.all:
        continue
        try:
            i.get_parents()
        except ValueError:
            objects_with_invalid_parents.append(i)
    for i in Host.objects.filter(register="1"):
            if i['contacts'] is None and i['contact_groups'] is None:
                hosts_without_contacts.append(i)
            if i.get_effective_services() == []:
                hosts_without_services.append(i)
    for i in Service.objects.filter(register="1"):
            if i['contacts'] is None and i['contact_groups'] is None:
                services_without_contacts.append(i)
            if i['hostgroups'] is not None:
                services_using_hostgroups.append(i)
            if i['icon_image'] is None:
                services_without_icon_image.append(i)
    c['booleans']['Nagios Service has been reloaded since last configuration change'] = not Model.config.needs_reload()
    c['booleans']['Adagios configuration cache is up-to-date'] = not Model.config.needs_reparse()
    c['booleans']['OKConfig is installed and working'] = configurator.okconfig.verify()
    s['Services with no "service_description"'] = services_no_description            
    s['Hosts without any contacts'] = hosts_without_contacts
    s['Services without any contacts'] = services_without_contacts
    s['Objects with invalid "use" attribute'] = objects_with_invalid_parents
    s['Services applied to hostgroups'] = services_using_hostgroups
    s['Services without a logo'] = services_without_icon_image
    s['Hosts without Service Checks'] = hosts_without_services
    if request.GET.has_key('show') and s.has_key( request.GET['show'] ):
        objects =  s[request.GET['show']]
        print len(objects)
        return list_objects(request,display_these_objects=objects )
    else:
        return render_to_response('suggestions.html', c)

def view_nagioscfg(request):
    c = {}
    c['filename'] = Model.config.cfg_file
    c['content'] = Model.config.maincfg_values
    c['content'].sort()
    return render_to_response('view_configfile.html', c)
    
 