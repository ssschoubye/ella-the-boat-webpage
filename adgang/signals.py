"""Spend the invitation once an account actually exists.

`user_signed_up` fires for both signup paths -- Google and the email code --
so this is the one place that has to mark a link used, rather than each
adapter doing it slightly differently.
"""
import logging

from allauth.account.signals import user_signed_up
from django.dispatch import receiver

from .adapters import forget_invitation, pending_invitation

logger = logging.getLogger(__name__)


@receiver(user_signed_up)
def spend_invitation(request, user, **kwargs):
    invitation = pending_invitation(request)
    if invitation is not None:
        invitation.accept(user)
        logger.info("Invitation %s accepted by %s", invitation.pk, user.pk)
    else:
        # The adapters refuse signup without a usable invitation, so this
        # means one expired or was revoked between the check and here. The
        # account exists either way; say so loudly rather than silently.
        logger.warning("Account %s was created with no usable invitation", user.pk)
    forget_invitation(request)
