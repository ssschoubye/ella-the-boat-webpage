import calendar
import uuid
from datetime import date, timedelta

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import BookingForm
from .models import Booking

REPEAT_STEPS = {
    "weekly": timedelta(weeks=1),
    "biweekly": timedelta(weeks=2),
}


def _add_months(dt, months):
    month_index = dt.month - 1 + months
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def _shift_datetime(dt, repeat_type, step_index):
    if repeat_type == "monthly":
        return _add_months(dt, step_index)
    return dt + REPEAT_STEPS[repeat_type] * step_index

DANISH_MONTHS = [
    "", "Januar", "Februar", "Marts", "April", "Maj", "Juni",
    "Juli", "August", "September", "Oktober", "November", "December",
]
DANISH_WEEKDAYS = ["Man", "Tir", "Ons", "Tor", "Fre", "Lør", "Søn"]
DANISH_WEEKDAYS_FULL = ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag", "Søndag"]


def _date_label(d):
    return f"{d.day}. {DANISH_MONTHS[d.month].lower()}"


def _group_by_month(bookings):
    groups = []
    current_key = None
    current_items = None
    for booking in bookings:
        key = (booking.start_date.year, booking.start_date.month)
        if key != current_key:
            current_key = key
            current_items = []
            groups.append((f"{DANISH_MONTHS[key[1]]} {key[0]}", current_items))
        current_items.append(booking)
    return groups


def month_view(request, year=None, month=None):
    today = date.today()
    year = year or today.year
    month = month or today.month

    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdatescalendar(year, month)

    bookings = Booking.objects.filter(
        start_date__date__lte=weeks[-1][-1],
        end_date__date__gte=weeks[0][0],
    )
    bookings_by_day = {}
    for booking in bookings:
        day = max(booking.start_date.date(), weeks[0][0])
        last = min(booking.end_date.date(), weeks[-1][-1])
        while day <= last:
            bookings_by_day.setdefault(day, []).append(booking)
            day += timedelta(days=1)

    calendar_weeks = []
    for week in weeks:
        week_start_col, week_end_col = week[0], week[-1]
        week_days = []
        for day in week:
            entries = []
            for booking in bookings_by_day.get(day, []):
                start_d = booking.start_date.date()
                end_d = booking.end_date.date()
                entries.append({
                    "booking": booking,
                    "is_run_start": day == start_d or day == week_start_col,
                    "is_run_end": day == end_d or day == week_end_col,
                    "is_multi_day": start_d != end_d,
                })
            week_days.append({
                "date": day,
                "in_month": day.month == month,
                "is_today": day == today,
                "entries": entries,
            })
        calendar_weeks.append(week_days)

    prev_month = month - 1 or 12
    prev_year = year - 1 if month == 1 else year
    next_month = month + 1 if month < 12 else 1
    next_year = year + 1 if month == 12 else year

    context = {
        "active_view": "month",
        "weekdays": DANISH_WEEKDAYS,
        "calendar_weeks": calendar_weeks,
        "month_label": f"{DANISH_MONTHS[month]} {year}",
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
        "is_current_month": year == today.year and month == today.month,
        "upcoming": Booking.objects.filter(end_date__date__gte=today).order_by("start_date")[:5],
    }
    return render(request, "booking/calendar.html", context)


def week_view(request, year=None, week=None):
    today = date.today()
    if year is None or week is None:
        iso_year, iso_week, _ = today.isocalendar()
    else:
        iso_year, iso_week = year, week

    week_start = date.fromisocalendar(iso_year, iso_week, 1)
    week_end = week_start + timedelta(days=6)

    bookings = Booking.objects.filter(
        start_date__date__lte=week_end,
        end_date__date__gte=week_start,
    )
    bookings_by_day = {}
    for booking in bookings:
        day = max(booking.start_date.date(), week_start)
        last = min(booking.end_date.date(), week_end)
        while day <= last:
            bookings_by_day.setdefault(day, []).append(booking)
            day += timedelta(days=1)

    days = []
    for i in range(7):
        d = week_start + timedelta(days=i)
        days.append({
            "date": d,
            "weekday_full": DANISH_WEEKDAYS_FULL[i],
            "date_label": _date_label(d),
            "is_today": d == today,
            "bookings": bookings_by_day.get(d, []),
        })

    prev_week_date = week_start - timedelta(days=7)
    next_week_date = week_start + timedelta(days=7)
    prev_iso_year, prev_iso_week, _ = prev_week_date.isocalendar()
    next_iso_year, next_iso_week, _ = next_week_date.isocalendar()

    context = {
        "active_view": "week",
        "days": days,
        "week_label": f"Uge {iso_week}, {iso_year}",
        "week_range_label": f"{_date_label(week_start)} – {_date_label(week_end)}",
        "prev_year": prev_iso_year,
        "prev_week": prev_iso_week,
        "next_year": next_iso_year,
        "next_week": next_iso_week,
        "is_current_week": (iso_year, iso_week) == today.isocalendar()[:2],
    }
    return render(request, "booking/calendar_week.html", context)


def list_view(request):
    today = date.today()
    upcoming = Booking.objects.filter(end_date__date__gte=today).order_by("start_date")
    past = Booking.objects.filter(end_date__date__lt=today).order_by("-start_date")

    context = {
        "active_view": "list",
        "upcoming_groups": _group_by_month(upcoming),
        "past_groups": _group_by_month(past),
        "past_count": past.count(),
    }
    return render(request, "booking/calendar_list.html", context)


def add_booking(request):
    if request.method == "POST":
        form = BookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            # Whoever is signed in is the booker. It is no longer a dropdown,
            # so the recorded name is always the real one (ADR 0011).
            booking.booker = request.user
            repeat_type = form.cleaned_data.get("repeat_type") or "none"
            repeat_count = form.cleaned_data.get("repeat_count") or 1

            if repeat_type == "none":
                booking.save()
            else:
                series_id = uuid.uuid4()
                occurrences = [
                    Booking(
                        title=booking.title,
                        booker=booking.booker,
                        start_date=_shift_datetime(booking.start_date, repeat_type, i),
                        end_date=_shift_datetime(booking.end_date, repeat_type, i),
                        notes=booking.notes,
                        series_id=series_id,
                    )
                    for i in range(repeat_count)
                ]
                Booking.objects.bulk_create(occurrences)
                booking = occurrences[0]

            return redirect(
                reverse("kalender_month", args=[booking.start_date.year, booking.start_date.month])
            )
    else:
        form = BookingForm()
    return render(request, "booking/booking_form.html", {"form": form, "booking": None})


def edit_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if request.method == "POST":
        form = BookingForm(request.POST, instance=booking)
        form.fields.pop("repeat_type", None)
        form.fields.pop("repeat_count", None)
        if form.is_valid():
            booking = form.save()
            return redirect(
                reverse("kalender_month", args=[booking.start_date.year, booking.start_date.month])
            )
    else:
        form = BookingForm(instance=booking)
        form.fields.pop("repeat_type", None)
        form.fields.pop("repeat_count", None)

    series_count = None
    if booking.series_id:
        series_count = Booking.objects.filter(series_id=booking.series_id).count()

    return render(request, "booking/booking_form.html", {
        "form": form,
        "booking": booking,
        "series_count": series_count,
    })


@require_POST
def delete_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    year, month = booking.start_date.year, booking.start_date.month
    booking.delete()
    return redirect(reverse("kalender_month", args=[year, month]))


@require_POST
def delete_series(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    year, month = booking.start_date.year, booking.start_date.month
    if booking.series_id:
        Booking.objects.filter(series_id=booking.series_id).delete()
    else:
        booking.delete()
    return redirect(reverse("kalender_month", args=[year, month]))
