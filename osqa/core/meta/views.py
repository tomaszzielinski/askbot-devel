from django.shortcuts import render_to_response, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseForbidden, Http404
from django.core.exceptions import PermissionDenied
from django.template import RequestContext
from django.utils import simplejson
from django.core.urlresolvers import reverse
from django.conf import settings

from osqa.models import *
from osqa.core.questions.views import questions, index
from osqa.core.users import auth
from osqa.core.users.auth import *
from osqa.core.users.models import mark_offensive, delete_post_or_answer

from osqa.utils.decorators import ajax_login_required, ajax_method

DEFAULT_PAGE_SIZE = 60

def tags(request):
    stag = ""
    is_paginated = True
    sortby = request.GET.get('sort', 'used')
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1

    if request.method == "GET":
        stag = request.GET.get("q", "").strip()
        if stag != '':
            objects_list = Paginator(Tag.objects.filter(deleted=False).exclude(used_count=0).extra(where=['name like %s'], params=['%' + stag + '%']), DEFAULT_PAGE_SIZE)
        else:
            if sortby == "name":
                objects_list = Paginator(Tag.objects.all().filter(deleted=False).exclude(used_count=0).order_by("name"), DEFAULT_PAGE_SIZE)
            else:
                objects_list = Paginator(Tag.objects.all().filter(deleted=False).exclude(used_count=0).order_by("-used_count"), DEFAULT_PAGE_SIZE)

    try:
        tags = objects_list.page(page)
    except (EmptyPage, InvalidPage):
        tags = objects_list.page(objects_list.num_pages)

    return render_to_response('tags.html', {
                                            "tags" : tags,
                                            "stag" : stag,
                                            "tab_id" : sortby,
                                            "keywords" : stag,
                                            "context" : {
                                                'is_paginated' : is_paginated,
                                                'pages': objects_list.num_pages,
                                                'page': page,
                                                'has_previous': tags.has_previous(),
                                                'has_next': tags.has_next(),
                                                'previous': tags.previous_page_number(),
                                                'next': tags.next_page_number(),
                                                'base_url' : reverse('tags') + '?sort=%s&' % sortby
                                            }
                                }, context_instance=RequestContext(request))

def tag(request, tag):
    return questions(request, tagname=tag)

def __comments(request, obj, type):
    # only support get comments by ajax now
    user = request.user
    if request.is_ajax():
        if request.method == "GET":
            response = __generate_comments_json(obj, type, user)
        elif request.method == "POST":
            if auth.can_add_comments(user,obj):
                comment_data = request.POST.get('comment')
                comment = Comment(content_object=obj, comment=comment_data, user=request.user)
                comment.save()
                obj.comment_count = obj.comment_count + 1
                obj.save()
                response = __generate_comments_json(obj, type, user)
            else:
                response = HttpResponseForbidden(mimetype="application/json")
        return response

def __generate_comments_json(obj, type, user):
    comments = obj.comments.all().order_by('id')
    # {"Id":6,"PostId":38589,"CreationDate":"an hour ago","Text":"hello there!","UserDisplayName":"Jarrod Dixon","UserUrl":"/users/3/jarrod-dixon","DeleteUrl":null}
    json_comments = []
    from osqa.templatetags.extra_tags import diff_date
    for comment in comments:
        comment_user = comment.user
        delete_url = ""
        if user != None and auth.can_delete_comment(user, comment):
            #/posts/392845/comments/219852/delete
            #todo translate this url
            delete_url = reverse(index) + type + "s/%s/comments/%s/delete/" % (obj.id, comment.id)
        json_comments.append({"id" : comment.id,
            "object_id" : obj.id,
            "comment_age" : diff_date(comment.added_at),
            "text" : comment.comment,
            "user_display_name" : comment_user.username,
            "user_url" : comment_user.get_profile_url(),
            "delete_url" : delete_url
        })

    data = simplejson.dumps(json_comments)
    return HttpResponse(data, mimetype="application/json")

def question_comments(request, id):
    question = get_object_or_404(Question, id=id)
    user = request.user
    return __comments(request, question, 'question')

def answer_comments(request, id):
    answer = get_object_or_404(Answer, id=id)
    user = request.user
    return __comments(request, answer, 'answer')

def delete_comment(request, object_id='', comment_id='', commented_object_type=None):
    response = None
    commented_object = None
    if commented_object_type == 'question':
        commented_object = Question
    elif commented_object_type == 'answer':
        commented_object = Answer

    if request.is_ajax():
        comment = get_object_or_404(Comment, id=comment_id)
        if auth.can_delete_comment(request.user, comment):
            obj = get_object_or_404(commented_object, id=object_id)
            obj.comments.remove(comment)
            obj.comment_count = obj.comment_count - 1
            obj.save()
            user = request.user
            return __generate_comments_json(obj, commented_object_type, user)
    raise PermissionDenied()

@ajax_login_required
def mark_tag(request, tag=None, **kwargs):
    action = kwargs['action']
    ts = MarkedTag.objects.filter(user=request.user, tag__name=tag)
    if action == 'remove':
        logging.debug('deleting tag %s' % tag)
        ts.delete()
    else:
        reason = kwargs['reason']
        if len(ts) == 0:
            try:
                t = Tag.objects.get(name=tag)
                mt = MarkedTag(user=request.user, reason=reason, tag=t)
                mt.save()
            except:
                pass
        else:
            ts.update(reason=reason)
    return HttpResponse(simplejson.dumps(''), mimetype="application/json")

@ajax_login_required
def ajax_toggle_ignored_questions(request):
    if request.user.hide_ignored_questions:
        new_hide_setting = False
    else:
        new_hide_setting = True
    request.user.hide_ignored_questions = new_hide_setting
    request.user.save()

@ajax_method
def ajax_command(request):
    if 'command' not in request.POST:
        return HttpResponseForbidden(mimetype="application/json")
    if request.POST['command'] == 'toggle-ignored-questions':
        return ajax_toggle_ignored_questions(request)

def vote(request, id):
    """
    vote_type:
        acceptAnswer : 0,
        questionUpVote : 1,
        questionDownVote : 2,
        favorite : 4,
        answerUpVote: 5,
        answerDownVote:6,
        offensiveQuestion : 7,
        offensiveAnswer:8,
        removeQuestion: 9,
        removeAnswer:10
        questionSubscribeUpdates:11

    accept answer code:
        response_data['allowed'] = -1, Accept his own answer   0, no allowed - Anonymous    1, Allowed - by default
        response_data['success'] =  0, failed                                               1, Success - by default
        response_data['status']  =  0, By default                                           1, Answer has been accepted already(Cancel)

    vote code:
        allowed = -3, Don't have enough votes left
                  -2, Don't have enough reputation score
                  -1, Vote his own post
                   0, no allowed - Anonymous
                   1, Allowed - by default
        status  =  0, By default
                   1, Cancel
                   2, Vote is too old to be canceled

    offensive code:
        allowed = -3, Don't have enough flags left
                  -2, Don't have enough reputation score to do this
                   0, not allowed
                   1, allowed
        status  =  0, by default
                   1, can't do it again
    """
    response_data = {
        "allowed": 1,
        "success": 1,
        "status" : 0,
        "count"  : 0,
        "message" : ''
    }

    def can_vote(vote_score, user):
        if vote_score == 1:
            return can_vote_up(request.user)
        else:
            return can_vote_down(request.user)

    try:
        if not request.user.is_authenticated():
            response_data['allowed'] = 0
            response_data['success'] = 0

        elif request.is_ajax():
            question = get_object_or_404(Question, id=id)
            vote_type = request.POST.get('type')

            #accept answer
            if vote_type == '0':
                answer_id = request.POST.get('postId')
                answer = get_object_or_404(Answer, id=answer_id)
                # make sure question author is current user
                if question.author == request.user:
                    # answer user who is also question author is not allow to accept answer
                    if answer.author == question.author:
                        response_data['success'] = 0
                        response_data['allowed'] = -1
                    # check if answer has been accepted already
                    elif answer.accepted:
                        onAnswerAcceptCanceled(answer, request.user)
                        response_data['status'] = 1
                    else:
                        # set other answers in this question not accepted first
                        for answer_of_question in Answer.objects.get_answers_from_question(question, request.user):
                            if answer_of_question != answer and answer_of_question.accepted:
                                onAnswerAcceptCanceled(answer_of_question, request.user)

                        #make sure retrieve data again after above author changes, they may have related data
                        answer = get_object_or_404(Answer, id=answer_id)
                        onAnswerAccept(answer, request.user)
                else:
                    response_data['allowed'] = 0
                    response_data['success'] = 0
            # favorite
            elif vote_type == '4':
                has_favorited = False
                fav_questions = FavoriteQuestion.objects.filter(question=question)
                # if the same question has been favorited before, then delete it
                if fav_questions is not None:
                    for item in fav_questions:
                        if item.user == request.user:
                            item.delete()
                            response_data['status'] = 1
                            response_data['count']  = len(fav_questions) - 1
                            if response_data['count'] < 0:
                                response_data['count'] = 0
                            has_favorited = True
                # if above deletion has not been executed, just insert a new favorite question
                if not has_favorited:
                    new_item = FavoriteQuestion(question=question, user=request.user)
                    new_item.save()
                    response_data['count']  = FavoriteQuestion.objects.filter(question=question).count()
                Question.objects.update_favorite_count(question)

            elif vote_type in ['1', '2', '5', '6']:
                post_id = id
                post = question
                vote_score = 1
                if vote_type in ['5', '6']:
                    answer_id = request.POST.get('postId')
                    answer = get_object_or_404(Answer, id=answer_id)
                    post_id = answer_id
                    post = answer
                if vote_type in ['2', '6']:
                    vote_score = -1

                if post.author == request.user:
                    response_data['allowed'] = -1
                elif not can_vote(vote_score, request.user):
                    response_data['allowed'] = -2
                elif post.votes.filter(user=request.user).count() > 0:
                    vote = post.votes.filter(user=request.user)[0]
                    # unvote should be less than certain time
                    if (datetime.datetime.now().day - vote.voted_at.day) >= VOTE_RULES['scope_deny_unvote_days']:
                        response_data['status'] = 2
                    else:
                        voted = vote.vote
                        if voted > 0:
                            # cancel upvote
                            onUpVotedCanceled(vote, post, request.user)

                        else:
                            # cancel downvote
                            onDownVotedCanceled(vote, post, request.user)

                        response_data['status'] = 1
                        response_data['count'] = post.score
                elif Vote.objects.get_votes_count_today_from_user(request.user) >= VOTE_RULES['scope_votes_per_user_per_day']:
                    response_data['allowed'] = -3
                else:
                    vote = Vote(user=request.user, content_object=post, vote=vote_score, voted_at=datetime.datetime.now())
                    if vote_score > 0:
                        # upvote
                        onUpVoted(vote, post, request.user)
                    else:
                        # downvote
                        onDownVoted(vote, post, request.user)

                    votes_left = VOTE_RULES['scope_votes_per_user_per_day'] - Vote.objects.get_votes_count_today_from_user(request.user)
                    if votes_left <= VOTE_RULES['scope_warn_votes_left']:
                        response_data['message'] = u'%s votes left' % votes_left
                    response_data['count'] = post.score
            elif vote_type in ['7', '8']:
                post = question
                post_id = id
                if vote_type == '8':
                    post_id = request.POST.get('postId')
                    post = get_object_or_404(Answer, id=post_id)

                if FlaggedItem.objects.get_flagged_items_count_today(request.user) >= VOTE_RULES['scope_flags_per_user_per_day']:
                    response_data['allowed'] = -3
                elif not can_flag_offensive(request.user):
                    response_data['allowed'] = -2
                elif post.flagged_items.filter(user=request.user).count() > 0:
                    response_data['status'] = 1
                else:
                    item = FlaggedItem(user=request.user, content_object=post, flagged_at=datetime.datetime.now())
                    onFlaggedItem(item, post, request.user)
                    response_data['count'] = post.offensive_flag_count
                    # send signal when question or answer be marked offensive
                    mark_offensive.send(sender=post.__class__, instance=post, mark_by=request.user)
            elif vote_type in ['9', '10']:
                post = question
                post_id = id
                if vote_type == '10':
                    post_id = request.POST.get('postId')
                    post = get_object_or_404(Answer, id=post_id)

                if not can_delete_post(request.user, post):
                    response_data['allowed'] = -2
                elif post.deleted == True:
                    logging.debug('debug restoring post in view')
                    onDeleteCanceled(post, request.user)
                    response_data['status'] = 1
                else:
                    onDeleted(post, request.user)
                    delete_post_or_answer.send(sender=post.__class__, instance=post, delete_by=request.user)
            elif vote_type == '11':#subscribe q updates
                user = request.user
                if user.is_authenticated():
                    if user not in question.followed_by.all():
                        question.followed_by.add(user)
                        if settings.EMAIL_VALIDATION == 'on' and user.email_isvalid == False:
                            response_data['message'] = \
                                    _('subscription saved, %(email)s needs validation, see %(details_url)s') \
                                    % {'email':user.email,'details_url':reverse('faq') + '#validate'}
                    feed_setting = EmailFeedSetting.objects.get(subscriber=user,feed_type='q_sel')
                    if feed_setting.frequency == 'n':
                        feed_setting.frequency = 'd'
                        feed_setting.save()
                        if 'message' in response_data:
                            response_data['message'] += '<br/>'
                        response_data['message'] = _('email update frequency has been set to daily')
                    #response_data['status'] = 1
                    #responst_data['allowed'] = 1
                else:
                    pass
                    #response_data['status'] = 0
                    #response_data['allowed'] = 0
            elif vote_type == '12':#unsubscribe q updates
                user = request.user
                if user.is_authenticated():
                    if user in question.followed_by.all():
                        question.followed_by.remove(user)
        else:
            response_data['success'] = 0
            response_data['message'] = u'Request mode is not supported. Please try again.'

        data = simplejson.dumps(response_data)

    except Exception, e:
        response_data['message'] = str(e)
        data = simplejson.dumps(response_data)
    return HttpResponse(data, mimetype="application/json")