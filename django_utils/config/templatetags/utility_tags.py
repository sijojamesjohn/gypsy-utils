import re

from django import template
from django.core.urlresolvers import NoReverseMatch
from django.template.defaulttags import url as django_url_func

register = template.Library()


def ifurlmatch(parser, token):
    """
    This is a block tag similar to an {% if %}{% endif %} block.

    It will conditionally display the content between matching
    {% ifurlmatch %}{% endifurlmatch %} tags if the URL path (minus hostname)
    matches the parameter, which should be a string or regex pattern.
    """
    tag_name, pattern = token.split_contents()

    # Arg, split_contents doesn't remove encapsing quotes.
    pattern = pattern.strip('"\'')
    nodelist = parser.parse(('endifurlmatch'))
    parser.delete_first_token()
    return UrlMatchNode(nodelist, pattern)


class UrlMatchNode(template.Node):
    def __init__(self, nodelist, pattern):
        self.pattern = pattern
        self.nodelist = nodelist

    def render(self, context):
        if self._path_matches(context):
            return self.nodelist.render(context)
        return ''

    def _path_matches(self, context):
        req = context['request']
        path = req.META.get('PATH_INFO', '/')
        return re.search(self.pattern, path) is not None

register.tag("ifurlmatch", ifurlmatch)


def ifpathmatch(parser, token):
    """
    This is a block tag similar to an {% if %}{% endif %} block.
    It will conditionally display the content between matching
    {% ifpathmatch %}{% endifpathmatch %} tags if the current page's URL
    matches the named path from v1.py passed in as the parameters.

    BUG/NOTE: Currently all string parameters to this must be quoted, or it
    will never match. For example, to match the
    relationships:clients:activity URL path you would need to do the
    following:
    {% ifpathmatch "relationships:clients:activity" "my-client-slug" %}
    Parameters which aren't literal strings shouldn't be quoted.
    For example, if passing in a client object's slug:
    {% ifpathmatch "relationships:clients:activity" myclientobj.slug %}
    """

    nodelist = parser.parse(('endifpathmatch'))
    parser.delete_first_token()
    return NamedPathMatchNode(nodelist, parser, token, True)


def ifpathcontains(parser, token):
    """
    Similar to ifpathmatch, but will return true if url contains passed in path
    """
    nodelist = parser.parse(('endifpathcontains'))
    parser.delete_first_token()
    return NamedPathMatchNode(nodelist, parser, token, False)


class NamedPathMatchNode(template.Node):
    def __init__(self, nodelist, parser, token, strict):
        self.token = token
        self.nodelist = nodelist
        self.parser = parser
        self.strict = strict

    def render(self, context):
        reversed_url = None
        try:
            reversed_url = django_url_func(
            self.parser, self.token).render(context)
        except NoReverseMatch:
            pass

        if self.strict:
            if reversed_url is not None and self._path_matches(
                context, reversed_url):
                return self.nodelist.render(context)
        else:
            if reversed_url is not None and self._path_contains(
                context, reversed_url):
                return self.nodelist.render(context)
        return ''

    def _path_matches(self, context, reversed_url):
        req = context['request']
        return req.META.get('PATH_INFO', '/') == reversed_url

    def _path_contains(self, context, reversed_url):
        req = context['request']
        return reversed_url in req.META.get('PATH_INFO', '/')

register.tag("ifpathmatch", ifpathmatch)
register.tag("ifpathcontains", ifpathcontains)


@register.filter
def replace(value,arg=None):
    if arg.find(':') != -1:
        source,repl = arg.split(':')
        return value.replace(source,repl)
    return value