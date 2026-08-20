from django.urls import path
from apps.core.consumers import GlobalMultiplexConsumer

websocket_urlpatterns = [
    # Using the single original endpoint to prevent frontend modifications
    path('ws/users/', GlobalMultiplexConsumer.as_asgi()),
]
