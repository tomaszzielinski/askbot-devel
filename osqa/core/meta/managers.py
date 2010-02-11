import datetime
import time

from django.db import connection, models, transaction
from django.db.models import Q

#from models import *

class TagManager(models.Manager):
    UPDATE_USED_COUNTS_QUERY = (
        'UPDATE tag '
        'SET used_count = ('
            'SELECT COUNT(*) FROM question_tags '
            'INNER JOIN question ON question_id=question.id '
            'WHERE tag_id = tag.id AND question.deleted=False'
        ') '
        'WHERE id IN (%s)')

    def get_valid_tags(self, page_size):
      tags = self.all().filter(deleted=False).exclude(used_count=0).order_by("-id")[:page_size]
      return tags

    def get_or_create_multiple(self, names, user):
        """
        Fetches a list of Tags with the given names, creating any Tags
        which don't exist when necesssary.
        """
        tags = list(self.filter(name__in=names))
        #Set all these tag visible
        for tag in tags:
            if tag.deleted:
                tag.deleted = False
                tag.deleted_by = None
                tag.deleted_at = None
                tag.save()

        if len(tags) < len(names):
            existing_names = set(tag.name for tag in tags)
            new_names = [name for name in names if name not in existing_names]
            tags.extend([self.create(name=name, created_by=user)
                         for name in new_names if self.filter(name=name).count() == 0 and len(name.strip()) > 0])

        return tags

    def update_use_counts(self, tags):
        """Updates the given Tags with their current use counts."""
        if not tags:
            return
        cursor = connection.cursor()
        query = self.UPDATE_USED_COUNTS_QUERY % ','.join(['%s'] * len(tags))
        cursor.execute(query, [tag.id for tag in tags])
        transaction.commit_unless_managed()

    def get_tags_by_questions(self, questions):
        question_ids = []
        for question in questions:
            question_ids.append(question.id)

        question_ids_str = ','.join([str(id) for id in question_ids])
        related_tags = self.extra(
                tables=['tag', 'question_tags'],
                where=["tag.id = question_tags.tag_id AND question_tags.question_id IN (" + question_ids_str + ")"]
        ).distinct()

        return related_tags

class VoteManager(models.Manager):
    COUNT_UP_VOTE_BY_USER = "SELECT count(*) FROM vote WHERE user_id = %s AND vote = 1"
    COUNT_DOWN_VOTE_BY_USER = "SELECT count(*) FROM vote WHERE user_id = %s AND vote = -1"
    COUNT_VOTES_PER_DAY_BY_USER = "SELECT COUNT(*) FROM vote WHERE user_id = %s AND DATE(voted_at) = %s"
    def get_up_vote_count_from_user(self, user):
        if user is not None:
            cursor = connection.cursor()
            cursor.execute(self.COUNT_UP_VOTE_BY_USER, [user.id])
            row = cursor.fetchone()
            return row[0]
        else:
            return 0

    def get_down_vote_count_from_user(self, user):
        if user is not None:
            cursor = connection.cursor()
            cursor.execute(self.COUNT_DOWN_VOTE_BY_USER, [user.id])
            row = cursor.fetchone()
            return row[0]
        else:
            return 0

    def get_votes_count_today_from_user(self, user):
        if user is not None:
            cursor = connection.cursor()
            cursor.execute(self.COUNT_VOTES_PER_DAY_BY_USER, [user.id,  time.strftime("%Y-%m-%d",  datetime.datetime.now().timetuple())])
            row = cursor.fetchone()
            return row[0]

        else:
            return 0

class FlaggedItemManager(models.Manager):
    COUNT_FLAGS_PER_DAY_BY_USER = "SELECT COUNT(*) FROM flagged_item WHERE user_id = %s AND DATE(flagged_at) = %s"
    def get_flagged_items_count_today(self, user):
        if user is not None:
            cursor = connection.cursor()
            cursor.execute(self.COUNT_FLAGS_PER_DAY_BY_USER, [user.id, time.strftime("%Y-%m-%d",  datetime.datetime.now().timetuple())])
            row = cursor.fetchone()
            return row[0]

        else:
            return 0