import datetime

from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes import generic
from django.contrib.sitemaps import ping_google
from django.core.urlresolvers import reverse
from django.template.defaultfilters import slugify
from django.utils.http import urlquote  as django_urlquote
from django.utils.translation import ugettext as _
from django.conf import settings

#from osqa.core.questions.models import *
from osqa.core.meta.models import *
from osqa.core.shared.models import *

from managers import AnswerManager

import logging
import osqa.core.questions.models

class Answer(models.Model):
    question = models.ForeignKey('osqa.Question', related_name='answers')
    author   = models.ForeignKey(User, related_name='answers')
    added_at = models.DateTimeField(default=datetime.datetime.now)
    # Status
    wiki        = models.BooleanField(default=False)
    wikified_at = models.DateTimeField(null=True, blank=True)
    accepted    = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)
    deleted     = models.BooleanField(default=False)
    deleted_by  = models.ForeignKey(User, null=True, blank=True, related_name='deleted_answers')
    locked      = models.BooleanField(default=False)
    locked_by   = models.ForeignKey(User, null=True, blank=True, related_name='locked_answers')
    locked_at   = models.DateTimeField(null=True, blank=True)
    # Denormalised data
    score                = models.IntegerField(default=0)
    vote_up_count        = models.IntegerField(default=0)
    vote_down_count      = models.IntegerField(default=0)
    comment_count        = models.PositiveIntegerField(default=0)
    offensive_flag_count = models.SmallIntegerField(default=0)
    last_edited_at       = models.DateTimeField(null=True, blank=True)
    last_edited_by       = models.ForeignKey(User, null=True, blank=True, related_name='last_edited_answers')
    html                 = models.TextField()
    comments             = generic.GenericRelation(Comment)
    votes                = generic.GenericRelation(Vote)
    flagged_items        = generic.GenericRelation(FlaggedItem)

    objects = AnswerManager()

    get_comments = get_object_comments
    get_last_update_info = post_get_last_update_info

    def save(self,**kwargs):
        super(Answer,self).save(**kwargs)
        try:
            ping_google()
        except Exception:
            logging.debug('problem pinging google did you register you sitemap with google?')

    def get_user_vote(self, user):
	if user.__class__.__name__ == "AnonymousUser":
	    return None

        votes = self.votes.filter(user=user)
        if votes and votes.count() > 0:
            return votes[0]
        else:
            return None

    def get_latest_revision(self):
        return self.revisions.all()[0]

    def get_question_title(self):
        return self.question.title

    def get_absolute_url(self):
        return '%s%s#%s' % (reverse('question', args=[self.question.id]), django_urlquote(slugify(self.question.title)), self.id)

    class Meta:
        app_label = 'osqa'
        db_table = u'answer'

    def __unicode__(self):
        return self.html

class AnswerRevision(models.Model):
    """A revision of an Answer."""
    answer     = models.ForeignKey(Answer, related_name='revisions')
    revision   = models.PositiveIntegerField()
    author     = models.ForeignKey(User, related_name='answer_revisions')
    revised_at = models.DateTimeField()
    summary    = models.CharField(max_length=300, blank=True)
    text       = models.TextField()

    def get_absolute_url(self):
        return reverse('answer_revisions', kwargs={'id':self.answer.id})

    def get_question_title(self):
        return self.answer.question.title

    class Meta:
        app_label = 'osqa'
        db_table = u'answer_revision'
        ordering = ('-revision',)

    def save(self, **kwargs):
        """Looks up the next available revision number if not set."""
        if not self.revision:
            self.revision = AnswerRevision.objects.filter(
                answer=self.answer).values_list('revision',
                                                flat=True)[0] + 1
        super(AnswerRevision, self).save(**kwargs)

class AnonymousAnswer(models.Model):
    question = models.ForeignKey('osqa.Question', related_name='anonymous_answers')
    session_key = models.CharField(max_length=40)  #session id for anonymous questions
    wiki = models.BooleanField(default=False)
    added_at = models.DateTimeField(default=datetime.datetime.now)
    ip_addr = models.IPAddressField(max_length=21) #allow high port numbers
    author = models.ForeignKey(User,null=True)
    text = models.TextField()
    summary = models.CharField(max_length=180)

    def publish(self,user):
        from views import create_new_answer
        added_at = datetime.datetime.now()
        #print user.id
        create_new_answer(question=self.question,wiki=self.wiki,
                            added_at=added_at,text=self.text,
                            author=user)
        self.delete()

    class Meta:
        app_label = 'osqa'
