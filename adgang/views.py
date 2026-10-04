from django.shortcuts import redirect, render

from .adapters import remember_invitation
from .models import Invitation


def invitation(request, token):
    """Landing page for an invitation link.

    Its only real job is to put the token in the session, so that the social
    adapter will allow a signup when the visitor comes back from Google. The
    page itself just explains what is about to happen and offers the button.
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

    remember_invitation(request, found)
    return render(request, "adgang/invitation.html", {"invitation": found})
