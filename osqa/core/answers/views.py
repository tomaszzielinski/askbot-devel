from django.utils.translation import ugettext as _
from django.contrib.auth.decorators import login_required
from django.template import RequestContext, loader
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseForbidden, Http404
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.utils.datastructures import SortedDict
from django.utils import simplejson
from django.utils.html import *

from osqa.core.shared.views import markdowner

from forms import *
from osqa.core.shared.forms import RevisionForm
from osqa.models import *
from templates import *
from osqa.core.users.auth import *
from osqa.utils.diff import textDiff as htmldiff
from osqa.utils.html import sanitize_html

def answer(request, id):
    question = get_object_or_404(Question, id=id)
    if request.method == "POST":
        form = AnswerForm(question, request.user, request.POST)
        if form.is_valid():
            wiki = form.cleaned_data['wiki']
            text = form.cleaned_data['text']
            update_time = datetime.datetime.now()

            if request.user.is_authenticated():
                create_new_answer(
                                  question=question,
                                  author=request.user,
                                  added_at=update_time,
                                  wiki=wiki,
                                  text=text,
                                  email_notify=form.cleaned_data['email_notify']
                                  )
            else:
                request.session.flush()
                html = sanitize_html(markdowner.convert(text))
                summary = strip_tags(html)[:120]
                anon = AnonymousAnswer(
                                       question=question,
                                       wiki=wiki,
                                       text=text,
                                       summary=summary,
                                       session_key=request.session.session_key,
                                       ip_addr=request.META['REMOTE_ADDR'],
                                       )
                anon.save()
                return HttpResponseRedirect(reverse('user_signin_new_answer'))

    return HttpResponseRedirect(question.get_absolute_url())

@login_required
def edit_answer(request, id):
    answer = get_object_or_404(Answer, id=id)
    if answer.deleted and not can_view_deleted_post(request.user, answer):
        raise Http404
    elif not can_edit_post(request.user, answer):
        raise Http404
    else:
        latest_revision = answer.get_latest_revision()
        if request.method == "POST":
            if 'select_revision' in request.POST:
                # user has changed revistion number
                revision_form = RevisionForm(answer, latest_revision, request.POST)
                if revision_form.is_valid():
                    # Replace with those from the selected revision
                    form = EditAnswerForm(answer,
                                          AnswerRevision.objects.get(answer=answer,
                                          revision=revision_form.cleaned_data['revision']))
                else:
                    form = EditAnswerForm(answer, latest_revision, request.POST)
            else:
                form = EditAnswerForm(answer, latest_revision, request.POST)
                if form.is_valid():
                    html = sanitize_html(markdowner.convert(form.cleaned_data['text']))
                    if form.has_changed():
                        edited_at = datetime.datetime.now()
                        updated_fields = {
                            'last_edited_at': edited_at,
                            'last_edited_by': request.user,
                            'html': html,
                        }
                        Answer.objects.filter(id=answer.id).update(**updated_fields)

                        revision = AnswerRevision(
                                                  answer=answer,
                                                  author=request.user,
                                                  revised_at=edited_at,
                                                  text=form.cleaned_data['text']
                                                  )

                        if form.cleaned_data['summary']:
                            revision.summary = form.cleaned_data['summary']
                        else:
                            revision.summary = 'No.%s Revision' % latest_revision.revision
                        revision.save()

                        answer.question.last_activity_at = edited_at
                        answer.question.last_activity_by = request.user
                        answer.question.save()

                    return HttpResponseRedirect(answer.get_absolute_url())
        else:
            revision_form = RevisionForm(answer, latest_revision)
            form = EditAnswerForm(answer, latest_revision)
        return render_to_response('answer_edit.html', {
                                  'answer': answer,
                                  'revision_form': revision_form,
                                  'form': form,
                                  }, context_instance=RequestContext(request))

def answer_revisions(request, id):
    post = get_object_or_404(Answer, id=id)
    revisions = list(post.revisions.all())
    revisions.reverse()
    for i, revision in enumerate(revisions):
        revision.html = ANSWER_REVISION_TEMPLATE % {
            'html': sanitize_html(markdowner.convert(revision.text))
        }
        if i > 0:
            revisions[i].diff = htmldiff(revisions[i-1].html, revision.html)
        else:
            revisions[i].diff = revisions[i].text
            revisions[i].summary = _('initial version')
    return render_to_response('revisions_answer.html', {
                              'post': post,
                              'revisions': revisions,
                              }, context_instance=RequestContext(request))

def create_new_answer( question=None, author=None,\
            added_at=None, wiki=False,\
            text='', email_notify=False):

    html = sanitize_html(markdowner.convert(text))

    #create answer
    answer = Answer(
        question = question,
        author = author,
        added_at = added_at,
        wiki = wiki,
        html = html
    )
    if answer.wiki:
        answer.last_edited_by = answer.author
        answer.last_edited_at = added_at
        answer.wikified_at = added_at

    answer.save()

    #update question data
    question.last_activity_at = added_at
    question.last_activity_by = author
    question.save()
    Question.objects.update_answer_count(question)

    #update revision
    AnswerRevision.objects.create(
        answer     = answer,
        revision   = 1,
        author     = author,
        revised_at = added_at,
        summary    = CONST['default_version'],
        text       = text
    )

    #set notification/delete
    if email_notify:
        if author not in question.followed_by.all():
            question.followed_by.add(author)
    else:
        #not sure if this is necessary. ajax should take care of this...
        try:
            question.followed_by.remove(author)
        except:
            pass