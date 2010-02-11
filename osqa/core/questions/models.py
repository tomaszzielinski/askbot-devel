import datetime

from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes import generic
from django.contrib.sitemaps import ping_google
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from django.conf import settings

from osqa.core.answers.models import Answer
from osqa.core.meta.models import *
from osqa.core.shared.models import *
from osqa.core.shared.const import CLOSE_REASONS

from managers import QuestionManager

import logging

class Question(models.Model):
    title    = models.CharField(max_length=300)
    author   = models.ForeignKey(User, related_name='questions')
    added_at = models.DateTimeField(default=datetime.datetime.now)
    tags     = models.ManyToManyField(Tag, related_name='questions')
    # Status
    wiki            = models.BooleanField(default=False)
    wikified_at     = models.DateTimeField(null=True, blank=True)
    answer_accepted = models.BooleanField(default=False)
    closed          = models.BooleanField(default=False)
    closed_by       = models.ForeignKey(User, null=True, blank=True, related_name='closed_questions')
    closed_at       = models.DateTimeField(null=True, blank=True)
    close_reason    = models.SmallIntegerField(choices=CLOSE_REASONS, null=True, blank=True)
    deleted         = models.BooleanField(default=False)
    deleted_at      = models.DateTimeField(null=True, blank=True)
    deleted_by      = models.ForeignKey(User, null=True, blank=True, related_name='deleted_questions')
    locked          = models.BooleanField(default=False)
    locked_by       = models.ForeignKey(User, null=True, blank=True, related_name='locked_questions')
    locked_at       = models.DateTimeField(null=True, blank=True)
    followed_by     = models.ManyToManyField(User, related_name='followed_questions')
    # Denormalised data
    score                = models.IntegerField(default=0)
    vote_up_count        = models.IntegerField(default=0)
    vote_down_count      = models.IntegerField(default=0)
    answer_count         = models.PositiveIntegerField(default=0)
    comment_count        = models.PositiveIntegerField(default=0)
    view_count           = models.PositiveIntegerField(default=0)
    offensive_flag_count = models.SmallIntegerField(default=0)
    favourite_count      = models.PositiveIntegerField(default=0)
    last_edited_at       = models.DateTimeField(null=True, blank=True)
    last_edited_by       = models.ForeignKey(User, null=True, blank=True, related_name='last_edited_questions')
    last_activity_at     = models.DateTimeField(default=datetime.datetime.now)
    last_activity_by     = models.ForeignKey(User, related_name='last_active_in_questions')
    tagnames             = models.CharField(max_length=125)
    summary              = models.CharField(max_length=180)
    html                 = models.TextField()
    comments             = generic.GenericRelation(Comment)
    votes                = generic.GenericRelation(Vote)
    flagged_items        = generic.GenericRelation(FlaggedItem)

    objects = QuestionManager()

    def delete(self):
        super(Question, self).delete()
        try:
            ping_google()
        except Exception:
            logging.debug('problem pinging google did you register you sitemap with google?')

    def save(self, **kwargs):
        """
        Overridden to manually manage addition of tags when the object
        is first saved.

        This is required as we're using ``tagnames`` as the sole means of
        adding and editing tags.
        """
        initial_addition = (self.id is None)
        super(Question, self).save(**kwargs)
        try:
            ping_google()
        except Exception:
            logging.debug('problem pinging google did you register you sitemap with google?')
        if initial_addition:
            tags = Tag.objects.get_or_create_multiple(self.tagname_list(),
                                                      self.author)
            self.tags.add(*tags)
            Tag.objects.update_use_counts(tags)

    def tagname_list(self):
        """Creates a list of Tag names from the ``tagnames`` attribute."""
        return [name for name in self.tagnames.split(u' ')]

    def tagname_meta_generator(self):
        return u','.join([unicode(tag) for tag in self.tagname_list()])

    def get_absolute_url(self):
        return '%s%s' % (reverse('question', args=[self.id]), django_urlquote(slugify(self.title)))

    def has_favorite_by_user(self, user):
        if not user.is_authenticated():
            return False
        return FavoriteQuestion.objects.filter(question=self, user=user).count() > 0

    def get_answer_count_by_user(self, user_id):
        query_set = Answer.objects.filter(author__id=user_id)
        return query_set.filter(question=self).count()

    def get_question_title(self):
        if self.closed:
            attr = CONST['closed']
        elif self.deleted:
            attr = CONST['deleted']
        else:
            attr = None
        if attr is not None:
            return u'%s %s' % (self.title, attr)
        else:
            return self.title

    def get_revision_url(self):
        return reverse('question_revisions', args=[self.id])

    def get_latest_revision(self):
        return self.revisions.all()[0]

    get_comments = get_object_comments

    def get_last_update_info(self):

        when, who = post_get_last_update_info(self)

        answers = self.answers.all()
        if len(answers) > 0:
            for a in answers:
                a_when, a_who = a.get_last_update_info()
                if a_when > when:
                    when = a_when
                    who = a_who

        return when, who

    def get_update_summary(self,last_reported_at=None,recipient_email=''):
        edited = False
        if self.last_edited_at and self.last_edited_at > last_reported_at:
            if self.last_edited_by.email != recipient_email:
                edited = True
        comments = []
        for comment in self.comments.all():
            if comment.added_at > last_reported_at and comment.user.email != recipient_email:
                comments.append(comment)
        new_answers = []
        answer_comments = []
        modified_answers = []
        commented_answers = []
        import sets
        commented_answers = sets.Set([])
        for answer in self.answers.all():
            if (answer.added_at > last_reported_at and answer.author.email != recipient_email):
                new_answers.append(answer)
            if (answer.last_edited_at
                and answer.last_edited_at > last_reported_at
                and answer.last_edited_by.email != recipient_email):
                modified_answers.append(answer)
            for comment in answer.comments.all():
                if comment.added_at > last_reported_at and comment.user.email != recipient_email:
                    commented_answers.add(answer)
                    answer_comments.append(comment)

        #create the report
        if edited or new_answers or modified_answers or answer_comments:
            out = []
            if edited:
                out.append(_('%(author)s modified the question') % {'author':self.last_edited_by.username})
            if new_answers:
                names = sets.Set(map(lambda x: x.author.username,new_answers))
                people = ', '.join(names)
                out.append(_('%(people)s posted %(new_answer_count)s new answers') \
                                % {'new_answer_count':len(new_answers),'people':people})
            if comments:
                names = sets.Set(map(lambda x: x.user.username,comments))
                people = ', '.join(names)
                out.append(_('%(people)s commented the question') % {'people':people})
            if answer_comments:
                names = sets.Set(map(lambda x: x.user.username,answer_comments))
                people = ', '.join(names)
                if len(commented_answers) > 1:
                    out.append(_('%(people)s commented answers') % {'people':people})
                else:
                    out.append(_('%(people)s commented an answer') % {'people':people})
            url = settings.APP_URL + self.get_absolute_url()
            retval = '<a href="%s">%s</a>:<br>\n' % (url,self.title)
            out = map(lambda x: '<li>' + x + '</li>',out)
            retval += '<ul>' + '\n'.join(out) + '</ul><br>\n'
            return retval
        else:
            return None

    def __unicode__(self):
        return self.title

    class Meta:
        app_label = 'osqa'
        db_table = u'question'

class QuestionView(models.Model):
    question = models.ForeignKey(Question, related_name='viewed')
    who = models.ForeignKey(User, related_name='question_views')
    when = models.DateTimeField()

    class Meta:
        app_label = 'osqa'

class FavoriteQuestion(models.Model):
    """A favorite Question of a User."""
    question      = models.ForeignKey(Question)
    user          = models.ForeignKey(User, related_name='user_favorite_questions')
    added_at = models.DateTimeField(default=datetime.datetime.now)
    
    class Meta:
        app_label = 'osqa'
        db_table = u'favorite_question'
    def __unicode__(self):
        return '[%s] favorited at %s' %(self.user, self.added_at)

class QuestionRevision(models.Model):
    """A revision of a Question."""
    question   = models.ForeignKey(Question, related_name='revisions')
    revision   = models.PositiveIntegerField(blank=True)
    title      = models.CharField(max_length=300)
    author     = models.ForeignKey(User, related_name='question_revisions')
    revised_at = models.DateTimeField()
    tagnames   = models.CharField(max_length=125)
    summary    = models.CharField(max_length=300, blank=True)
    text       = models.TextField()

    class Meta:
        app_label = 'osqa'
        db_table = u'question_revision'
        ordering = ('-revision',)

    def get_question_title(self):
        return self.question.title

    def get_absolute_url(self):
        #print 'in QuestionRevision.get_absolute_url()'
        return reverse('question_revisions', args=[self.question.id])

    def save(self, **kwargs):
        """Looks up the next available revision number."""
        if not self.revision:
            self.revision = QuestionRevision.objects.filter(
                question=self.question).values_list('revision',
                                                    flat=True)[0] + 1
        super(QuestionRevision, self).save(**kwargs)

    def __unicode__(self):
        return u'revision %s of %s' % (self.revision, self.title)

class AnonymousQuestion(models.Model):
    title = models.CharField(max_length=300)
    session_key = models.CharField(max_length=40)  #session id for anonymous questions
    text = models.TextField()
    summary = models.CharField(max_length=180)
    tagnames = models.CharField(max_length=125)
    wiki = models.BooleanField(default=False)
    added_at = models.DateTimeField(default=datetime.datetime.now)
    ip_addr = models.IPAddressField(max_length=21) #allow high port numbers
    author = models.ForeignKey(User,null=True)

    def publish(self,user):
        from views import create_new_question
        added_at = datetime.datetime.now()
        create_new_question(title=self.title, author=user, added_at=added_at,
                                wiki=self.wiki, tagnames=self.tagnames,
                                summary=self.summary, text=self.text)
        self.delete()

    class Meta:
        app_label = 'osqa'