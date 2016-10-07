from __future__ import absolute_import, unicode_literals

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.urlresolvers import reverse

from wagtail.utils.compat import user_is_authenticated
from wagtail.wagtailcore import hooks
from wagtail.wagtailcore.models import PageViewRestriction


def require_wagtail_login(next):
    login_url = getattr(settings, 'WAGTAIL_FRONTEND_LOGIN_URL', reverse('wagtailcore_login'))
    return redirect_to_login(next, login_url)


@hooks.register('before_serve_page')
def check_view_restrictions(page, request, serve_args, serve_kwargs):
    """
    Check whether there are any view restrictions on this page which are
    not fulfilled by the given request object. If there are, return an
    HttpResponse that will notify the user of that restriction (and possibly
    include a password / login form that will allow them to proceed). If
    there are no such restrictions, return None
    """
    restrictions = page.get_view_restrictions()

    if restrictions:
        passed_restrictions = request.session.get('passed_page_view_restrictions', [])
        for restriction in restrictions:
            if restriction.restriction_type == PageViewRestriction.PASSWORD:
                if restriction.id not in passed_restrictions:
                    from wagtail.wagtailcore.forms import PasswordPageViewRestrictionForm
                    form = PasswordPageViewRestrictionForm(instance=restriction,
                                                           initial={'return_url': request.get_full_path()})
                    action_url = reverse('wagtailcore_authenticate_with_password', args=[restriction.id, page.id])
                    return page.serve_password_required_response(request, form, action_url)
            elif restriction.restriction_type == PageViewRestriction.LOGIN:
                if not user_is_authenticated(request.user):
                    return require_wagtail_login(next=request.get_full_path())
            elif restriction.restriction_type == PageViewRestriction.GROUPS:
                if not request.user.is_superuser:
                    current_user_groups = request.user.groups.all()

                    if not any(group in current_user_groups for group in restriction.groups.all()):
                        return require_wagtail_login(next=request.get_full_path())
