import logging

from django.contrib.auth import login
from django.shortcuts import redirect, render

from .forms import SignupForm
from .models import Invitation

logger = logging.getLogger(__name__)


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
            user = form.save()
            found.accept(user)
            logger.info("Invitation %s accepted by %s", found.pk, user.pk)
            # The backend has to be named: AxesStandaloneBackend is also
            # installed, and Django refuses to guess between two backends.
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            return redirect("home")
    else:
        form = SignupForm()

    return render(request, "adgang/invitation.html", {"form": form, "invitation": found})
