from django.contrib import admin

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("title", "booker", "start_date", "end_date", "series_id")
    list_filter = ("booker", "start_date")
    search_fields = ("title", "notes")
