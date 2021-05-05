from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse_lazy
import logging

import sys

log = logging.getLogger('config.decorator')

# example 
def company_user_required(func):
    def actual_decorator(request,*args, **kwargs):
        #do something useful here
        path = request.build_absolute_uri()

        if request.user.is_authenticated():
            try:
                company_admin = request.user.userprofile and request.user.userprofile.company or request.user.userprofile.admin_companies.all()
            except:
                log.info("Company admin not found %s" % sys.exc_info()[0])
                company_admin = False
            log.info("Company admin not %s" % company_admin)
            if company_admin:                        
                return func(request,*args, **kwargs)
            else:
                return HttpResponseRedirect(reverse_lazy('testimonials-admin'))
    return actual_decorator


def owner_user_required(func):
    def actual_decorator(request,*args, **kwargs):
        #do something useful here
        path = request.build_absolute_uri()
        owner_admin = None
        if request.user.is_authenticated():
            try:
                owner_admin = request.user.groups.filter(name='OwnerAdmin').exists()
            except:
                log.info("Company admin not found %s" % sys.exc_info()[0])
                owner_admin = False
            log.info("Company admin not %s" % owner_admin)
            if owner_admin:                        
                return func(request,*args, **kwargs)
            else:
                return HttpResponseRedirect(reverse_lazy('resource_logout'))
        else:
            return HttpResponseRedirect(reverse_lazy('resource_login'))
    return actual_decorator

