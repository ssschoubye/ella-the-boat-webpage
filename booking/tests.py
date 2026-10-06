from datetime import datetime
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Booking

User = get_user_model()


class BookerAttributionTests(TestCase):
    """The booker is whoever is signed in, and only that (ADR 0011).

    It used to be a dropdown of hardcoded names, so anyone could book as
    anyone. These tests are the reason that is no longer possible.
    """

    def setUp(self):
        self.anton = User.objects.create_user("anton", first_name="Anton")
        self.someone_else = User.objects.create_user("emil", first_name="Emil")
        self.client.force_login(self.anton)

    def post_a_trip(self, **extra):
        return self.client.post(
            reverse("tilfoj_tur"),
            {
                "title": "Weekendtur",
                "start_date": "2026-07-04T09:00",
                "end_date": "2026-07-05T17:00",
                "notes": "",
                "repeat_type": "none",
                **extra,
            },
        )

    def test_the_booker_is_the_signed_in_user(self):
        self.post_a_trip()

        self.assertEqual(Booking.objects.get().booker, self.anton)

    def test_a_posted_booker_is_ignored(self):
        """The field is not on the form, so Django drops it. Pinned here so
        that re-adding it to BookingForm.Meta.fields fails loudly."""
        self.post_a_trip(booker=self.someone_else.pk)

        self.assertEqual(Booking.objects.get().booker, self.anton)

    def test_the_form_has_no_booker_field(self):
        response = self.client.get(reverse("tilfoj_tur"))
        self.assertNotContains(response, 'name="booker"')

    def test_a_repeating_trip_attributes_every_occurrence(self):
        self.post_a_trip(repeat_type="weekly", repeat_count=3)

        bookings = Booking.objects.all()
        self.assertEqual(bookings.count(), 3)
        self.assertEqual({b.booker_id for b in bookings}, {self.anton.pk})

    def test_a_trip_that_does_not_repeat_is_saved_once_whatever_the_count(self):
        self.post_a_trip(repeat_type="none", repeat_count=1)
        self.post_a_trip(repeat_type="none", repeat_count=7)

        self.assertEqual(Booking.objects.count(), 2)

    def test_a_repeating_trip_needs_at_least_two(self):
        response = self.post_a_trip(repeat_type="weekly", repeat_count=1)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Booking.objects.exists())

    def test_editing_someone_elses_trip_does_not_reassign_it(self):
        """Everyone may edit everything here, but the record of who booked it
        should survive a correction to the dates."""
        booking = Booking.objects.create(
            title="Emils tur",
            booker=self.someone_else,
            start_date="2026-07-04T09:00Z",
            end_date="2026-07-05T17:00Z",
        )

        self.client.post(
            reverse("rediger_tur", args=[booking.pk]),
            {
                "title": "Emils tur",
                "start_date": "2026-07-04T10:00",
                "end_date": "2026-07-05T17:00",
                "notes": "",
            },
        )

        booking.refresh_from_db()
        self.assertEqual(booking.booker, self.someone_else)


class DeletedAccountTests(TestCase):
    def test_deleting_an_account_keeps_the_booking(self):
        """SET_NULL: losing an account must not lose the boat's history."""
        user = User.objects.create_user("anton", first_name="Anton")
        Booking.objects.create(
            title="Tur", booker=user, start_date="2026-07-04T09:00Z", end_date="2026-07-05T17:00Z"
        )

        user.delete()

        self.assertIsNone(Booking.objects.get().booker)


class AddFromCalendarDayTests(TestCase):
    """Clicking a day in the calendar opens the form with that day filled in."""

    def setUp(self):
        self.client.force_login(User.objects.create_user("anton"))

    def test_a_day_prefills_start_and_end(self):
        response = self.client.get(reverse("tilfoj_tur") + "?dato=2026-07-04")
        self.assertContains(response, 'value="2026-07-04T09:00"')
        self.assertContains(response, 'value="2026-07-04T13:00"')

    def test_a_garbled_day_gives_an_empty_form(self):
        response = self.client.get(reverse("tilfoj_tur") + "?dato=nonsense")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'value="20')

    def test_month_and_week_days_link_to_the_form(self):
        link = reverse("tilfoj_tur") + "?dato=2026-07-04"
        self.assertContains(self.client.get(reverse("kalender_month", args=[2026, 7])), link)
        self.assertContains(self.client.get(reverse("kalender_uge_at", args=[2026, 27])), link)


class ListViewTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user("anton"))

    def test_dates_show_the_weekday(self):
        # 2099-07-04 is a Saturday, 2099-07-05 a Sunday.
        Booking.objects.create(
            title="Weekendtur",
            start_date=datetime(2099, 7, 4, 9, tzinfo=ZoneInfo("Europe/Copenhagen")),
            end_date=datetime(2099, 7, 5, 17, tzinfo=ZoneInfo("Europe/Copenhagen")),
        )
        response = self.client.get(reverse("kalender_liste"))
        self.assertContains(response, "Lør 4. kl. 09:00")
        self.assertContains(response, "Søn 5. kl. 17:00")
