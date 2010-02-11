from django.conf.urls.defaults import *
from django.utils.translation import ugettext as _

import views as app

urlpatterns = patterns('',
    url(r'^%s(?P<id>\d+)/%s$' % (_('answers/'), _('edit/')), app.edit_answer, name='edit_answer'),
    url(r'^%s(?P<id>\d+)/%s$' % (_('answers/'), _('revisions/')), app.answer_revisions, name='answer_revisions'),
    url(r'^%s(?P<id>\d+)/%s$' % (_('questions/'), _('answer/')), app.answer, name='answer'),
)