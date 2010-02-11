from django.conf.urls.defaults import *
from django.utils.translation import ugettext as _

import views as app

urlpatterns = patterns('',
    url(r'^%s$' % _('tags/'), app.tags, name='tags'),
    url(r'^%s(?P<tag>[^/]+)/$' % _('tags/'), app.tag, name='tag_questions'),
    url(r'^%s(?P<id>\d+)/%s$' % (_('questions/'), _('comments/')), app.question_comments, name='question_comments'),
    url(r'^%s(?P<id>\d+)/%s$' % (_('answers/'), _('comments/')), app.answer_comments, name='answer_comments'),
    url(r'^%s(?P<object_id>\d+)/%s(?P<comment_id>\d+)/%s$' % (_('questions/'), _('comments/'),_('delete/')), \
                                                app.delete_comment, kwargs={'commented_object_type':'question'},\
                                                name='delete_question_comment'),

    url(r'^%s(?P<object_id>\d+)/%s(?P<comment_id>\d+)/%s$' % (_('answers/'), _('comments/'),_('delete/')), \
                                                app.delete_comment, kwargs={'commented_object_type':'answer'}, \
                                                name='delete_answer_comment'), \

    url(r'^%s%s(?P<tag>[^/]+)/$' % (_('mark-tag/'),_('interesting/')), app.mark_tag, \
                                kwargs={'reason':'good','action':'add'}, \
                                name='mark_interesting_tag'),

    url(r'^%s%s(?P<tag>[^/]+)/$' % (_('mark-tag/'),_('ignored/')), app.mark_tag, \
                                kwargs={'reason':'bad','action':'add'}, \
                                name='mark_ignored_tag'),

    url(r'^%s(?P<tag>[^/]+)/$' % _('unmark-tag/'), app.mark_tag, \
                                kwargs={'action':'remove'}, \
                                name='mark_ignored_tag'),

    url(r'^%s$' % _('command/'), app.ajax_command, name='call_ajax'),
    url(r'^%s(?P<id>\d+)/%s$' % (_('questions/'), _('vote/')), app.vote, name='vote'),
)