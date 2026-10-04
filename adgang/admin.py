from django.contrib import admin

from .models import Invitation


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("label", "status", "created_at", "expires_at", "accepted_by")
    list_filter = ("revoked",)
    search_fields = ("label",)
    readonly_fields = ("link", "created_at", "accepted_at", "accepted_by")
    fields = ("label", "expires_at", "revoked", "link", "created_at", "accepted_at", "accepted_by")

    @admin.display(description="Link til afsendelse")
    def link(self, obj):
        """Shown on the change form so the link can be copied out of the admin
        on a phone, which is the usual way one gets sent."""
        if not obj.pk:
            return "Gem invitationen, så vises linket her."
        return obj.url

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
