from django.contrib import admin

from .models import Comment, Ticket


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "created_by", "archived", "updated_at")
    list_filter = ("status", "archived", "created_by")
    search_fields = ("title", "description")
    inlines = [CommentInline]
