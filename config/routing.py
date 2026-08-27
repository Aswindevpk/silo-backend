from django.urls import path
from apps.core.consumers import GlobalMultiplexConsumer

websocket_urlpatterns = [
    path('ws/users/', GlobalMultiplexConsumer.as_asgi()),
]
