from django import forms
from django.utils.translation import ugettext as _

from models import *
from osqa.core.shared.forms import *

class EditUserEmailFeedsForm(forms.Form):
    WN = (('w',_('weekly')),('n',_('no email')))
    DWN = (('d',_('daily')),('w',_('weekly')),('n',_('no email')))
    FORM_TO_MODEL_MAP = {
                'all_questions':'q_all',
                'asked_by_me':'q_ask',
                'answered_by_me':'q_ans',
                'individually_selected':'q_sel',
                }
    NO_EMAIL_INITIAL = {
                'all_questions':'n',
                'asked_by_me':'n',
                'answered_by_me':'n',
                'individually_selected':'n',
                }
    asked_by_me = forms.ChoiceField(choices=DWN,initial='w',
                            widget=forms.RadioSelect,
                            label=_('Asked by me'))
    answered_by_me = forms.ChoiceField(choices=DWN,initial='w',
                            widget=forms.RadioSelect,
                            label=_('Answered by me'))
    individually_selected = forms.ChoiceField(choices=DWN,initial='w',
                            widget=forms.RadioSelect,
                            label=_('Individually selected'))
    all_questions = forms.ChoiceField(choices=DWN,initial='w',
                            widget=forms.RadioSelect,
                            label=_('Entire forum (tag filtered)'),)

    def set_initial_values(self,user=None):
        KEY_MAP = dict([(v,k) for k,v in self.FORM_TO_MODEL_MAP.iteritems()])
        if user != None:
            settings = EmailFeedSetting.objects.filter(subscriber=user)
            initial_values = {}
            for setting in settings:
                feed_type = setting.feed_type
                form_field = KEY_MAP[feed_type]
                frequency = setting.frequency
                initial_values[form_field] = frequency
            self.initial = initial_values
        return self

    def reset(self):
        self.cleaned_data['all_questions'] = 'n'
        self.cleaned_data['asked_by_me'] = 'n'
        self.cleaned_data['answered_by_me'] = 'n'
        self.cleaned_data['individually_selected'] = 'n'
        self.initial = self.NO_EMAIL_INITIAL
        return self

    def save(self,user,save_unbound=False):
        """
            with save_unbound==True will bypass form validation and save initial values
        """
        changed = False
        for form_field, feed_type in self.FORM_TO_MODEL_MAP.items():
            s, created = EmailFeedSetting.objects.get_or_create(subscriber=user,\
                                                    feed_type=feed_type)
            if save_unbound:
                #just save initial values instead
                if form_field in self.initial:
                    new_value = self.initial[form_field]
                else:
                    new_value = self.fields[form_field].initial
            else:
                new_value = self.cleaned_data[form_field]
            if s.frequency != new_value:
                s.frequency = new_value
                s.save()
                changed = True
            else:
                if created:
                    s.save()
            if form_field == 'individually_selected':
                feed_type = ContentType.objects.get_for_model(Question)
                user.followed_questions.clear()
        return changed

class SimpleEmailSubscribeForm(forms.Form):
    SIMPLE_SUBSCRIBE_CHOICES = (
        ('y',_('okay, let\'s try!')),
        ('n',_('no OSQA community email please, thanks'))
    )
    subscribe = forms.ChoiceField(widget=forms.widgets.RadioSelect(), \
                                error_messages={'required':_('please choose one of the options above')},
                                choices=SIMPLE_SUBSCRIBE_CHOICES)

    def save(self,user=None):
        EFF = EditUserEmailFeedsForm
        if self.cleaned_data['subscribe'] == 'y':
            email_settings_form = EFF()
            #logging.debug('%s wants to subscribe' % user.username)
        else:
            email_settings_form = EFF(initial=EFF.NO_EMAIL_INITIAL)
        email_settings_form.save(user,save_unbound=True)

class FeedbackForm(forms.Form):
    name = forms.CharField(label=_('Your name:'), required=False)
    email = forms.EmailField(label=_('Email (not shared with anyone):'), required=False)
    message = forms.CharField(label=_('Your message:'), max_length=800,widget=forms.Textarea(attrs={'cols':60}))
    next = NextUrlField()

class EditUserForm(forms.Form):
    email = forms.EmailField(label=u'Email', help_text=_('this email does not have to be linked to gravatar'), required=True, max_length=255, widget=forms.TextInput(attrs={'size' : 35}))
    if settings.EDITABLE_SCREEN_NAME:
    	username = UserNameField(label=_('Screen name'))
    realname = forms.CharField(label=_('Real name'), required=False, max_length=255, widget=forms.TextInput(attrs={'size' : 35}))
    website = forms.URLField(label=_('Website'), required=False, max_length=255, widget=forms.TextInput(attrs={'size' : 35}))
    city = forms.CharField(label=_('Location'), required=False, max_length=255, widget=forms.TextInput(attrs={'size' : 35}))
    birthday = forms.DateField(label=_('Date of birth'), help_text=_('will not be shown, used to calculate age, format: YYYY-MM-DD'), required=False, widget=forms.TextInput(attrs={'size' : 35}))
    about = forms.CharField(label=_('Profile'), required=False, widget=forms.Textarea(attrs={'cols' : 60}))

    def __init__(self, user, *args, **kwargs):
        super(EditUserForm, self).__init__(*args, **kwargs)
        logging.debug('initializing the form')
        if settings.EDITABLE_SCREEN_NAME:
            self.fields['username'].initial = user.username
            self.fields['username'].user_instance = user
        self.fields['email'].initial = user.email
        self.fields['realname'].initial = user.real_name
        self.fields['website'].initial = user.website
        self.fields['city'].initial = user.location

        if user.date_of_birth is not None:
            self.fields['birthday'].initial = user.date_of_birth
        else:
            self.fields['birthday'].initial = '1990-01-01'
        self.fields['about'].initial = user.about
        self.user = user

    def clean_email(self):
        """For security reason one unique email in database"""
        if self.user.email != self.cleaned_data['email']:
            #todo dry it, there is a similar thing in openidauth
            if settings.EMAIL_UNIQUE == True:
                if 'email' in self.cleaned_data:
                    try:
                        user = User.objects.get(email = self.cleaned_data['email'])
                    except User.DoesNotExist:
                        return self.cleaned_data['email']
                    except User.MultipleObjectsReturned:
                        raise forms.ValidationError(_('this email has already been registered, please use another one'))
                    raise forms.ValidationError(_('this email has already been registered, please use another one'))
        return self.cleaned_data['email']

class TagFilterSelectionForm(forms.ModelForm):
    tag_filter_setting = forms.ChoiceField(choices=TAG_EMAIL_FILTER_CHOICES, #imported from forum/const.py
                                            initial='ignored',
                                            label=_('Choose email tag filter'),
                                            widget=forms.RadioSelect)
    class Meta:
        model = User
        fields = ('tag_filter_setting',)

    def save(self):
        before = self.instance.tag_filter_setting
        super(TagFilterSelectionForm, self).save()
        after = self.instance.tag_filter_setting #User.objects.get(pk=self.instance.id).tag_filter_setting
        if before != after:
            return True
        return False

class ModerateUserForm(forms.ModelForm):
    is_approved = forms.BooleanField(label=_("Automatically accept user's contributions for the email updates"),
                                     required=False)

    def clean_is_approved(self):
        if 'is_approved' not in self.cleaned_data:
            self.cleaned_data['is_approved'] = False
        return self.cleaned_data['is_approved']

    class Meta:
        model = User
        fields = ('is_approved',)

class NotARobotForm(forms.Form):
    recaptcha = ReCaptchaField()
    