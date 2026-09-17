from django import template
from django.utils import timezone

register = template.Library()

DANISH_MONTHS = [
    "", "januar", "februar", "marts", "april", "maj", "juni",
    "juli", "august", "september", "oktober", "november", "december",
]


@register.filter
def danish_datetime(value):
    """Format a timezone-aware datetime as '19. august 2026 kl. 14:30' in local time."""
    if not value:
        return ""
    local = timezone.localtime(value)
    return f"{local.day}. {DANISH_MONTHS[local.month]} {local.year} kl. {local.strftime('%H:%M')}"
