from django.shortcuts import render_to_response
from django.template import RequestContext
from django.core.urlresolvers import reverse
from django.core.files.storage import default_storage
from django.http import HttpResponse
from django.conf import settings

from osqa.core.users.auth import *

def about(request):
    return render_to_response('about.html', context_instance=RequestContext(request))

def faq(request):
    data = {
        'gravatar_faq_url': reverse('faq') + '#gravatar',
        'send_email_key_url': reverse('send_email_key'),
        'ask_question_url': reverse('ask'),
    }
    return render_to_response('faq.html', data, context_instance=RequestContext(request))

def privacy(request):
    return render_to_response('privacy.html', context_instance=RequestContext(request))

def read_message(request):
    if request.method == "POST":
        if request.POST['formdata'] == 'required':
            request.session['message_silent'] = 1
            if request.user.is_authenticated():
                request.user.delete_messages()
    return HttpResponse('')    

def upload(request):
    class FileTypeNotAllow(Exception):
        pass
    class FileSizeNotAllow(Exception):
        pass
    class UploadPermissionNotAuthorized(Exception):
        pass

    #<result><msg><![CDATA[%s]]></msg><error><![CDATA[%s]]></error><file_url>%s</file_url></result>
    xml_template = "<result><msg><![CDATA[%s]]></msg><error><![CDATA[%s]]></error><file_url>%s</file_url></result>"

    try:
        f = request.FILES['file-upload']
        # check upload permission
        if not can_upload_files(request.user):
            raise UploadPermissionNotAuthorized

        # check file type
        file_name_suffix = os.path.splitext(f.name)[1].lower()
        if not file_name_suffix in settings.ALLOW_FILE_TYPES:
            raise FileTypeNotAllow

        # generate new file name
        new_file_name = str(time.time()).replace('.', str(random.randint(0,100000))) + file_name_suffix
        # use default storage to store file
        default_storage.save(new_file_name, f)
        # check file size
        # byte
        size = default_storage.size(new_file_name)
        if size > settings.ALLOW_MAX_FILE_SIZE:
            default_storage.delete(new_file_name)
            raise FileSizeNotAllow

        result = xml_template % ('Good', '', default_storage.url(new_file_name))
    except UploadPermissionNotAuthorized:
        result = xml_template % ('', _('uploading images is limited to users with >60 reputation points'), '')
    except FileTypeNotAllow:
        result = xml_template % ('', _("allowed file types are 'jpg', 'jpeg', 'gif', 'bmp', 'png', 'tiff'"), '')
    except FileSizeNotAllow:
        result = xml_template % ('', _("maximum upload file size is %sK") % settings.ALLOW_MAX_FILE_SIZE / 1024, '')
    except Exception:
        result = xml_template % ('', _('Error uploading file. Please contact the site administrator. Thank you. %s' % Exception), '')

    return HttpResponse(result, mimetype="application/xml")