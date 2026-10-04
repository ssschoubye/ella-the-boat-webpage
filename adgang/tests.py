import re
from datetime import timedelta
from io import StringIO

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialLogin
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .adapters import (
    InvitationOnlyAccountAdapter,
    InvitationOnlySocialAccountAdapter,
    pending_invitation,
    remember_invitation,
)
from .models import SESSION_KEY, Invitation
from .signals import spend_invitation

User = get_user_model()


def google_login(email="anton@example.com", first_name="Anton", verified=True, uid="g-1"):
    """A SocialLogin as allauth would hand one to the adapter after Google."""
    return SocialLogin(
        user=User(email=email, first_name=first_name),
        account=SocialAccount(provider="google", uid=uid, extra_data={"email": email}),
        email_addresses=[EmailAddress(email=email, verified=verified, primary=True)],
    )


def extract_code(body):
    """Pull the code out of a sent mail.

    allauth's default generator produces an uppercase alphanumeric code with a
    dash in it (e.g. TSPC-CKMW), on a line of its own -- not six digits, which
    is what one assumes and then writes a regex for.
    """
    match = re.search(r"^([A-Z0-9][A-Z0-9-]{5,})$", body, re.MULTILINE)
    assert match, "no code found in mail body: " + body
    return match.group(1)


def request_with_session():
    request = RequestFactory().get("/")
    request.session = SessionStore()
    request.session.create()
    return request


class InvitationModelTests(TestCase):
    def test_a_fresh_invitation_is_usable(self):
        self.assertTrue(Invitation.objects.create(label="Anton").is_usable)

    def test_tokens_are_unguessable_and_distinct(self):
        tokens = {Invitation.objects.create(label=f"nr {i}").token for i in range(5)}
        self.assertEqual(len(tokens), 5)
        self.assertGreaterEqual(min(len(t) for t in tokens), 32)

    def test_expired_revoked_and_used_are_not_usable(self):
        expired = Invitation.objects.create(
            label="Gammel", expires_at=timezone.now() - timedelta(days=1)
        )
        revoked = Invitation.objects.create(label="Fortrudt", revoked=True)
        used = Invitation.objects.create(label="Brugt")
        used.accept(User.objects.create_user("someone"))

        self.assertFalse(expired.is_usable)
        self.assertFalse(revoked.is_usable)
        self.assertFalse(used.is_usable)
        self.assertEqual(
            [expired.status, revoked.status, used.status],
            ["Udløbet", "Tilbagekaldt", "Brugt"],
        )

    def test_url_is_absolute_so_it_can_be_pasted_into_a_message(self):
        invitation = Invitation.objects.create(label="Anton")
        self.assertTrue(invitation.url.startswith("https://"))
        self.assertIn(invitation.token, invitation.url)


class InvitationViewTests(TestCase):
    def test_opening_a_link_parks_the_token_in_the_session(self):
        invitation = Invitation.objects.create(label="Anton")

        response = self.client.get(invitation.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session[SESSION_KEY], invitation.token)

    def test_unknown_token_is_a_404(self):
        self.assertEqual(self.client.get("/invitation/not-a-real-token/").status_code, 404)

    def test_used_link_is_gone_and_does_not_grant_a_session(self):
        invitation = Invitation.objects.create(label="Anton")
        invitation.accept(User.objects.create_user("anton"))

        response = self.client.get(invitation.get_absolute_url())

        self.assertEqual(response.status_code, 410)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_expired_link_is_gone(self):
        invitation = Invitation.objects.create(
            label="Anton", expires_at=timezone.now() - timedelta(seconds=1)
        )
        self.assertEqual(self.client.get(invitation.get_absolute_url()).status_code, 410)

    def test_an_invitation_page_is_reachable_without_logging_in(self):
        """The whole point: it is the one way in for someone with no account."""
        invitation = Invitation.objects.create(label="Anton")
        self.assertEqual(self.client.get(invitation.get_absolute_url()).status_code, 200)


class PendingInvitationTests(TestCase):
    def test_nothing_in_the_session_means_no_invitation(self):
        self.assertIsNone(pending_invitation(request_with_session()))

    def test_revoking_takes_effect_for_a_session_already_holding_the_link(self):
        """Someone who opened the link and walked away must not still get in."""
        invitation = Invitation.objects.create(label="Anton")
        request = request_with_session()
        remember_invitation(request, invitation)
        self.assertIsNotNone(pending_invitation(request))

        Invitation.objects.filter(pk=invitation.pk).update(revoked=True)

        self.assertIsNone(pending_invitation(request))


class SignupGateTests(TestCase):
    """Both adapters have to refuse, or the gate has a hole in it."""

    def setUp(self):
        self.social = InvitationOnlySocialAccountAdapter()
        self.local = InvitationOnlyAccountAdapter()

    def test_signup_is_closed_on_both_paths_without_an_invitation(self):
        request = request_with_session()
        self.assertFalse(self.social.is_open_for_signup(request, google_login()))
        self.assertFalse(self.local.is_open_for_signup(request))

    def test_signup_is_open_on_both_paths_while_holding_an_invitation(self):
        request = request_with_session()
        remember_invitation(request, Invitation.objects.create(label="Anton"))
        self.assertTrue(self.social.is_open_for_signup(request, google_login()))
        self.assertTrue(self.local.is_open_for_signup(request))

    def test_signup_is_closed_once_the_invitation_is_spent(self):
        invitation = Invitation.objects.create(label="Anton")
        request = request_with_session()
        remember_invitation(request, invitation)
        invitation.accept(User.objects.create_user("earlier"))

        self.assertFalse(self.social.is_open_for_signup(request, google_login()))
        self.assertFalse(self.local.is_open_for_signup(request))

    def test_the_account_keeps_the_name_and_email_from_google(self):
        request = request_with_session()
        remember_invitation(request, Invitation.objects.create(label="Anton"))

        user = self.social.save_user(
            request, google_login(email="a@example.com", first_name="Anton")
        )

        self.assertEqual(user.first_name, "Anton")
        self.assertEqual(user.email, "a@example.com")


class SpendInvitationSignalTests(TestCase):
    """The signal is what marks a link used, on either signup path."""

    def test_it_spends_the_invitation_and_clears_the_session(self):
        invitation = Invitation.objects.create(label="Anton")
        request = request_with_session()
        remember_invitation(request, invitation)
        user = User.objects.create_user("anton")

        spend_invitation(request=request, user=user)

        invitation.refresh_from_db()
        self.assertEqual(invitation.accepted_by, user)
        self.assertIsNotNone(invitation.accepted_at)
        self.assertFalse(invitation.is_usable)
        self.assertNotIn(SESSION_KEY, request.session)

    def test_it_tolerates_an_invitation_that_vanished_mid_flow(self):
        """The adapters already refused without one; this is belt and braces
        for a link revoked between the check and the account being created."""
        request = request_with_session()
        user = User.objects.create_user("anton")

        spend_invitation(request=request, user=user)  # must not raise

        self.assertNotIn(SESSION_KEY, request.session)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EmailCodeSignupTests(TestCase):
    """End to end: an invited person with no Google account (ADR 0013)."""

    def setUp(self):
        # allauth throttles code emails through the cache ("1/10s/key" for
        # confirm_email), and LocMemCache outlives a single test. Without this
        # the second test in the class gets no mail and the failure looks like
        # a broken template.
        cache.clear()

    def code_from_mail(self):
        self.assertEqual(len(mail.outbox), 1, "expected exactly one email")
        return extract_code(mail.outbox[0].body)

    def test_an_invited_person_can_sign_up_with_any_email_address(self):
        invitation = Invitation.objects.create(label="Anton")
        self.client.get(invitation.get_absolute_url())

        signup = self.client.post(
            reverse("account_signup"), {"email": "anton@firma.dk"}, follow=True
        )
        self.assertEqual(signup.status_code, 200)

        confirm = self.client.post(
            reverse("account_email_verification_sent"),
            {"code": self.code_from_mail()},
            follow=True,
        )

        self.assertEqual(confirm.status_code, 200)
        user = User.objects.get(email="anton@firma.dk")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        invitation.refresh_from_db()
        self.assertEqual(invitation.accepted_by, user)
        self.assertFalse(invitation.is_usable)

    def test_the_account_gets_no_usable_password(self):
        """ACCOUNT_SIGNUP_FIELDS omits them, so there is nothing to reset."""
        invitation = Invitation.objects.create(label="Anton")
        self.client.get(invitation.get_absolute_url())
        self.client.post(reverse("account_signup"), {"email": "anton@firma.dk"})
        self.client.post(
            reverse("account_email_verification_sent"), {"code": self.code_from_mail()}
        )

        self.assertFalse(User.objects.get(email="anton@firma.dk").has_usable_password())

    def test_signing_up_without_an_invitation_is_refused(self):
        response = self.client.post(
            reverse("account_signup"), {"email": "stranger@example.com"}, follow=True
        )

        self.assertTemplateUsed(response, "account/signup_closed.html")
        self.assertFalse(User.objects.filter(email="stranger@example.com").exists())
        self.assertEqual(mail.outbox, [])

    def test_the_signup_page_is_refused_without_an_invitation(self):
        response = self.client.get(reverse("account_signup"))
        self.assertTemplateUsed(response, "account/signup_closed.html")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EmailCodeLoginTests(TestCase):
    """End to end: a returning person asking for a sign-in code."""

    def setUp(self):
        cache.clear()  # see EmailCodeSignupTests.setUp
        self.anton = User.objects.create_user("anton", email="anton@firma.dk")
        EmailAddress.objects.create(
            user=self.anton, email="anton@firma.dk", verified=True, primary=True
        )

    def code_from_mail(self):
        self.assertEqual(len(mail.outbox), 1, "expected exactly one email")
        return extract_code(mail.outbox[0].body)

    def test_a_known_address_gets_a_code_that_logs_them_in(self):
        self.client.post(reverse("account_request_login_code"), {"email": "anton@firma.dk"})

        response = self.client.post(
            reverse("account_confirm_login_code"), {"code": self.code_from_mail()}, follow=True
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.anton.pk)

    def test_a_wrong_code_does_not_log_anyone_in(self):
        self.client.post(reverse("account_request_login_code"), {"email": "anton@firma.dk"})

        self.client.post(reverse("account_confirm_login_code"), {"code": "000000"})

        self.assertNotIn("_auth_user_id", self.client.session)

    def test_an_unknown_address_creates_no_account_and_does_not_say_so(self):
        """ACCOUNT_PREVENT_ENUMERATION: the screen must not reveal whether an
        address has an account, so the mail carries the bad news instead."""
        response = self.client.post(
            reverse("account_request_login_code"), {"email": "stranger@example.com"}, follow=True
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="stranger@example.com").exists())
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("/accounts/signup/", mail.outbox[0].body)

    def test_the_code_email_comes_from_the_configured_sender(self):
        self.client.post(reverse("account_request_login_code"), {"email": "anton@firma.dk"})

        self.assertEqual(mail.outbox[0].from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertIn("Ella", mail.outbox[0].subject)


class ExistingAccountLinkingTests(TestCase):
    """pre_social_login: the break-glass admin signing in with Google."""

    def setUp(self):
        self.adapter = InvitationOnlySocialAccountAdapter()

    def test_a_verified_google_email_links_to_the_existing_account(self):
        admin = User.objects.create_user("admin", email="soren@example.com", password="x")
        sociallogin = google_login(email="soren@example.com")

        self.adapter.pre_social_login(request_with_session(), sociallogin)

        self.assertTrue(SocialAccount.objects.filter(user=admin, provider="google").exists())

    def test_an_unverified_email_does_not_link(self):
        """Otherwise anyone could claim an account by naming its address."""
        User.objects.create_user("admin", email="soren@example.com", password="x")
        sociallogin = google_login(email="soren@example.com", verified=False)

        self.adapter.pre_social_login(request_with_session(), sociallogin)

        self.assertFalse(SocialAccount.objects.exists())

    def test_an_unrelated_email_does_not_link(self):
        User.objects.create_user("admin", email="soren@example.com", password="x")
        sociallogin = google_login(email="someone.else@example.com")

        self.adapter.pre_social_login(request_with_session(), sociallogin)

        self.assertFalse(SocialAccount.objects.exists())


class InviteCommandTests(TestCase):
    def test_it_creates_one_invitation_and_prints_the_link(self):
        out = StringIO()
        call_command("invite", "Anton", stdout=out)

        invitation = Invitation.objects.get()
        self.assertEqual(invitation.label, "Anton")
        self.assertIn(invitation.url, out.getvalue())

    def test_days_sets_the_expiry(self):
        call_command("invite", "Anton", "--days", "2", stdout=StringIO())

        invitation = Invitation.objects.get()
        self.assertLess(invitation.expires_at, timezone.now() + timedelta(days=2, minutes=1))
        self.assertGreater(invitation.expires_at, timezone.now() + timedelta(days=1))
