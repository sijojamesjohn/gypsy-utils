from django.shortcuts import render
from django.http import HttpResponse
try:
	from django.utils import simplejson as json
except ImportError:
	import json

from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
# Create your views here.
try:
    from django.http import JsonResponse
except ImportError:
    from .utils import JsonResponse


from .decorators import company_user_required,owner_user_required
import logging

log = logging.getLogger('config.views')



class LoginRequiredMixin(object):
    @classmethod
    def as_view(cls, **initkwargs):
        view = super(LoginRequiredMixin, cls).as_view(**initkwargs)
        return staff_member_required(view,login_url='account_login')

class NormalLoginRequiredMixin(object):
    @classmethod
    def as_view(cls, **initkwargs):
        view = super(NormalLoginRequiredMixin, cls).as_view(**initkwargs)
        return login_required(view,login_url='resource_login')
        

class CompanyRequiredMixin(object):
    @classmethod
    def as_view(cls, **initkwargs):
        view = super(CompanyRequiredMixin, cls).as_view(**initkwargs)
        return login_required(view) # company_user_matches()
    
class OwnerRequiredMixin(object):
    @classmethod
    def as_view(cls, **initkwargs):
        view = super(OwnerRequiredMixin, cls).as_view(**initkwargs)
        return owner_user_required(view) # company_user_matches()

class AjaxableResponseMixin(object):
    """
    Mixin to add AJAX support to a form.
    Must be used with an object-based FormView (e.g. CreateView)
    """
    def form_invalid(self, form):
        log.info("ajax form invalid %s" % form.errors)
        response = super(AjaxableResponseMixin, self).form_invalid(form)
        if self.request.is_ajax():
            return JsonResponse(form.errors, status=400)
        else:
            return response

    def form_valid(self, form):
        log.info("ajax form valid %s" % self.request.is_ajax())
        # We make sure to call the parent's form_valid() method because
        # it might do some processing (in the case of CreateView, it will
        # call form.save() for example).
        response = super(AjaxableResponseMixin, self).form_valid(form)
        if self.request.is_ajax():
            data = {
                'pk': self.object.pk,
            }
            return JsonResponse(data)
        else:
            return response


class JSONResponseMixin(object):
    """
    A mixin that can be used to render a JSON response.

    Usage in view:
    
    class JSONView(JSONResponseMixin, TemplateView):
    def render_to_response(self, context, **response_kwargs):
        return self.render_to_json_response(context, **response_kwargs)


    """
    def render_to_json_response(self, context, **response_kwargs):
        """
        Returns a JSON response, transforming 'context' to make the payload.
        """
        return HttpResponse(
            self.convert_context_to_json(context),
            content_type='application/json',
            **response_kwargs
        )

    def convert_context_to_json(self, context):
        "Convert the context dictionary into a JSON object"
        # Note: This is *EXTREMELY* naive; in reality, you'll need
        # to do much more complex handling to ensure that arbitrary
        # objects -- such as Django model instances or querysets
        # -- can be serialized as JSON.
        return json.dumps(context)
