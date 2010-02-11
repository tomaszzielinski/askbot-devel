from models import *
from django.db import models

class QuestionManager(models.Manager):

    def update_tags(self, question, tagnames, user):
        """
        Updates Tag associations for a question to match the given
        tagname string.

        Returns ``True`` if tag usage counts were updated as a result,
        ``False`` otherwise.
        """

        current_tags = list(question.tags.all())
        current_tagnames = set(t.name for t in current_tags)
        updated_tagnames = set(t for t in tagnames.split(' ') if t)
        modified_tags = []

        removed_tags = [t for t in current_tags
                        if t.name not in updated_tagnames]
        if removed_tags:
            modified_tags.extend(removed_tags)
            question.tags.remove(*removed_tags)

        added_tagnames = updated_tagnames - current_tagnames
        if added_tagnames:
            added_tags = Tag.objects.get_or_create_multiple(added_tagnames,
                                                            user)
            modified_tags.extend(added_tags)
            question.tags.add(*added_tags)

        if modified_tags:
            Tag.objects.update_use_counts(modified_tags)
            return True

        return False

    def update_answer_count(self, question):
        """
        Executes an UPDATE query to update denormalised data with the
        number of answers the given question has.
        """

        # for some reasons, this Answer class failed to be imported,
        # although we have imported all classes from models on top.

        self.filter(id=question.id).update(
            answer_count=Answer.objects.get_answers_from_question(question).filter(deleted=False).count())

    def update_view_count(self, question):
        """
        update counter+1 when user browse question page
        """
        self.filter(id=question.id).update(view_count = question.view_count + 1)

    def update_favorite_count(self, question):
        """
        update favourite_count for given question
        """
        from models import FavoriteQuestion
        self.filter(id=question.id).update(favourite_count = FavoriteQuestion.objects.filter(question=question).count())

    def get_similar_questions(self, question):
        """
        Get 10 similar questions for given one.
        This will search the same tag list for give question(by exactly same string) first.
        Questions with the individual tags will be added to list if above questions are not full.
        """
        #print datetime.datetime.now()
        questions = list(self.filter(tagnames = question.tagnames, deleted=False).all())

        tags_list = question.tags.all()
        for tag in tags_list:
            extend_questions = self.filter(tags__id = tag.id, deleted=False)[:50]
            for item in extend_questions:
                if item not in questions and len(questions) < 10:
                    questions.append(item)

        #print datetime.datetime.now()
        return questions