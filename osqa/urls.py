from django.conf.urls.defaults import *
from django.utils.translation import ugettext as _

from osqa.core.urls import urlpatterns as core_urls
from osqa.core.questions.urls import urlpatterns as question_urls
from osqa.core.answers.urls import urlpatterns as answer_urls
from osqa.core.meta.urls import urlpatterns as meta_urls
from osqa.core.reputation.urls import urlpatterns as reputation_urls
from osqa.core.auth.urls import urlpatterns as auth_urls
from osqa.core.users.urls import urlpatterns as users_urls

from osqa.modules.utils import get_module_urlpatterns

urlpatterns = (
                core_urls +
                question_urls +
                answer_urls +
                meta_urls +
                auth_urls +
                users_urls +
                reputation_urls +
                get_module_urlpatterns()
)
