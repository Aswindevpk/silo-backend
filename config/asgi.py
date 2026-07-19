"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os
from pathlib import Path
import environ

# Load .env file explicitly if it exists so we can grab DJANGO_SETTINGS_MODULE
env = environ.Env()
env_file = Path(__file__).resolve().parent.parent / '.env'
if env_file.exists():
    environ.Env.read_env(env_file)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', env('DJANGO_SETTINGS_MODULE', default='config.settings.development'))

from django.conf import settings
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.core.asgi import get_asgi_application

# 1. Initialize Django completely FIRST
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from apps.users.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": URLRouter(websocket_urlpatterns),
})

# Wrap the root ProtocolTypeRouter application with ASGIStaticFilesHandler for local development
if settings.DEBUG:
    application = ASGIStaticFilesHandler(application)
