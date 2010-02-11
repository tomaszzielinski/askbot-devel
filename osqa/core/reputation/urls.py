from django.conf.urls.defaults import *
from django.utils.translation import ugettext as _

import views as app

urlpatterns = patterns('',
    url(r'^%s$' % _('badges/'),app.badges, name='badges'),
    url(r'^%s(?P<id>\d+)//*' % _('badges/'), app.badge, name='badge'),
)