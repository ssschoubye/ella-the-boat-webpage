"""
ASGI config for the project. Only needed if you later add async features
(e.g. Django Channels, websockets).
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_asgi_application()
