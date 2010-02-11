from osqa.core.questions import models as question_models
from osqa.core.answers import models as answer_models
from osqa.core.meta import models as meta_models
from osqa.core.reputation import models as reputation_models
from osqa.core.users import models as user_models

Question = question_models.Question
QuestionRevision = question_models.QuestionRevision
QuestionView = question_models.QuestionView
FavoriteQuestion = question_models.FavoriteQuestion
AnonymousQuestion = question_models.AnonymousQuestion

Answer = answer_models.Answer
AnswerRevision = answer_models.AnswerRevision
AnonymousAnswer = answer_models.AnonymousAnswer

Tag = meta_models.Tag
Comment = meta_models.Comment
Vote = meta_models.Vote
FlaggedItem = meta_models.FlaggedItem
MarkedTag = meta_models.MarkedTag

Badge = reputation_models.Badge
Award = reputation_models.Award
Repute = reputation_models.Repute

Activity = user_models.Activity
EmailFeedSetting = user_models.EmailFeedSetting
AnonymousEmail = user_models.AnonymousEmail

__all__ = [
        'Question',
        'QuestionRevision',
        'QuestionView',
        'FavoriteQuestion',
        'AnonymousQuestion',

        'Answer',
        'AnswerRevision',
        'AnonymousAnswer',

        'Tag',
        'Comment',
        'Vote',
        'FlaggedItem',
        'MarkedTag',

        'Badge',
        'Award',
        'Repute',

        'Activity',
        'EmailFeedSetting',
        'AnonymousEmail',
        ]

from modules.utils import get_module_models

for k, v in get_module_models().items():
    __all__.append(k)
    exec "%s = v" % k