"""Rendering a person.

The booker, uploader and ticket author are accounts now (ADR 0011), and an
account created from a Google login has a first name but a machine-generated
username. So templates ask for a name through this filter rather than
rendering the object, which would print that username.
"""
from django import template

register = template.Library()


@register.filter
def person(user):
    """A short display name, or "Ukendt" for a record whose account is gone."""
    if user is None:
        return "Ukendt"
    name = (user.get_short_name() or "").strip()
    if name:
        return name
    # No first name from the provider: the part of the email before the @ is
    # the least bad remaining option, and better than a generated username.
    email = (user.email or "").strip()
    if email:
        return email.split("@")[0]
    return user.get_username()
