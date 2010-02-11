from django import template
#from osqa.modules.auth import get_signin_icon_list

register = template.Library()

@register.inclusion_tag("auth/providers.html")
def auth_providers():
    return {
        #'icons': get_signin_icon_list()
    }