from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import CommentForm, TicketForm
from .models import STATUS_CHOICES, STATUS_FAERDIG, SWEEP_AFTER, Ticket, sweep_finished_tickets


def _safe_next(request, fallback):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return fallback


def board(request):
    sweep_finished_tickets()
    query = request.GET.get("q", "").strip()

    tickets = Ticket.objects.filter(archived=False)
    if query:
        tickets = tickets.filter(Q(title__icontains=query) | Q(description__icontains=query))

    columns = []
    for i, (value, label) in enumerate(STATUS_CHOICES):
        prev_status = STATUS_CHOICES[i - 1] if i > 0 else None
        next_status = STATUS_CHOICES[i + 1] if i < len(STATUS_CHOICES) - 1 else None
        skip_targets = {value}
        if prev_status:
            skip_targets.add(prev_status[0])
        if next_status:
            skip_targets.add(next_status[0])
        columns.append({
            "value": value,
            "label": label,
            "tickets": tickets.filter(status=value),
            "prev_status": prev_status,
            "next_status": next_status,
            "skip_statuses": [c for c in STATUS_CHOICES if c[0] not in skip_targets],
        })

    context = {
        "columns": columns,
        "query": query,
    }
    return render(request, "vedligehold/board.html", context)


def ticket_create(request):
    initial = {}
    status = request.GET.get("status", "")
    if status in dict(STATUS_CHOICES):
        initial["status"] = status

    if request.method == "POST":
        form = TicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.created_by = request.user
            if ticket.status == STATUS_FAERDIG:
                ticket.completed_at = timezone.now()
            ticket.save()
            return redirect("vedligehold_ticket_detail", pk=ticket.pk)
    else:
        form = TicketForm(initial=initial)
    return render(request, "vedligehold/ticket_form.html", {"form": form})


def ticket_edit(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    # The status buttons are hidden on archived tickets, and so is Rediger:
    # a status set here would leave the ticket archived and off the board.
    if ticket.archived:
        return redirect("vedligehold_ticket_detail", pk=ticket.pk)
    if request.method == "POST":
        old_status = ticket.status
        form = TicketForm(request.POST, instance=ticket)
        if form.is_valid():
            ticket = form.save(commit=False)
            # The form has already written the new status onto the instance;
            # put the old one back so set_status() sees the change and keeps
            # completed_at right.
            new_status, ticket.status = ticket.status, old_status
            ticket.set_status(new_status)
            ticket.save()
            return redirect("vedligehold_ticket_detail", pk=ticket.pk)
    else:
        form = TicketForm(instance=ticket)
    return render(request, "vedligehold/ticket_form.html", {"form": form, "ticket": ticket})


@require_POST
def ticket_delete(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    was_archived = ticket.archived
    ticket.delete()  # its comments go with it (CASCADE)
    return redirect("vedligehold_archive" if was_archived else "vedligehold")


def ticket_detail(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.ticket = ticket
            comment.author = request.user
            comment.save()
            return redirect("vedligehold_ticket_detail", pk=ticket.pk)
    else:
        form = CommentForm()

    sweep_date = None
    if ticket.status == STATUS_FAERDIG and not ticket.archived and ticket.completed_at:
        sweep_date = ticket.completed_at + SWEEP_AFTER

    context = {
        "ticket": ticket,
        "comments": ticket.comments.all(),
        "form": form,
        "status_choices": [c for c in STATUS_CHOICES if c[0] != ticket.status],
        "sweep_date": sweep_date,
    }
    return render(request, "vedligehold/ticket_detail.html", context)


@require_POST
def move_ticket(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    new_status = request.POST.get("status")
    if new_status in dict(STATUS_CHOICES):
        ticket.set_status(new_status)
        ticket.save()
    return redirect(_safe_next(request, reverse("vedligehold")))


@require_POST
def archive_ticket(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    ticket.archive()
    ticket.save()
    return redirect(_safe_next(request, reverse("vedligehold_ticket_detail", args=[pk])))


@require_POST
def reopen_ticket(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    ticket.reopen()
    ticket.save()
    return redirect(_safe_next(request, reverse("vedligehold_ticket_detail", args=[pk])))


def archive_list(request):
    sweep_finished_tickets()
    query = request.GET.get("q", "").strip()

    tickets = Ticket.objects.filter(archived=True)
    if query:
        tickets = tickets.filter(Q(title__icontains=query) | Q(description__icontains=query))

    context = {"tickets": tickets, "query": query}
    return render(request, "vedligehold/archive.html", context)
