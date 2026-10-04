"""allauth adapters: who is allowed to create an account, and when.

The whole access model is here. There is no allow-list of email addresses
anywhere; instead a visitor may create an account only while an unused
invitation link is held in their session, which `views.invitation` puts there
(ADR 0010).
"""
import logging

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model

from .models import SESSION_KEY, Invitation

logger = logging.getLogger(__name__)


def pending_invitation(request):
    """The usable invitation this session is holding, or None.

    Re-read and re-checked on every call rather than trusted from the session,
    so revoking or expiring a link takes effect even for someone who already
    opened it and is part-way through signing in.
    """
    token = request.session.get(SESSION_KEY)
    if not token:
        return None
    invitation = Invitation.objects.filter(token=token).first()
    if invitation is None or not invitation.is_usable:
        return None
    return invitation


def remember_invitation(request, invitation):
    request.session[SESSION_KEY] = invitation.token


def forget_invitation(request):
    request.session.pop(SESSION_KEY, None)


class NoLocalSignupAccountAdapter(DefaultAccountAdapter):
    """No passwords, so no local signup either.

    `SOCIALACCOUNT_ONLY` already hides the local login forms; this closes the
    signup path itself in case a URL is reached directly.
    """

    def is_open_for_signup(self, request):
        return False


class InvitationOnlySocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        return pending_invitation(request) is not None

    def pre_social_login(self, request, sociallogin):
        """Attach Google to an account that already has the same email.

        Without this, signing in with Google as someone who already has a
        local account -- in practice the `createsuperuser` break-glass admin,
        which is likely to use the owner's own Google address -- fails with an
        "email already in use" error and no way forward.

        Only a provider-verified address is matched. Google verifies the
        addresses it hands out, and an unverified one would let anyone claim
        an existing account by typing its address into a signup form.
        """
        if sociallogin.is_existing:
            return

        emails = [e.email for e in sociallogin.email_addresses if e.verified and e.email]
        if not emails:
            return

        user = get_user_model().objects.filter(email__iexact=emails[0]).first()
        if user is None:
            return

        logger.info("Linking Google login to existing account %s", user.pk)
        sociallogin.connect(request, user)

    def save_user(self, request, sociallogin, form=None):
        """Create the account and spend the invitation that allowed it.

        `is_open_for_signup` has already refused if there was no usable
        invitation, so re-fetching here is belt and braces -- but it is also
        where the link gets marked used, which has to happen exactly once.
        """
        user = super().save_user(request, sociallogin, form)
        invitation = pending_invitation(request)
        if invitation is not None:
            invitation.accept(user)
            logger.info("Invitation %s accepted by %s", invitation.pk, user.pk)
        forget_invitation(request)
        return user
