from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.core.urlresolvers import reverse

from osqa.models import Badge, Award

def badges(request):
    badges = Badge.objects.all().order_by('type')
    my_badges = []
    if request.user.is_authenticated():
        my_badges = Award.objects.filter(user=request.user)
        #my_badges.query.group_by = ['badge_id']

    return render_to_response('badges.html', {
        'badges' : badges,
        'mybadges' : my_badges,
        'feedback_faq_url' : reverse('feedback'),
    }, context_instance=RequestContext(request))

def badge(request, id):
    badge = get_object_or_404(Badge, id=id)
    awards = Award.objects.extra(
        select={'id': 'auth_user.id', 
                'name': 'auth_user.username',
                'rep':'auth_user.reputation',
                'gold': 'auth_user.gold',
                'silver': 'auth_user.silver',
                'bronze': 'auth_user.bronze'},
        tables=['award', 'auth_user'],
        where=['badge_id=%s AND user_id=auth_user.id'],
        params=[id]
    ).distinct('id')

    return render_to_response('badge.html', {
        'awards' : awards,
        'badge' : badge,
    }, context_instance=RequestContext(request))