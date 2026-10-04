from datetime import timedelta
from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Invitation

User = get_user_model()

GOOD_PASSWORD = "Spraydaek-42-Agterspejl"


def signup_post(**overrides):
    return {
        "first_name": "Anton",
        "email": "anton@firma.dk",
        "password1": GOOD_PASSWORD,
        "password2": GOOD_PASSWORD,
        **overrides,
    }


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


class SignupThroughInvitationTests(TestCase):
    """The only way an account comes into existence (ADR 0014)."""

    def test_it_creates_the_account_and_signs_them_in(self):
        invitation = Invitation.objects.create(label="Anton")

        response = self.client.post(invitation.get_absolute_url(), signup_post())

        self.assertRedirects(response, reverse("home"))
        user = User.objects.get(email="anton@firma.dk")
        self.assertEqual(user.username, "anton@firma.dk")
        self.assertEqual(user.first_name, "Anton")
        self.assertTrue(user.check_password(GOOD_PASSWORD))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_it_spends_the_invitation(self):
        invitation = Invitation.objects.create(label="Anton")

        self.client.post(invitation.get_absolute_url(), signup_post())

        invitation.refresh_from_db()
        self.assertEqual(invitation.accepted_by, User.objects.get())
        self.assertIsNotNone(invitation.accepted_at)
        self.assertFalse(invitation.is_usable)

    def test_the_same_link_cannot_be_used_twice(self):
        invitation = Invitation.objects.create(label="Anton")
        self.client.post(invitation.get_absolute_url(), signup_post())
        self.client.logout()

        response = self.client.post(
            invitation.get_absolute_url(), signup_post(email="someone.else@firma.dk")
        )

        self.assertEqual(response.status_code, 410)
        self.assertEqual(User.objects.count(), 1)

    def test_a_revoked_link_is_refused_on_post_not_just_on_get(self):
        """Someone could sit on the open form while the link is pulled."""
        invitation = Invitation.objects.create(label="Anton")
        self.client.get(invitation.get_absolute_url())
        Invitation.objects.filter(pk=invitation.pk).update(revoked=True)

        response = self.client.post(invitation.get_absolute_url(), signup_post())

        self.assertEqual(response.status_code, 410)
        self.assertFalse(User.objects.exists())

    def test_an_expired_link_creates_nothing(self):
        invitation = Invitation.objects.create(
            label="Anton", expires_at=timezone.now() - timedelta(seconds=1)
        )

        response = self.client.post(invitation.get_absolute_url(), signup_post())

        self.assertEqual(response.status_code, 410)
        self.assertFalse(User.objects.exists())

    def test_an_unknown_token_is_a_404_and_creates_nothing(self):
        response = self.client.post("/invitation/not-a-real-token/", signup_post())

        self.assertEqual(response.status_code, 404)
        self.assertFalse(User.objects.exists())

    def test_there_is_no_signup_url_other_than_an_invitation(self):
        for path in ("/signup/", "/accounts/signup/", "/register/"):
            with self.subTest(path=path):
                self.assertIn(self.client.get(path).status_code, (301, 302, 404))
        self.assertFalse(User.objects.exists())

    def test_the_invitation_page_is_reachable_without_logging_in(self):
        invitation = Invitation.objects.create(label="Anton")
        self.assertEqual(self.client.get(invitation.get_absolute_url()).status_code, 200)


class SignupValidationTests(TestCase):
    def setUp(self):
        self.invitation = Invitation.objects.create(label="Anton")

    def post(self, **overrides):
        return self.client.post(self.invitation.get_absolute_url(), signup_post(**overrides))

    def assert_rejected(self, response, expected_users=0):
        """The form came back with errors, no account was added, and the link
        is still good -- a rejected attempt must not burn the invitation."""
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), expected_users)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.invitation.refresh_from_db()
        self.assertTrue(self.invitation.is_usable, "a rejected signup must not spend the link")

    def test_mismatched_passwords_are_rejected(self):
        self.assert_rejected(self.post(password2="noget-helt-andet-42"))

    def test_a_weak_password_is_rejected(self):
        """Django's own validators, since nothing else is guarding these."""
        self.assert_rejected(self.post(password1="kode", password2="kode"))

    def test_an_all_numeric_password_is_rejected(self):
        self.assert_rejected(self.post(password1="83927461", password2="83927461"))

    def test_a_common_password_is_rejected(self):
        self.assert_rejected(self.post(password1="password1", password2="password1"))

    def test_an_invalid_email_is_rejected(self):
        self.assert_rejected(self.post(email="ikke-en-adresse"))

    def test_an_address_already_in_use_is_rejected(self):
        User.objects.create_user("anton@firma.dk", email="anton@firma.dk", password="x")
        self.assert_rejected(self.post(email="anton@firma.dk"), expected_users=1)

    def test_the_address_is_matched_case_insensitively(self):
        """Anton@ and anton@ must not become two accounts."""
        User.objects.create_user("anton@firma.dk", email="anton@firma.dk", password="x")
        self.assert_rejected(self.post(email="Anton@Firma.DK"), expected_users=1)

    def test_the_address_is_stored_lower_case(self):
        self.client.post(self.invitation.get_absolute_url(), signup_post(email="Anton@Firma.DK"))

        user = User.objects.get()
        self.assertEqual(user.username, "anton@firma.dk")
        self.assertEqual(user.email, "anton@firma.dk")


class LoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "anton@firma.dk", email="anton@firma.dk", password=GOOD_PASSWORD, first_name="Anton"
        )

    def test_logging_in_with_the_email_address(self):
        response = self.client.post(
            reverse("login"), {"username": "anton@firma.dk", "password": GOOD_PASSWORD}
        )

        self.assertRedirects(response, reverse("home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_the_address_is_case_insensitive_on_the_way_in_too(self):
        response = self.client.post(
            reverse("login"), {"username": "Anton@Firma.DK", "password": GOOD_PASSWORD}
        )

        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_a_wrong_password_does_not_sign_anyone_in(self):
        self.client.post(
            reverse("login"), {"username": "anton@firma.dk", "password": "forkert-42-kode"}
        )

        self.assertNotIn("_auth_user_id", self.client.session)

    def test_a_deactivated_account_cannot_log_in(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        self.client.post(
            reverse("login"), {"username": "anton@firma.dk", "password": GOOD_PASSWORD}
        )

        self.assertNotIn("_auth_user_id", self.client.session)

    def test_the_login_page_is_public(self):
        self.assertEqual(self.client.get(reverse("login")).status_code, 200)


class LockoutTests(TestCase):
    """django-axes is the main defence now that the login page is public and
    the credential is a password people chose themselves (ADR 0014)."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            "anton@firma.dk", email="anton@firma.dk", password=GOOD_PASSWORD
        )

    def attempt(self, password):
        return self.client.post(
            reverse("login"),
            {"username": "anton@firma.dk", "password": password},
            # axes attributes attempts to this header in production, because
            # every request arrives via cloudflared and Caddy.
            HTTP_CF_CONNECTING_IP="203.0.113.7",
        )

    def test_guessing_is_locked_out_after_five_tries(self):
        for _ in range(settings.AXES_FAILURE_LIMIT):
            self.attempt("forkert-42-kode")

        blocked = self.attempt("forkert-42-kode")

        # axes 8 answers 429 Too Many Requests, not 403.
        self.assertEqual(blocked.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_the_lockout_survives_the_right_password(self):
        """Otherwise the limit only slows a guesser down until they land it."""
        for _ in range(settings.AXES_FAILURE_LIMIT):
            self.attempt("forkert-42-kode")

        blocked = self.attempt(GOOD_PASSWORD)

        self.assertEqual(blocked.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_a_few_wrong_tries_then_the_right_one_still_works(self):
        self.attempt("forkert-42-kode")
        self.attempt("forkert-42-kode")

        self.attempt(GOOD_PASSWORD)

        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)


class RenameLoginCommandTests(TestCase):
    """The username is the login identifier, so renaming it must be safe."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            "soren", email="soren@firma.dk", password=GOOD_PASSWORD
        )

    def test_it_moves_the_login_to_the_email_address(self):
        call_command("rename_login", "soren", "Soren@Firma.DK", stdout=StringIO())

        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "soren@firma.dk")
        self.assertEqual(self.user.email, "soren@firma.dk")

    def test_the_renamed_account_can_then_use_the_site_login(self):
        """The point of the command: /login/ is an email field, so a superuser
        called `soren` could only ever get in via /admin/."""
        before = self.client.post(
            reverse("login"), {"username": "soren", "password": GOOD_PASSWORD}
        )
        self.assertEqual(before.status_code, 200)  # form redisplayed: not an email
        self.assertNotIn("_auth_user_id", self.client.session)

        call_command("rename_login", "soren", "soren@firma.dk", stdout=StringIO())

        response = self.client.post(
            reverse("login"), {"username": "soren@firma.dk", "password": GOOD_PASSWORD}
        )

        self.assertRedirects(response, reverse("home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_it_keeps_their_history(self):
        from booking.models import Booking

        Booking.objects.create(
            title="Tur", booker=self.user,
            start_date="2026-07-04T09:00Z", end_date="2026-07-05T17:00Z",
        )

        call_command("rename_login", "soren", "soren@firma.dk", stdout=StringIO())

        self.assertEqual(Booking.objects.get().booker_id, self.user.pk)

    def test_an_unknown_account_is_an_error(self):
        with self.assertRaises(CommandError):
            call_command("rename_login", "nobody", "x@firma.dk", stdout=StringIO())

    def test_an_invalid_address_is_an_error(self):
        with self.assertRaises(CommandError):
            call_command("rename_login", "soren", "not-an-address", stdout=StringIO())
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "soren")

    def test_a_clash_is_an_error_rather_than_a_merge(self):
        User.objects.create_user("anton@firma.dk", email="anton@firma.dk", password="x")

        with self.assertRaises(CommandError):
            call_command("rename_login", "soren", "anton@firma.dk", stdout=StringIO())

        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "soren")


class ListPeopleCommandTests(TestCase):
    def test_it_warns_about_a_username_that_cannot_use_the_login(self):
        User.objects.create_superuser("soren", email="soren@firma.dk", password="x")

        out = StringIO()
        call_command("list_people", stdout=out)

        printed = out.getvalue()
        self.assertIn("soren", printed)
        self.assertIn("rename_login", printed)

    def test_it_is_quiet_about_a_normal_account(self):
        User.objects.create_user("anton@firma.dk", email="anton@firma.dk", password="x")

        out = StringIO()
        call_command("list_people", stdout=out)

        printed = out.getvalue()
        self.assertIn("anton@firma.dk", printed)
        self.assertNotIn("rename_login", printed)

    def test_it_copes_with_no_accounts(self):
        out = StringIO()
        call_command("list_people", stdout=out)
        self.assertIn("No accounts yet", out.getvalue())


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
