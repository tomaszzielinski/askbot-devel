from django.db import connection, models, transaction
from django.db.models import Q

class AnswerManager(models.Manager):
    GET_ANSWERS_FROM_USER_QUESTIONS = u'SELECT answer.* FROM answer INNER JOIN question ON answer.question_id = question.id WHERE question.author_id =%s AND answer.author_id <> %s'
    def get_answers_from_question(self, question, user=None):
        """
        Retrieves visibile answers for the given question. Delete answers
        are only visibile to the person who deleted them.
        """

        if user is None or not user.is_authenticated():
            return self.filter(question=question, deleted=False)
        else:
            return self.filter(Q(question=question),
                               Q(deleted=False) | Q(deleted_by=user))

    def get_answers_from_questions(self, user_id):
        """
        Retrieves visibile answers for the given question. Which are not included own answers
        """
        cursor = connection.cursor()
        cursor.execute(self.GET_ANSWERS_FROM_USER_QUESTIONS, [user_id, user_id])
        return cursor.fetchall()