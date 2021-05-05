try:
    from django.utils import simplejson as json
except ImportError:
    import json 

from django.core.serializers.base import Serializer as BaseSerializer
from django.core.serializers.python import Serializer as PythonSerializer
from django.core.serializers.json import Serializer as JsonSerializer
from django.utils import six

from django.http import HttpResponse
from django.template.defaultfilters import slugify
import re
import operator

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection, send_mail, EmailMessage # SMTPConnection depreceated used  get_connection() 
from django.template import loader, Template, RequestContext, TemplateDoesNotExist, Context
from django.utils.encoding import smart_str
from django.contrib.sites.models import Site
from django.template.defaultfilters import slugify        
from django.template.loader import render_to_string, get_template
import csv

import logging

log = logging.getLogger('config.utils')


try:
    import sendgrid
    from sendgrid.helpers.mail import *
except ImportError:
    log.info("Please install Sendgrid")


import hashlib
import base64


class ExtBaseSerializer(BaseSerializer):
    """ Abstract serializer class; everything is the same as Django's base except from the marked lines """
    def serialize(self, queryset, **options):
        self.options = options

        self.stream = options.pop('stream', six.StringIO())
        self.selected_fields = options.pop('fields', None)
        self.selected_props = options.pop('props', None)  # added this
        self.use_natural_keys = options.pop('use_natural_keys', False)
        self.use_natural_foreign_keys = options.pop('use_natural_foreign_keys', False)
        self.use_natural_primary_keys = options.pop('use_natural_primary_keys', False)

        self.start_serialization()
        self.first = True
        for obj in queryset:
            self.start_object(obj)
            concrete_model = obj._meta.concrete_model
            for field in concrete_model._meta.local_fields:
                if field.serialize:
                    if field.rel is None:
                        if self.selected_fields is None or field.attname in self.selected_fields:
                            self.handle_field(obj, field)
                    else:
                        if self.selected_fields is None or field.attname[:-3] in self.selected_fields:
                            self.handle_fk_field(obj, field)
            for field in concrete_model._meta.many_to_many:
                if field.serialize:
                    if self.selected_fields is None or field.attname in self.selected_fields:
                        self.handle_m2m_field(obj, field)
            # added this loop
            if self.selected_props:
                for field in self.selected_props:
                    self.handle_prop(obj, field)
            self.end_object(obj)
            if self.first:
                self.first = False
        self.end_serialization()
        return self.getvalue()

    # added this function
    def handle_prop(self, obj, field):
        self._current[field] = getattr(obj, field)


class ExtPythonSerializer(ExtBaseSerializer, PythonSerializer):
    pass


class ExtJsonSerializer(ExtPythonSerializer, JsonSerializer):
    pass

def create_username(email):
    hash_user = hashlib.sha1()
    hash_user.update(email)
    return base64.b64encode(hash_user.digest())
    
class JsonResponse(HttpResponse):
    """
        JSON response
    """
    def __init__(self, content, mimetype='application/json', status=None, content_type=None):
        super(JsonResponse, self).__init__(
            content=json.dumps(content),
            mimetype=mimetype,
            status=status,
            content_type=content_type,
        )

def SlugifyUniquely(value, model, slugfield="slug"):
        """Returns a slug on a name which is unique within a model's table

        This code suffers a race condition between when a unique
        slug is determined and when the object with that slug is saved.
        It's also not exactly database friendly if there is a high
        likelyhood of common slugs being attempted.

        A good usage pattern for this code would be to add a custom save()
        method to a model with a slug field along the lines of:

                from django.template.defaultfilters import slugify

                def save(self):
                    if not self.id:
                        # replace self.name with your prepopulate_from field
                        self.slug = SlugifyUniquely(self.name, self.__class__)
                super(self.__class__, self).save()

        Original pattern discussed at
        http://www.b-list.org/weblog/2006/11/02/django-tips-auto-populated-fields
        """
        suffix = 0
        potential = base = slugify(value)
        while True:
                if suffix:
                        potential = "-".join([base, str(suffix)])
                
                if not model.objects.filter(**{slugfield: potential}).count():
                        return potential
                # we hit a conflicting slug, so bump the suffix & try again
                suffix += 1



EMAIL_RE = re.compile(
    r"(^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*"  # dot-atom
    r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]|\\[\001-011\013\014\016-\177])*"' # quoted-string
    r')@(?:[A-Z0-9-]+\.)+[A-Z]{2,6}$', re.IGNORECASE)

class InvalidEmailException(Exception):
    def __init__(self,email):
        if isinstance(email,list):
            self.email = email
        else:
            self.email = ["%s" % email]
        
    def __str__(self):
        return 'Email %s is invalid' % ','.join(self.email)


def is_valid_email(email):
    """
    return True or InvalidEmailException against a given email address
    
    >>> is_valid_email('test@test-email.com')
    True
    >>> is_valid_email('test@test email.com')
    Traceback (most recent call last):
    InvalidEmailException: Email test@test email.com is invalid
    """  
    if EMAIL_RE.search(email):
        return True
    raise InvalidEmailException(email)


def validate_emails(emails,delimiter=','):
    """
    validates one or more emails in a string or list
    tolerates whitespace in a string
    returns given emails upon success or throws InvalidEmailException
    
    args:
        emails  - str,unicode or list of emails
    kwarg:
        delimiter - character used as delimiter if emails is a string, default = ','
    
    #validate a single string    
    >>> validate_emails('test@test.com')
    ['test@test.com']
    
    #validate multiple emails in a string
    >>> validate_emails('test@test.com,test2@test.com')
    ['test@test.com', 'test2@test.com']
    
    #validate multiple emails in a string with a delimiter other than ','
    >>> validate_emails('test@test.com;test2@test.com',delimiter=';')
    ['test@test.com', 'test2@test.com']
    
    #can tolerate whitespace
    >>> validate_emails('test@test.com ; test2@test.com',delimiter=';')
    ['test@test.com', 'test2@test.com']
    
    #can accept a list
    >>> validate_emails(['list@list.com','list2@list.com'])
    ['list@list.com', 'list2@list.com']
    
    #single error returns a InvalidEmailException
    >>> validate_emails('test@te st.com')
    Traceback (most recent call last):
    InvalidEmailException: Email test@te st.com is invalid
    
    #InvalidEmailException contains 'email', a list of all the invalid emails
    >>> try:
    ...     validate_emails('test@bad email.com ; test2@bad email.com; test@goodemail.com',delimiter=';')
    ... except InvalidEmailException,e:
    ...     print e.email
    ['test@bad email.com', 'test2@bad email.com']
    """
    if isinstance(emails,basestring):
        emails = emails.split("%s" % delimiter)
        emails = [x.strip() for x in emails if x]
    errors = []
    if not emails is None:
        for e in emails:
            try:
                is_valid_email(e)
            except InvalidEmailException:
                errors.append(e)
                    
    if errors:
        raise InvalidEmailException(errors)
                
    return emails


def send_mass_html_mail(datatuple, fail_silently=False, auth_user=None,
                   auth_password=None):
    """
    Copy of send_mass_mail, but uses EmailMultiAlterative for html sending
    database tuple takes 4 args (subject,html_message,text_message,from_email,recipient_list,bcc_list)
    
    Given a datatuple of (subject, html_message, text_message from_email, recipient_list), sends
    each message to each recipient list. Returns the number of e-mails sent.

    If from_email is None, the DEFAULT_FROM_EMAIL setting is used.
    If auth_user and auth_password are set, they're used to log in.
    If auth_user is None, the EMAIL_HOST_USER setting is used.
    If auth_password is None, the EMAIL_HOST_PASSWORD setting is used.

    """
    log.debug('send mass html mail called')
    connection = get_connection(username=auth_user, password=auth_password,
                                fail_silently=fail_silently)
    
##    connection = SMTPConnection(username=auth_user, password=auth_password,
##                                fail_silently=fail_silently)
    
    messages = []
    
    for subject,message,text_message,sender,recipient,bcc in datatuple:
    
        msg = EmailMultiAlternatives(subject,text_message,sender,recipient,bcc=bcc)
        msg.attach_alternative(message,'text/html')
        messages.append(msg)
    if settings.DEBUG:
        log.debug('settings DEBUG is true, returning %s messages' % len(messages))
        return messages
    log.info('sending mass html mail - %s messages' % len(messages))
    return connection.send_messages(messages)

def test_smtp():
    try:
        conn = get_connection() #SMTPConnection()
        conn.open()
        conn.close()
        return True
    except:
        log.critical('SMTP NOT AVAILABLE')
        pass
    return False

class FormEmailUtil:
    _context = None
    
    def __init__(self,form,fromemail,toemail,subject,template_file,language='',extra_context={},fallback_template=''):
        log.debug('init formemail util')
        self.form = form
        self.fromemail = fromemail
        self.to_email = toemail #comma delimited string of emails
        self.subject = subject
        self.template_file = template_file
        self.language = language
        self.extra_context = extra_context
        self.fallback_template = fallback_template
        self.HIDDEN_FIELDS = ['cform','honeypot','content_type','timestamp','security_hash'] #messy, refactor
        self._context = None
        #ooptional extra context kwargs:
        #_message_override if there is no template and dont want to print the form
        
    

    def send(self):
        log.debug('formemail util send')
        html,text = self.message()
        log.debug('message text html: %s' % html)
        log.debug('message text txt: %s' % text)
        if html and not text:
            #this should be impossible - text should always generate
            text = html
        message_kwargs = self.get_message_dict()
        log.debug('got message kwargs - %s' % message_kwargs)
        message_kwargs['body'] = text
        #test for a connection, if none, send to the log
        if not test_smtp():
            log.warn('FormEmailUtil send - NO SMTP CONNECTION for email: %s' % message_kwargs)
            
        if html:
            msg = EmailMultiAlternatives(**message_kwargs)
            log.debug('EmailMultiAlternatives init')
            msg.attach_alternative(html, "text/html")
            msg.send()
            log.info('sent html email - %s' % message_kwargs)
        else:
            msg = EmailMessage(**message_kwargs)
            log.debug('EmailMessage init')
            msg.send()
            log.info('sent txt email - %s' % message_kwargs)
        
        
    #    #thanks to James Bennet
    def get_message_dict(self):
        if not self.form.is_valid():
            raise ValueError("Message cannot be sent from invalid contact form")
        message_dict = {}
        log.info('get_message_dict')
        for message_part,function in (('from_email','from_email'), ('to','recipient_list'), ('subject','get_subject')):
            log.debug('getting %s' % message_part)
            attr = getattr(self, function)
            
            message_dict[message_part] = callable(attr) and attr() or attr
        
        return message_dict
    
    
    def get_context(self):
        if not self.form and not self.form.is_valid():
            raise ValueError("Cannot generate Context when there is no form")
        if self._context is None:
            log.debug('getting context')
            this_context = self.form.cleaned_data
            #convert the cleaned_data keys into slugs
            this_context = {'form_field' : {} } #reliees on no cleaned item called 'form field'
            #!add validation for form_field reserved variable
            for k,v in self.form.cleaned_data.iteritems():
                s = slugify(k)
                this_context["%s" % s] = v
                #problem with spaces parsing '-' in template, for backwards
                #comparisbility keep old method, but add '_fields'] to context
                #with bugfixed solution to use '_'  instead of '-'
                this_context['form_field']["%s" % s.replace('-','_')] = v
            this_context.update(self.extra_context)
            this_context
            log.debug('thiscontext %s' % this_context)
            self._context = RequestContext(self.form.request,dict=this_context)
            log.debug('context - %s' % self._context)
        return self._context
    

    def from_email(self):
        if self.fromemail:
            return self.fromemail
        return self._from_email()
    
    def recipient_list(self):
        return self.get_to_email()
    
    def message(self,type='text'):
        """
        Renders the body of the message to a string.
        
        """
        log.debug('getting message')
        html_template,txt_template = self.get_template()
        log.debug('retrieved templates, html: %s, txt: %s' % (html_template,txt_template))
        html_message = ''
        txt_message = ''
        if html_template:
            try:
                html_message = html_template.render(self.get_context())
                log.debug('generating html email from templates ')
            except:
                pass
        
        if txt_template:
            try:
                txt_message = txt_template.render(self.get_context())
                log.debug('generating txt email from templates')
            except:
                pass
            
        if not txt_message:
            log.debug('No templates found, generating txt email automatically')
            if self.extra_context.has_key('_message_override'):
                txt_message = self.extra_context['_message_override']
            else:
                #refactor using map?
                for k,v in self.form.cleaned_data.iteritems():
                    if k not in self.HIDDEN_FIELDS:
                        txt_message += "%s : %s\n" % (k,v)
    
        return (html_message,txt_message)
            
                

    def get_subject(self):
        """
        Renders the subject of the message to a string.
        
        """
        log.debug('get subejct')
        template = Template(self.subject)
        log.debug('got subject template')
        subject = template.render(self.get_context())
        log.debug('rendered subject %s' % ''.join(subject.splitlines()))
        return ''.join(subject.splitlines())
    
    def get_template(self):

        html,text = self._get_template_names()
        html_template = None
        text_template = None
        try:
            log.debug('trying html templates %s' % html)
            html_template = loader.select_template(html)
            log.debug('got html template: %s' % html_template)
        except TemplateDoesNotExist:
            log.info('form html template does not exist')
            
        try:
            log.debug('trying txt templates %s' % text)
            text_template = loader.select_template(text)
            log.debug('got txt template: %s' % text_template)
        except TemplateDoesNotExist:
            log.info('form txt template does not exist')
        return (html_template,text_template)
            

    def _get_template_names(self):
        html = []
        txt = []
        lang = None
        file = self.template_file
        
        try:
            if self.language:
                lang = self.language
            else:
                lang = get_request_language(self.form.request)
        except:
            lang = settings.LANGUAGE_DEFAULT
            
            
        if lang:
            html.append("forms/%s/%s.html" % (lang,file))
            txt.append("forms/%s/%s.txt" % (lang,file))
        
        html.append("forms/%s.html" % file)
        txt.append("forms/%s.txt" % file)
        
        if self.fallback_template:
            html.append("forms/%s.html" % self.fallback_template)
            txt.append("forms/%s.txt" % self.fallback_template)
        return (html,txt)    
    
        
    def _from_email(self):
        e = self.fromemail
        if not e:
           e = self._default_email()
        return e
    
    def get_to_email(self):
        """returns a string of emails, multiple emails should be comma delimited, form handles conversion"""
        e = self.to_email
        if not e:
            e = self._default_email()
        return [email for email in e.split(',') if email]
        
    
    
    def _default_email(self):
        from configuration import get_site_email
        return get_site_email()
    


def email_from_template(template, ctx, to,subject=None,reply_to=None, sender_name=None,attachment=None,
                        fail_silently=False,sender_email=None,bcc_list=[],email_host=None,email_username=None,
                        email_password=None,email_port=None):
    """
    email from template`
    
    args:
        template - path to template (from MEDIA_ROOT), dropping format extension
        ctx - context for rendering message and subject
        to - *list* of email addresses to send email
    kwargs:
        subject - subject for mail              default:None
        reply_to - reply to for the email              default:None
        sender_name - Name of the sender              default:None
        sender_email - From email of the sender              default:None
        fail_silently - default False
        bcc_list - *list* of blind carbon copy
        
    will look for templates with .txt and .html, .txt is required,
    .html is optional. requires txt file of same name as template finishing
    '_subject' from which to draw subject line,
    
    e.g. "emails/form_email" template will look for emails/form_email.txt
    (required), emails/form_email.html (optional) and
    emails/form_email_subject.txt (required)
    """
    #propogate a TemplateDoesNotExist excpetion for a txt file
    #but hide if html, just sending a txt email
    
    html = None
    
    txt = get_template("%s.txt" % template)
    try:
        html = get_template("%s.html" % template)
    except TemplateDoesNotExist:
        pass
    
    #txt/html variables become actual text 
    #txt = txt.render(Context(ctx))
    #django 1.9
    txt = txt.render(ctx)
    if html is not None:
        html = html.render(ctx)
    if not subject:
        subject = get_template('%s_subject.txt' % template)
    else:
        subject = Template(subject)
    subject = subject.render(ctx).replace('\n','')
    
    headers = {}
    #from configuration.models import Configuration
    #c = Configuration.objects.get_current()
    
    site = Site.objects.get_current()
    domain = site.domain.replace('www.','')
    email = getattr(settings,'DEFAULT_FROM_EMAIL','no-reply@%s' % domain)
    if sender_email:
        email = sender_email
    
    if sender_name:
        sender = '%s <%s>' % (sender_name, email)
    else:
        sender = email
        
    if not reply_to is None:
        headers['Reply-To'] = reply_to
    #if not sender_name is None:
    #    headers['From'] = sender_name
    #    
    connection = get_connection(host=email_host,port=email_port,username=email_username, password=email_password,
                                fail_silently=fail_silently)

    email = EmailMultiAlternatives(subject, txt,
                 sender, to, headers=headers,bcc=bcc_list,connection=connection)
    if html:
        email.attach_alternative(html,"text/html")
    if attachment:
        if isinstance(attachment,list):
            for attachfile in attachment:
                email.attach_file(attachfile)
        else:
            email.attach_file(attachment)
    email.send(fail_silently=fail_silently)
    log.info("Email Sent to %s from %s,bcc %s, sub %s text %s" % (to,sender,bcc_list,subject,txt))



def encode_me(file):
    from StringIO import StringIO
    from mimetools import encode
    file_to_send=open(file,'rb')
    encoded_object = StringIO()
    encode(file_to_send,encoded_object,'base64')
    file_to_send.close()
    file = encoded_object.getvalue()
    return file

def email_from_template_sendgrid(template, ctx, to,subject=None,reply_to=None, sender_name=None,attachment=None,
                        fail_silently=False,sender_email=None,bcc_list=[]):
    """
    email from template`
    
    args:
        template - path to template (from MEDIA_ROOT), dropping format extension
        ctx - context for rendering message and subject
        to - *list* of email addresses to send email
    kwargs:
        subject - subject for mail              default:None
        reply_to - reply to for the email              default:None
        sender_name - Name of the sender              default:None
        sender_email - From email of the sender              default:None
        fail_silently - default False
        bcc_list - *list* of blind carbon copy
        
    will look for templates with .txt and .html, .txt is required,
    .html is optional. requires txt file of same name as template finishing
    '_subject' from which to draw subject line,
    
    e.g. "emails/form_email" template will look for emails/form_email.txt
    (required), emails/form_email.html (optional) and
    emails/form_email_subject.txt (required)
    """
    #propogate a TemplateDoesNotExist excpetion for a txt file
    #but hide if html, just sending a txt email
    
    html = None
    
    txt = get_template("%s.txt" % template)
    try:
        html = get_template("%s.html" % template)
    except TemplateDoesNotExist:
        pass
    
    #txt/html variables become actual text 
    txt = txt.render(Context(ctx))
    if html is not None:
        html = html.render(Context(ctx))
    if not subject:
        subject = get_template('%s_subject.txt' % template)
    else:
        subject = Template(subject)
    subject = subject.render(Context(ctx)).replace('\n','')
    
    headers = {}
    #from configuration.models import Configuration
    #c = Configuration.objects.get_current()
    
    site = Site.objects.get_current()
    domain = site.domain.replace('www.','')
    from_email = getattr(settings,'DEFAULT_FROM_EMAIL','no-reply@%s' % domain)
    if sender_email:
        from_email = sender_email
    
    if sender_name:
        sender = u'%s <%s>' % (sender_name, from_email)
    else:
        sender = from_email
        
    if not reply_to is None:
        headers['Reply-To'] = reply_to
    #if not sender_name is None:
    #    headers['From'] = sender_name
    #    
    # email = EmailMultiAlternatives(subject, txt,
    #              sender, to, headers=headers,bcc=bcc_list)
    # if html:
    #     email.attach_alternative(html,"text/html")
    # if attachment:
    #     if isinstance(attachment,list):
    #         for attachfile in attachment:
    #             email.attach_file(attachfile)
    #     else:
    #         email.attach_file(attachment)

    # email.send(fail_silently=fail_silently)



    sg = sendgrid.SendGridAPIClient(apikey=getattr(settings,'SENDGRID_API_KEY',''))
    mail = Mail()
    if sender_name:
        mail.set_from(Email(u"%s" % from_email, u"%s" % sender_name))
    else:
        mail.set_from(Email(u"%s" % from_email))

    mail.set_subject(subject)

    personalization = Personalization()
    for bcc_email in bcc_list:
        personalization.add_bcc(Email(u"%s" % bcc_email))
    
    personalization.set_subject(subject)
    
    #personalization.set_send_at(1443636843)
    mail.add_personalization(personalization)
    mail.add_content(Content("text/plain", txt))
    mail.add_content(Content("text/html", html))
    if attachment:
        if isinstance(attachment,list):
            for attachfile in attachment:
                attachment = Attachment()
                attachment.set_content(encode_me(attachfile))
                # attachment.set_type("application/pdf")
                # attachment.set_filename("balance_001.pdf")
                attachment.set_disposition("attachment")
                attachment.set_content_id(attachfile)
                mail.add_attachment(attachment)
        else:
            attachment = Attachment()
            attachment.set_content(encode_me(attachfile))
            # attachment.set_type("application/pdf")
            # attachment.set_filename("balance_001.pdf")
            attachment.set_disposition("attachment")
            attachment.set_content_id(attachfile)
            mail.add_attachment(attachment)
    
    mail.set_template_id("13b8f94f-bcae-4ec6-b752-70d6cb59f932")
    
    mail_settings = MailSettings()
    mail_settings.set_bcc_settings(BCCSettings(True, Email(from_email)))
    mail_settings.set_bypass_list_management(BypassListManagement(True))
    #mail_settings.set_footer_settings(FooterSettings(True, "Footer Text", "<html><body>Footer Text</body></html>"))
    mail_settings.set_sandbox_mode(SandBoxMode(False))
    mail_settings.set_spam_check(SpamCheck(True, 1, "https://spamcatcher.sendgrid.com"))
    mail.set_mail_settings(mail_settings)

    # tracking_settings = TrackingSettings()
    # tracking_settings.set_click_tracking(ClickTracking(True, True))
    # tracking_settings.set_open_tracking(OpenTracking(True, "Optional tag to replace with the open image in the body of the message"))
    # tracking_settings.set_subscription_tracking(SubscriptionTracking(True, "text to insert into the text/plain portion of the message", "<html><body>html to insert into the text/html portion of the message</body></html>", "Optional tag to replace with the open image in the body of the message"))
    # tracking_settings.set_ganalytics(Ganalytics(True, "some source", "some medium", "some term", "some_content", "some_campaign"))
    # mail.set_tracking_settings(tracking_settings)

    if not reply_to is None:
        mail.set_reply_to(Email(reply_to))

    return mail.get()


    response = sg.client.mail.send.post(request_body=mail.get())
    print(response.status_code)
    print(response.body)
    print(response.headers)

def exportcsv(qs, fields=None,extra_fields=[]):
    model = qs.model
    
    file = open('%s.csv' % slugify(model.__name__),'wb')
    writer = csv.writer(file)
    # Write headers to CSV file
    if fields:
        headers = fields
    else:        
        headers = []
        for field in model._meta.fields:
            headers.append(field.name)
    if extra_fields:
        headers.extend(extra_fields)
        
    writer.writerow(headers)
    # Write data to CSV file
    for obj in qs:
        row = []
        for field in headers:
            if field in headers:
                val = getattr(obj, field)
                if callable(val):
                    val = val()
                # work around csv unicode limitation
                if type(val) == unicode:
                    val = val.encode("utf-8")
                row.append(val)
        writer.writerow(row)
    # Return CSV file to browser as download
    file.close()


if __name__ == '__main__':
    import doctest
    doctest.testmod()
