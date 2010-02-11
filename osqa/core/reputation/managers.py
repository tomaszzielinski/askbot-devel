import datetime
import time

from django.db import connection, models

class ReputeManager(models.Manager):
    COUNT_REPUTATION_PER_DAY_BY_USER = "SELECT SUM(positive)+SUM(negative) FROM repute WHERE user_id = %s AND (reputation_type=1 OR reputation_type=-8) AND DATE(reputed_at) = %s"
    def get_reputation_by_upvoted_today(self, user):
        """
        For one user in one day, he can only earn rep till certain score (ep. +200)
        by upvoted(also substracted from upvoted canceled). This is because we need
        to prohibit gaming system by upvoting/cancel again and again.
        """
        if user is not None:
            cursor = connection.cursor()
            cursor.execute(self.COUNT_REPUTATION_PER_DAY_BY_USER, [user.id, time.strftime("%Y-%m-%d",  datetime.datetime.now().timetuple())])
            row = cursor.fetchone()
            return row[0]

        else:
            return 0
class AwardManager(models.Manager):
    def get_recent_awards(self):
        awards = super(AwardManager, self).extra(
            select={'badge_id': 'badge.id', 'badge_name':'badge.name',
                          'badge_description': 'badge.description', 'badge_type': 'badge.type',
                          'user_id': 'auth_user.id', 'user_name': 'auth_user.username'
                          },
            tables=['award', 'badge', 'auth_user'],
            order_by=['-awarded_at'],
            where=['auth_user.id=award.user_id AND badge_id=badge.id'],
        ).values('badge_id', 'badge_name', 'badge_description', 'badge_type', 'user_id', 'user_name')
        return awards