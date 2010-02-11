from osqa.models import Question
from django.conf import settings
from djangosphinx.manager import SphinxSearch


Question.add_to_class('search', SphinxSearch(
                                   index=' '.join(settings.SPHINX_SEARCH_INDICES),
                                   mode='SPH_MATCH_ALL',
                                )
                      )

from django.db import models

class TestModel(models.Model):
    name = models.CharField(max_length=16)

    class Meta:
        """Meta Class for your model."""
        app_label = 'osqa'