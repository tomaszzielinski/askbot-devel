from django.conf.urls.defaults import *
from django.utils.translation import ugettext as _

import views as app

urlpatterns = patterns('',
    url(r'^%s$' % _('users/'),app.users, name='users'),
    url(r'^%s(?P<id>\d+)/%s$' % (_('users/'), _('edit/')), app.edit_user, name='edit_user'),
    url(r'^%s(?P<id>\d+)//*' % _('users/'), app.user, name='user'),
    url(r'^%s(?P<id>\d+)/$' % _('moderate-user/'), app.moderate_user, name='moderate_user'),
    url(r'^%s$' % _('feedback/'), app.feedback, name='feedback'),
    url(r'^%s$' % _('logout/'), app.logout, name='logout'),
)