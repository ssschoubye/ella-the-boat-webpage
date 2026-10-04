import logging

from django.contrib.auth import login
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import SignupForm
from .models import Invitation

logger = logging.getLogger(__name__)


class _LinkAlreadyUsed(Exception):
    """Raised inside the signup transaction to roll the new account back."""


def _claim(invitation, user):
    """Spend the invitation, if it is still ours to spend.

    A single UPDATE with the usability test in its WHERE clause, so the check
    and the write cannot be separated. Returns True if we got it.

    This is the compare-and-swap that stops a double-click on the signup
    button creating two accounts from one link: both requests can pass the
    `is_usable` check in the view, but only one UPDATE can match. Written as a
    conditional UPDATE rather than `select_for_update`, which SQLite does not
    support.
    """
    return Invitation.objects.filter(
        pk=invitation.pk,
        accepted_at__isnull=True,
        revoked=False,
        expires_at__gt=timezone.now(),
    ).update(accepted_at=timezone.now(), accepted_by=user) == 1


def invitation(request, token):
    """The invitation link: create one account, then sign in.

    This is the only way an account comes into existence (ADR 0014). There is
    no separate signup URL to leave open by accident -- holding the token *is*
    the authorisation, so it is re-checked on the POST as well as the GET. A
    link revoked while someone sat on the form does not work.
    """
    found = Invitation.objects.filter(token=token).first()
    if found is None:
        return render(request, "adgang/invitation_invalid.html", {"reason": "ukendt"}, status=404)
    if not found.is_usable:
        return render(
            request,
            "adgang/invitation_invalid.html",
            {"reason": found.status.lower(), "invitation": found},
            status=410,
        )

    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save()
                    if not _claim(found, user):
                        raise _LinkAlreadyUsed
            except _LinkAlreadyUsed:
                # Another request spent the link first; the account we just
                # created is rolled back with the transaction.
                logger.info("Invitation %s was already spent; signup rolled back", found.pk)
                return render(
                    request,
                    "adgang/invitation_invalid.html",
                    {"reason": "brugt", "invitation": found},
                    status=410,
                )
            except IntegrityError:
                # The same address won the race a moment ago, so clean_email
                # had not seen it yet. Say so on the form rather than 500.
                logger.info("Signup collided on an address that was already taken")
                form.add_error(
                    "email",
                    "Der findes allerede en konto med den adresse. Prøv at logge ind i stedet.",
                )
            else:
                logger.info("Invitation %s accepted by %s", found.pk, user.pk)
                # The backend has to be named: AxesStandaloneBackend is also
                # installed, and Django refuses to guess between two backends.
                login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                return redirect("home")
    else:
        form = SignupForm()

    return render(request, "adgang/invitation.html", {"form": form, "invitation": found})
