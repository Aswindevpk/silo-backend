from django.urls import re_path
from apps.core.consumers import GlobalMultiplexConsumer

websocket_urlpatterns = [
    # Allow with or without trailing slash
    re_path(r'^ws/users/?$', GlobalMultiplexConsumer.as_asgi()),
]
