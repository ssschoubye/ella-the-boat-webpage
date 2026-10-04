from datetime import timedelta
from io import StringIO

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialLogin
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.utils import timezone

from .adapters import InvitationOnlySocialAccountAdapter, pending_invitation, remember_invitation
from .models import SESSION_KEY, Invitation

User = get_user_model()


def google_login(email="anton@example.com", first_name="Anton", verified=True, uid="g-1"):
    """A SocialLogin as allauth would hand one to the adapter after Google."""
    return SocialLogin(
        user=User(email=email, first_name=first_name),
        account=SocialAccount(provider="google", uid=uid, extra_data={"email": email}),
        email_addresses=[EmailAddress(email=email, verified=verified, primary=True)],
    )


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
    def setUp(self):
        self.adapter = InvitationOnlySocialAccountAdapter()

    def test_signup_is_closed_without_an_invitation(self):
        request = request_with_session()
        self.assertFalse(self.adapter.is_open_for_signup(request, google_login()))

    def test_signup_is_open_while_holding_a_usable_invitation(self):
        request = request_with_session()
        remember_invitation(request, Invitation.objects.create(label="Anton"))
        self.assertTrue(self.adapter.is_open_for_signup(request, google_login()))

    def test_signup_is_closed_once_the_invitation_is_spent(self):
        invitation = Invitation.objects.create(label="Anton")
        request = request_with_session()
        remember_invitation(request, invitation)
        invitation.accept(User.objects.create_user("earlier"))

        self.assertFalse(self.adapter.is_open_for_signup(request, google_login()))

    def test_saving_a_user_spends_the_invitation_and_clears_the_session(self):
        invitation = Invitation.objects.create(label="Anton")
        request = request_with_session()
        remember_invitation(request, invitation)

        user = self.adapter.save_user(request, google_login())

        invitation.refresh_from_db()
        self.assertEqual(invitation.accepted_by, user)
        self.assertIsNotNone(invitation.accepted_at)
        self.assertFalse(invitation.is_usable)
        self.assertNotIn(SESSION_KEY, request.session)

    def test_the_account_keeps_the_name_and_email_from_google(self):
        request = request_with_session()
        remember_invitation(request, Invitation.objects.create(label="Anton"))

        user = self.adapter.save_user(
            request, google_login(email="a@example.com", first_name="Anton")
        )

        self.assertEqual(user.first_name, "Anton")
        self.assertEqual(user.email, "a@example.com")


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
