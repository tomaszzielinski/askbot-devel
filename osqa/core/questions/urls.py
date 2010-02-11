from django.conf.urls.defaults import *
from django.utils.translation import ugettext as _

import views as app

urlpatterns = patterns('',
    url(r'^$', app.index, name='index'),
    url(r'^%s$' % _('questions/'), app.questions, name='questions'),
    url(r'^%s%s$' % (_('questions/'), _('ask/')), app.ask, name='ask'),
    url(r'^%s%s$' % (_('questions/'), _('unanswered/')), app.unanswered, name='unanswered'),
    url(r'^%s(?P<id>\d+)/%s$' % (_('questions/'), _('edit/')), app.edit_question, name='edit_question'),
    url(r'^%s(?P<id>\d+)/%s$' % (_('questions/'), _('close/')), app.close, name='close'),
    url(r'^%s(?P<id>\d+)/%s$' % (_('questions/'), _('reopen/')), app.reopen, name='reopen'),
    url(r'^%s(?P<id>\d+)/%s$' % (_('questions/'), _('revisions/')), app.question_revisions, name='question_revisions'),
    url(r'^%s(?P<id>\d+)/' % _('question/'), app.question, name='question'),

    url(r'^%s$' % _('search/'), app.search, name='search'),
)