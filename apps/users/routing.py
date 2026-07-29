from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/users/', consumers.GlobalConsumer.as_asgi()),
]
