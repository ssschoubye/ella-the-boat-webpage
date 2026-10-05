from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import STATUS_FAERDIG, STATUS_ONSKE, Comment, Ticket

User = get_user_model()


class AuthorAttributionTests(TestCase):
    """created_by and author are the signed-in account (ADR 0011)."""

    def setUp(self):
        self.anton = User.objects.create_user("anton", first_name="Anton")
        self.someone_else = User.objects.create_user("emil", first_name="Emil")
        self.client.force_login(self.anton)

    def test_a_new_ticket_records_its_real_creator(self):
        self.client.post(
            reverse("vedligehold_ticket_create"),
            {"title": "Skifte zinkanode", "description": "", "status": STATUS_ONSKE},
        )

        self.assertEqual(Ticket.objects.get().created_by, self.anton)

    def test_a_posted_creator_is_ignored(self):
        self.client.post(
            reverse("vedligehold_ticket_create"),
            {
                "title": "Skifte zinkanode",
                "description": "",
                "status": STATUS_ONSKE,
                "created_by": self.someone_else.pk,
            },
        )

        self.assertEqual(Ticket.objects.get().created_by, self.anton)

    def test_a_comment_records_its_real_author(self):
        ticket = Ticket.objects.create(title="Skifte zinkanode", created_by=self.someone_else)

        self.client.post(
            reverse("vedligehold_ticket_detail", args=[ticket.pk]),
            {"text": "Jeg har en anode liggende."},
        )

        comment = Comment.objects.get()
        self.assertEqual(comment.author, self.anton)
        self.assertEqual(comment.ticket, ticket)

    def test_a_posted_comment_author_is_ignored(self):
        ticket = Ticket.objects.create(title="Skifte zinkanode")

        self.client.post(
            reverse("vedligehold_ticket_detail", args=[ticket.pk]),
            {"text": "Hej", "author": self.someone_else.pk},
        )

        self.assertEqual(Comment.objects.get().author, self.anton)

    def test_the_forms_have_no_person_fields(self):
        ticket = Ticket.objects.create(title="Skifte zinkanode")

        create_page = self.client.get(reverse("vedligehold_ticket_create"))
        detail_page = self.client.get(reverse("vedligehold_ticket_detail", args=[ticket.pk]))

        self.assertNotContains(create_page, 'name="created_by"')
        self.assertNotContains(detail_page, 'name="author"')


class EditAndDeleteTests(TestCase):
    def setUp(self):
        self.anton = User.objects.create_user("anton", first_name="Anton")
        self.someone_else = User.objects.create_user("emil", first_name="Emil")
        self.client.force_login(self.anton)
        self.ticket = Ticket.objects.create(title="Skifte zinkanode", created_by=self.someone_else)

    def edit(self, **fields):
        data = {"title": self.ticket.title, "description": "", "status": self.ticket.status, **fields}
        return self.client.post(reverse("vedligehold_ticket_edit", args=[self.ticket.pk]), data)

    def test_editing_changes_the_ticket_but_not_its_creator(self):
        response = self.edit(title="Skifte begge zinkanoder", description="Før søsætning")

        self.assertRedirects(response, reverse("vedligehold_ticket_detail", args=[self.ticket.pk]))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.title, "Skifte begge zinkanoder")
        self.assertEqual(self.ticket.description, "Før søsætning")
        self.assertEqual(self.ticket.created_by, self.someone_else)

    def test_editing_the_status_to_done_and_back_manages_completed_at(self):
        self.edit(status=STATUS_FAERDIG)
        self.ticket.refresh_from_db()
        self.assertIsNotNone(self.ticket.completed_at)

        self.edit(status=STATUS_ONSKE)
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.completed_at)

    def test_deleting_removes_the_ticket_and_its_comments(self):
        Comment.objects.create(ticket=self.ticket, text="Har købt dem", author=self.anton)

        response = self.client.post(reverse("vedligehold_ticket_delete", args=[self.ticket.pk]))

        self.assertRedirects(response, reverse("vedligehold"))
        self.assertFalse(Ticket.objects.exists())
        self.assertFalse(Comment.objects.exists())

    def test_deleting_needs_a_post(self):
        response = self.client.get(reverse("vedligehold_ticket_delete", args=[self.ticket.pk]))

        self.assertEqual(response.status_code, 405)
        self.assertTrue(Ticket.objects.exists())

    def test_the_ticket_page_has_both_buttons(self):
        response = self.client.get(reverse("vedligehold_ticket_detail", args=[self.ticket.pk]))

        self.assertContains(response, reverse("vedligehold_ticket_edit", args=[self.ticket.pk]))
        self.assertContains(response, reverse("vedligehold_ticket_delete", args=[self.ticket.pk]))
