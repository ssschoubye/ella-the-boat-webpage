from django.apps import AppConfig


class AdgangConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "adgang"
    verbose_name = "Adgang"

    def ready(self):
        # Registers spend_invitation on allauth's user_signed_up.
        from . import signals  # noqa: F401
