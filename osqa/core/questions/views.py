from urllib import quote, unquote

from django.utils.translation import ugettext as _
from django.contrib.auth.decorators import login_required
from django.template import RequestContext, loader
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseForbidden, Http404
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.utils.datastructures import SortedDict
from django.utils import simplejson
from django.utils.html import *
from django.core.urlresolvers import reverse
from django.template.defaultfilters import slugify

from osqa.core.shared.views import markdowner

from forms import *
from osqa.core.shared.forms import RevisionForm
from osqa.core.answers.forms import AnswerForm
from osqa.models import *
from osqa.modules import handlers
from templates import *
from osqa.core.users.auth import *
from osqa.utils.diff import textDiff as htmldiff
from osqa.utils.html import sanitize_html

INDEX_PAGE_SIZE = 20
INDEX_AWARD_SIZE = 15
INDEX_TAGS_SIZE = 100
QUESTIONS_PAGE_SIZE = 10
ANSWERS_PAGE_SIZE = 10

def _get_tags_cache_json():
    tags = Tag.objects.filter(deleted=False).all()
    tags_list = []
    for tag in tags:
        dic = {'n': tag.name, 'c': tag.used_count}
        tags_list.append(dic)
    tags = simplejson.dumps(tags_list)
    return tags

def _get_and_remember_questions_sort_method(request, view_dic, default):
    if default not in view_dic:
        raise Exception('default value must be in view_dic')

    q_sort_method = request.REQUEST.get('sort', None)
    if q_sort_method == None:
        q_sort_method = request.session.get('questions_sort_method', default)

    if q_sort_method not in view_dic:
        q_sort_method = default
    request.session['questions_sort_method'] = q_sort_method
    return q_sort_method, view_dic[q_sort_method]

def index(request):
    view_dic = {
             "latest":"-last_activity_at",
             "hottest":"-answer_count",
             "mostvoted":"-score",
             }
    view_id, orderby = _get_and_remember_questions_sort_method(request, view_dic, 'latest')

    page_size = request.session.get('pagesize', QUESTIONS_PAGE_SIZE)
    questions = Question.objects.exclude(deleted=True).order_by(orderby)[:page_size]
    # RISK - inner join queries
    questions = questions.select_related()
    tags = Tag.objects.get_valid_tags(INDEX_TAGS_SIZE)

    awards = Award.objects.get_recent_awards()

    (interesting_tag_names, ignored_tag_names) = (None, None)
    if request.user.is_authenticated():
        pt = MarkedTag.objects.filter(user=request.user)
        interesting_tag_names = pt.filter(reason='good').values_list('tag__name', flat=True)
        ignored_tag_names = pt.filter(reason='bad').values_list('tag__name', flat=True)

    tags_autocomplete = _get_tags_cache_json()

    return render_to_response('index.html', {
        'interesting_tag_names': interesting_tag_names,
        'tags_autocomplete': tags_autocomplete,
        'ignored_tag_names': ignored_tag_names,
        "questions" : questions,
        "tab_id" : view_id,
        "tags" : tags,
        "awards" : awards[:INDEX_AWARD_SIZE],
        }, context_instance=RequestContext(request))    

def questions(request, tagname=None, unanswered=False):
    """
    List of Questions, Tagged questions, and Unanswered questions.
    """
    # template file
    # "questions.html" or maybe index.html in the future
    template_file = "questions.html"
    # Set flag to False by default. If it is equal to True, then need to be saved.
    pagesize_changed = False
    # get pagesize from session, if failed then get default value
    pagesize = request.session.get("pagesize",10)
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1

    view_dic = {"latest":"-added_at", "active":"-last_activity_at", "hottest":"-answer_count", "mostvoted":"-score" }
    view_id, orderby = _get_and_remember_questions_sort_method(request,view_dic,'latest')

    # check if request is from tagged questions
    qs = Question.objects.exclude(deleted=True)

    if tagname is not None:
        qs = qs.filter(tags__name = unquote(tagname))

    if unanswered:
        qs = qs.exclude(answer_accepted=True)

    author_name = None
    #user contributed questions & answers
    if 'user' in request.GET:
        try:
            author_name = request.GET['user']
            u = User.objects.get(username=author_name)
            qs = qs.filter(Q(author=u) | Q(answers__author=u))
        except User.DoesNotExist:
            author_name = None

    if request.user.is_authenticated():
        uid_str = str(request.user.id)
        qs = qs.extra(
                        select = SortedDict([
                            (
                                'interesting_score',
                                'SELECT COUNT(1) FROM osqa_markedtag, question_tags '
                                  + 'WHERE osqa_markedtag.user_id = %s '
                                  + 'AND osqa_markedtag.tag_id = question_tags.tag_id '
                                  + 'AND osqa_markedtag.reason = \'good\' '
                                  + 'AND question_tags.question_id = question.id'
                            ),
                                ]),
                        select_params = (uid_str,),
                     )
        if request.user.hide_ignored_questions:
            ignored_tags = Tag.objects.filter(user_selections__reason='bad',
                                            user_selections__user = request.user)
            qs = qs.exclude(tags__in=ignored_tags)
        else:
            qs = qs.extra(
                        select = SortedDict([
                            (
                                'ignored_score',
                                'SELECT COUNT(1) FROM osqa_markedtag, question_tags '
                                  + 'WHERE osqa_markedtag.user_id = %s '
                                  + 'AND osqa_markedtag.tag_id = question_tags.tag_id '
                                  + 'AND osqa_markedtag.reason = \'bad\' '
                                  + 'AND question_tags.question_id = question.id'
                            )
                                ]),
                        select_params = (uid_str, )
                     )

    qs = qs.select_related(depth=1).order_by(orderby)

    objects_list = Paginator(qs, pagesize)
    questions = objects_list.page(page)

    # Get related tags from this page objects
    if questions.object_list.count() > 0:
        related_tags = Tag.objects.get_tags_by_questions(questions.object_list)
    else:
        related_tags = None
    tags_autocomplete = _get_tags_cache_json()

    # get the list of interesting and ignored tags
    (interesting_tag_names, ignored_tag_names) = (None, None)
    if request.user.is_authenticated():
        pt = MarkedTag.objects.filter(user=request.user)
        interesting_tag_names = pt.filter(reason='good').values_list('tag__name', flat=True)
        ignored_tag_names = pt.filter(reason='bad').values_list('tag__name', flat=True)

    return render_to_response(template_file, {
        "questions" : questions,
        "author_name" : author_name,
        "tab_id" : view_id,
        "questions_count" : objects_list.count,
        "tags" : related_tags,
        "tags_autocomplete" : tags_autocomplete,
        "searchtag" : tagname,
        "is_unanswered" : unanswered,
        "interesting_tag_names": interesting_tag_names,
        'ignored_tag_names': ignored_tag_names,
        "context" : {
            'is_paginated' : True,
            'pages': objects_list.num_pages,
            'page': page,
            'has_previous': questions.has_previous(),
            'has_next': questions.has_next(),
            'previous': questions.previous_page_number(),
            'next': questions.next_page_number(),
            'base_url' : request.path + '?sort=%s&' % view_id,
            'pagesize' : pagesize
        }}, context_instance=RequestContext(request))

#TODO: allow anynomus user to ask question by providing email and username.
#@login_required
def ask(request):
    if request.method == "POST":
        form = AskForm(request.POST)
        if form.is_valid():

            added_at = datetime.datetime.now()
            title = strip_tags(form.cleaned_data['title'].strip())
            wiki = form.cleaned_data['wiki']
            tagnames = form.cleaned_data['tags'].strip()
            text = form.cleaned_data['text']
            html = sanitize_html(markdowner.convert(text))
            summary = strip_tags(html)[:120]

            if request.user.is_authenticated():
                author = request.user

                question = create_new_question(
                    title            = title,
                    author           = author,
                    added_at         = added_at,
                    wiki             = wiki,
                    tagnames         = tagnames,
                    summary          = summary,
                    text = text
                )

                return HttpResponseRedirect(question.get_absolute_url())
            else:
                request.session.flush()
                session_key = request.session.session_key
                question = AnonymousQuestion(
                    session_key = session_key,
                    title       = title,
                    tagnames = tagnames,
                    wiki = wiki,
                    text = text,
                    summary = summary,
                    added_at = added_at,
					ip_addr = request.META['REMOTE_ADDR'],
                )
                question.save()
                return HttpResponseRedirect(reverse('user_signin_new_question'))
    else:
        form = AskForm()

    tags = _get_tags_cache_json()
    return render_to_response('ask.html', {
        'form' : form,
        'tags' : tags,
        'email_validation_faq_url':reverse('faq') + '#validate',
        }, context_instance=RequestContext(request))

def unanswered(request):
    return questions(request, unanswered=True)

@login_required
def edit_question(request, id):
    question = get_object_or_404(Question, id=id)
    if question.deleted and not can_view_deleted_post(request.user, question):
        raise Http404
    if can_edit_post(request.user, question):
        return _edit_question(request, question)
    elif can_retag_questions(request.user):
        return _retag_question(request, question)
    else:
        raise Http404

@login_required
def close(request, id):
    question = get_object_or_404(Question, id=id)
    if not can_close_question(request.user, question):
        return HttpResponse('Permission denied.')
    if request.method == 'POST':
        form = CloseForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data['reason']
            question.closed = True
            question.closed_by = request.user
            question.closed_at = datetime.datetime.now()
            question.close_reason = reason
            question.save()
        return HttpResponseRedirect(question.get_absolute_url())
    else:
        form = CloseForm()
        return render_to_response('close.html', {
            'form' : form,
            'question' : question,
            }, context_instance=RequestContext(request))

@login_required
def reopen(request, id):
    question = get_object_or_404(Question, id=id)
    # open question
    if not can_reopen_question(request.user, question):
        return HttpResponse('Permission denied.')
    if request.method == 'POST' :
        Question.objects.filter(id=question.id).update(closed=False,
            closed_by=None, closed_at=None, close_reason=None)
        return HttpResponseRedirect(question.get_absolute_url())
    else:
        return render_to_response('reopen.html', {
            'question' : question,
            }, context_instance=RequestContext(request))

def question_revisions(request, id):
    post = get_object_or_404(Question, id=id)
    revisions = list(post.revisions.all())
    revisions.reverse()
    for i, revision in enumerate(revisions):
        revision.html = QUESTION_REVISION_TEMPLATE % {
            'title': revision.title,
            'html': sanitize_html(markdowner.convert(revision.text)),
            'tags': ' '.join(['<a class="post-tag">%s</a>' % tag
                              for tag in revision.tagnames.split(' ')]),
        }
        if i > 0:
            revisions[i].diff = htmldiff(revisions[i-1].html, revision.html)
        else:
            revisions[i].diff = QUESTION_REVISION_TEMPLATE % {
                'title': revisions[0].title,
                'html': sanitize_html(markdowner.convert(revisions[0].text)),
                'tags': ' '.join(['<a class="post-tag">%s</a>' % tag
                                 for tag in revisions[0].tagnames.split(' ')]),
            }
            revisions[i].summary = _('initial version')
    return render_to_response('revisions_question.html', {
                              'post': post,
                              'revisions': revisions,
                              }, context_instance=RequestContext(request))

def _edit_question(request, question):
    latest_revision = question.get_latest_revision()
    revision_form = None
    if request.method == 'POST':
        if 'select_revision' in request.POST:
            # user has changed revistion number
            revision_form = RevisionForm(question, latest_revision, request.POST)
            if revision_form.is_valid():
                # Replace with those from the selected revision
                form = EditQuestionForm(question,
                    QuestionRevision.objects.get(question=question,
                        revision=revision_form.cleaned_data['revision']))
            else:
                form = EditQuestionForm(question, latest_revision, request.POST)
        else:
            # Always check modifications against the latest revision
            form = EditQuestionForm(question, latest_revision, request.POST)
            if form.is_valid():
                html = sanitize_html(markdowner.convert(form.cleaned_data['text']))
                if form.has_changed():
                    edited_at = datetime.datetime.now()
                    tags_changed = (latest_revision.tagnames !=
                                    form.cleaned_data['tags'])
                    tags_updated = False
                    # Update the Question itself
                    updated_fields = {
                        'title': form.cleaned_data['title'],
                        'last_edited_at': edited_at,
                        'last_edited_by': request.user,
                        'last_activity_at': edited_at,
                        'last_activity_by': request.user,
                        'tagnames': form.cleaned_data['tags'],
                        'summary': strip_tags(html)[:120],
                        'html': html,
                    }

                    # only save when it's checked
                    # because wiki doesn't allow to be edited if last version has been enabled already
                    # and we make sure this in forms.
                    if ('wiki' in form.cleaned_data and
                        form.cleaned_data['wiki']):
                        updated_fields['wiki'] = True
                        updated_fields['wikified_at'] = edited_at

                    Question.objects.filter(
                        id=question.id).update(**updated_fields)
                    # Update the Question's tag associations
                    if tags_changed:
                        tags_updated = Question.objects.update_tags(
                            question, form.cleaned_data['tags'], request.user)
                    # Create a new revision
                    revision = QuestionRevision(
                        question   = question,
                        title      = form.cleaned_data['title'],
                        author     = request.user,
                        revised_at = edited_at,
                        tagnames   = form.cleaned_data['tags'],
                        text       = form.cleaned_data['text'],
                    )
                    if form.cleaned_data['summary']:
                        revision.summary = form.cleaned_data['summary']
                    else:
                        revision.summary = 'No.%s Revision' % latest_revision.revision
                    revision.save()

                return HttpResponseRedirect(question.get_absolute_url())
    else:

        revision_form = RevisionForm(question, latest_revision)
        form = EditQuestionForm(question, latest_revision)
    return render_to_response('question_edit.html', {
        'question': question,
        'revision_form': revision_form,
        'form' : form,
        'tags' : _get_tags_cache_json()
    }, context_instance=RequestContext(request))

def _retag_question(request, question):
    if request.method == 'POST':
        form = RetagQuestionForm(question, request.POST)
        if form.is_valid():
            if form.has_changed():
                latest_revision = question.get_latest_revision()
                retagged_at = datetime.datetime.now()
                # Update the Question itself
                Question.objects.filter(id=question.id).update(
                    tagnames         = form.cleaned_data['tags'],
                    last_edited_at   = retagged_at,
                    last_edited_by   = request.user,
                    last_activity_at = retagged_at,
                    last_activity_by = request.user
                )
                # Update the Question's tag associations
                tags_updated = Question.objects.update_tags(question,
                    form.cleaned_data['tags'], request.user)
                # Create a new revision
                QuestionRevision.objects.create(
                    question   = question,
                    title      = latest_revision.title,
                    author     = request.user,
                    revised_at = retagged_at,
                    tagnames   = form.cleaned_data['tags'],
                    summary    = CONST['retagged'],
                    text       = latest_revision.text
                )
                # send tags updated singal
                tags_updated.send(sender=question.__class__, question=question)

            return HttpResponseRedirect(question.get_absolute_url())
    else:
        form = RetagQuestionForm(question)
    return render_to_response('question_retag.html', {
        'question': question,
        'form' : form,
        'tags' : _get_tags_cache_json(),
    }, context_instance=RequestContext(request))

def create_new_question(title=None,author=None,added_at=None,
                        wiki=False,tagnames=None,summary=None,
                        text=None):
    """this is not a view
    and maybe should become one of the methods on Question object?
    """
    html = sanitize_html(markdowner.convert(text))
    question = Question(
        title            = title,
        author           = author,
        added_at         = added_at,
        last_activity_at = added_at,
        last_activity_by = author,
        wiki             = wiki,
        tagnames         = tagnames,
        html             = html,
        summary          = summary
    )
    if question.wiki:
        question.last_edited_by = question.author
        question.last_edited_at = added_at
        question.wikified_at = added_at

    question.save()

    # create the first revision
    QuestionRevision.objects.create(
        question   = question,
        revision   = 1,
        title      = question.title,
        author     = author,
        revised_at = added_at,
        tagnames   = question.tagnames,
        summary    = CONST['default_version'],
        text       = text
    )
    return question

def question_search(keywords):
    objects = Question.objects.filter(deleted=False).extra(where=['title like %s'], params=['%' + keywords + '%']).order_by(orderby)
    return objects.select_related();

question_search = handlers.get_handler('question_search', question_search)


def search(request):
    """
    Search by question, user and tag keywords.
    For questions now we only search keywords in question title.
    """
    if request.method == "GET":
        keywords = request.GET.get("q")
        search_type = request.GET.get("t")
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1
        if keywords is None:
            return HttpResponseRedirect(reverse(index))
        if search_type == 'tag':
            return HttpResponseRedirect(reverse('tags') + '?q=%s&page=%s' % (keywords.strip(), page))
        elif search_type == "user":
            return HttpResponseRedirect(reverse('users') + '?q=%s&page=%s' % (keywords.strip(), page))
        elif search_type == "question":

            template_file = "questions.html"
            # Set flag to False by default. If it is equal to True, then need to be saved.
            pagesize_changed = False
            # get pagesize from session, if failed then get default value
            user_page_size = request.session.get("pagesize", QUESTIONS_PAGE_SIZE)
            # set pagesize equal to logon user specified value in database
            if request.user.is_authenticated() and request.user.questions_per_page > 0:
                user_page_size = request.user.questions_per_page

            try:
                page = int(request.GET.get('page', '1'))
                # get new pagesize from UI selection
                pagesize = int(request.GET.get('pagesize', user_page_size))
                if pagesize <> user_page_size:
                    pagesize_changed = True

            except ValueError:
                page = 1
                pagesize  = user_page_size

            # save this pagesize to user database
            if pagesize_changed:
                request.session["pagesize"] = pagesize
                if request.user.is_authenticated():
                    user = request.user
                    user.questions_per_page = pagesize
                    user.save()

            view_id = request.GET.get('sort', None)
            view_dic = {"latest":"-added_at", "active":"-last_activity_at", "hottest":"-answer_count", "mostvoted":"-score" }
            try:
                orderby = view_dic[view_id]
            except KeyError:
                view_id = "latest"
                orderby = "-added_at"

            objects = question_search(keywords)

            objects_list = Paginator(objects, pagesize)
            questions = objects_list.page(page)

            # Get related tags from this page objects
            related_tags = []
            for question in questions.object_list:
                tags = list(question.tags.all())
                for tag in tags:
                    if tag not in related_tags:
                        related_tags.append(tag)

            #if is_search is true in the context, prepend this string to soting tabs urls
            search_uri = "?q=%s&page=%d&t=question" % ("+".join(keywords.split()),  page)

            return render_to_response(template_file, {
                "questions" : questions,
                "tab_id" : view_id,
                "questions_count" : objects_list.count,
                "tags" : related_tags,
                "searchtag" : None,
                "searchtitle" : keywords,
                "keywords" : keywords,
                "is_unanswered" : False,
                "is_search": True,
                "search_uri":  search_uri,
                "context" : {
                    'is_paginated' : True,
                    'pages': objects_list.num_pages,
                    'page': page,
                    'has_previous': questions.has_previous(),
                    'has_next': questions.has_next(),
                    'previous': questions.previous_page_number(),
                    'next': questions.next_page_number(),
                    'base_url' : request.path + '?t=question&q=%s&sort=%s&' % (keywords, view_id),
                    'pagesize' : pagesize
                }}, context_instance=RequestContext(request))

    else:
        raise Http404
        
def question(request, id):
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1

    view_id = request.GET.get('sort', None)
    view_dic = {"latest":"-added_at", "oldest":"added_at", "votes":"-score" }
    try:
        orderby = view_dic[view_id]
    except KeyError:
        qsm = request.session.get('questions_sort_method',None)
        if qsm in ('mostvoted','latest'):
            logging.debug('loaded from session ' + qsm)
            if qsm == 'mostvoted':
                view_id = 'votes'
                orderby = '-score'
            else:
                view_id = 'latest'
                orderby = '-added_at'
        else:
            view_id = "votes"
            orderby = "-score"

    logging.debug('view_id=' + str(view_id))

    question = get_object_or_404(Question, id=id)
    try:
        pattern = r'/%s%s%d/([\w-]+)' % (settings.FORUM_SCRIPT_ALIAS,_('question/'), question.id)
        path_re = re.compile(pattern)
        logging.debug(pattern)
        logging.debug(request.path)
        m = path_re.match(request.path)
        if m:
            slug = m.group(1)
            logging.debug('have slug %s' % slug)
            assert(slug == slugify(question.title))
        else:
            logging.debug('no match!')
    except:
        return HttpResponseRedirect(question.get_absolute_url())

    if question.deleted and not can_view_deleted_post(request.user, question):
        raise Http404
    answer_form = AnswerForm(question,request.user)
    answers = Answer.objects.get_answers_from_question(question, request.user)
    answers = answers.select_related(depth=1)

    favorited = question.has_favorite_by_user(request.user)
    if request.user.is_authenticated():
        question_vote = question.votes.select_related().filter(user=request.user)
    else:
        question_vote = None #is this correct?
    if question_vote is not None and question_vote.count() > 0:
        question_vote = question_vote[0]

    user_answer_votes = {}
    for answer in answers:
        vote = answer.get_user_vote(request.user)
        if vote is not None and not user_answer_votes.has_key(answer.id):
            vote_value = -1
            if vote.is_upvote():
                vote_value = 1
            user_answer_votes[answer.id] = vote_value

    if answers is not None:
        answers = answers.order_by("-accepted", orderby)

    filtered_answers = []
    for answer in answers:
        if answer.deleted == True:
            if answer.author_id == request.user.id:
                filtered_answers.append(answer)
        else:
            filtered_answers.append(answer)

    objects_list = Paginator(filtered_answers, ANSWERS_PAGE_SIZE)
    page_objects = objects_list.page(page)

    #todo: merge view counts per user and per session
    #1) view count per session
    update_view_count = False
    if 'question_view_times' not in request.session:
        request.session['question_view_times'] = {}

    last_seen = request.session['question_view_times'].get(question.id,None)
    updated_when, updated_who = question.get_last_update_info()

    if updated_who != request.user:
        if last_seen:
            if last_seen < updated_when:
                update_view_count = True
        else:
            update_view_count = True

    request.session['question_view_times'][question.id] = datetime.datetime.now()

    if update_view_count:
        question.view_count += 1
        question.save()

    #2) question view count per user
    if request.user.is_authenticated():
        try:
            question_view = QuestionView.objects.get(who=request.user, question=question)
        except QuestionView.DoesNotExist:
            question_view = QuestionView(who=request.user, question=question)
        question_view.when = datetime.datetime.now()
        question_view.save()

    return render_to_response('question.html', {
        "question" : question,
        "question_vote" : question_vote,
        "question_comment_count":question.comments.count(),
        "answer" : answer_form,
        "answers" : page_objects.object_list,
        "user_answer_votes": user_answer_votes,
        "tags" : question.tags.all(),
        "tab_id" : view_id,
        "favorited" : favorited,
        "similar_questions" : Question.objects.get_similar_questions(question),
        "context" : {
            'is_paginated' : True,
            'pages': objects_list.num_pages,
            'page': page,
            'has_previous': page_objects.has_previous(),
            'has_next': page_objects.has_next(),
            'previous': page_objects.previous_page_number(),
            'next': page_objects.next_page_number(),
            'base_url' : request.path + '?sort=%s&' % view_id,
            'extend_url' : "#sort-top"
        }
        }, context_instance=RequestContext(request))