 import os.path

from django.conf.urls.defaults import *
from django.utils.translation import ugettext as _

from osqa.core.sitemap import QuestionsSitemap
from osqa.core.feed import RssLastestQuestionsFeed

import views as app

feeds = {
    'rss': RssLastestQuestionsFeed
}

sitemaps = {
    'questions': QuestionsSitemap
}

APP_PATH = os.path.dirname(os.path.dirname(__file__))

urlpatterns = patterns('',
    (r'^%s' % _('account/'), include('django_authopenid.urls')),
    url(r'^%s$' % _('about/'), app.about, name='about'),
    url(r'^%s$' % _('faq/'), app.faq, name='faq'),
    url(r'^%s$' % _('privacy/'), app.privacy, name='privacy'),

    (r'^content/(?P<path>.*)$', 'django.views.static.serve',
        {'document_root': os.path.join(APP_PATH, '../templates/content').replace('\\','/')}
    ),
    (r'^%s(?P<path>.*)$' % _('upfiles/'), 'django.views.static.serve',
        {'document_root': os.path.join(APP_PATH, '../templates/upfiles').replace('\\','/')}
    ),
    (r'^%s$' % _('upload/'), app.upload),
    url(r'^sitemap.xml$', 'django.contrib.sitemaps.views.sitemap', {'sitemaps': sitemaps}),
    url(r'^feeds/(?P<url>.*)/$', 'django.contrib.syndication.views.feed', {'feed_dict': feeds}),
    (r'^favicon\.ico$', 'django.views.generic.simple.redirect_to', {'url': '/content/images/favicon.ico'}),
    (r'^favicon\.gif$', 'django.views.generic.simple.redirect_to', {'url': '/content/images/favicon.gif'}),

    url(r'^%s%s$' % (_('messages/'), _('markread/')),app.read_message, name='read_message'),
    (r'^i18n/', include('django.conf.urls.i18n')),
)