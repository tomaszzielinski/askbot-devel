from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import ugettext as _

from osqa.core.questions.models import *
from osqa.core.answers.models import *
from osqa.core.shared.models import *

from managers import *

class Tag(models.Model):
    name       = models.CharField(max_length=255, unique=True)
    created_by = models.ForeignKey(User, related_name='created_tags')
    deleted         = models.BooleanField(default=False)
    deleted_at      = models.DateTimeField(null=True, blank=True)
    deleted_by      = models.ForeignKey(User, null=True, blank=True, related_name='deleted_tags')
    # Denormalised data
    used_count = models.PositiveIntegerField(default=0)

    objects = TagManager()

    class Meta:
        app_label = 'osqa'
        db_table = u'tag'
        ordering = ('-used_count', 'name')

    def __unicode__(self):
        return self.name

class Comment(models.Model):
    content_type   = models.ForeignKey(ContentType)
    object_id      = models.PositiveIntegerField()
    content_object = generic.GenericForeignKey('content_type', 'object_id')
    user           = models.ForeignKey(User, related_name='comments')
    comment        = models.CharField(max_length=300)
    added_at       = models.DateTimeField(default=datetime.datetime.now)

    class Meta:
        app_label = 'osqa'
        ordering = ('-added_at',)
        db_table = u'comment'

    def save(self,**kwargs):
        super(Comment,self).save(**kwargs)
        try:
            ping_google()
        except Exception:
            logging.debug('problem pinging google did you register you sitemap with google?')

    def __unicode__(self):
        return self.comment

class Vote(models.Model):
    VOTE_UP = +1
    VOTE_DOWN = -1
    VOTE_CHOICES = (
        (VOTE_UP,   u'Up'),
        (VOTE_DOWN, u'Down'),
    )

    content_type   = models.ForeignKey(ContentType)
    object_id      = models.PositiveIntegerField()
    content_object = generic.GenericForeignKey('content_type', 'object_id')
    user           = models.ForeignKey(User, related_name='votes')
    vote           = models.SmallIntegerField(choices=VOTE_CHOICES)
    voted_at       = models.DateTimeField(default=datetime.datetime.now)

    objects = VoteManager()

    class Meta:
        app_label = 'osqa'
        unique_together = ('content_type', 'object_id', 'user')
        db_table = u'vote'
    def __unicode__(self):
        return '[%s] voted at %s: %s' %(self.user, self.voted_at, self.vote)

    def is_upvote(self):
        return self.vote == self.VOTE_UP

    def is_downvote(self):
        return self.vote == self.VOTE_DOWN

class FlaggedItem(models.Model):
    """A flag on a Question or Answer indicating offensive content."""
    content_type   = models.ForeignKey(ContentType)
    object_id      = models.PositiveIntegerField()
    content_object = generic.GenericForeignKey('content_type', 'object_id')
    user           = models.ForeignKey(User, related_name='flagged_items')
    flagged_at     = models.DateTimeField(default=datetime.datetime.now)

    objects = FlaggedItemManager()

    class Meta:
        app_label = 'osqa'
        unique_together = ('content_type', 'object_id', 'user')
        db_table = u'flagged_item'
    def __unicode__(self):
        return '[%s] flagged at %s' %(self.user, self.flagged_at)

class MarkedTag(models.Model):
    TAG_MARK_REASONS = (('good',_('interesting')),('bad',_('ignored')))
    tag = models.ForeignKey(Tag, related_name='user_selections')
    user = models.ForeignKey(User, related_name='tag_selections')
    reason = models.CharField(max_length=16, choices=TAG_MARK_REASONS)

    class Meta:
        app_label = 'osqa'
