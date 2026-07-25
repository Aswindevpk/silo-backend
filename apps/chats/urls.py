from django.urls import path
from .views import (
    ChannelListCreateView, MessageListView, DirectMessageChannelView, DirectMessageListView
)

urlpatterns = [
    path('workspaces/<slug:workspace_slug>/channels/', ChannelListCreateView.as_view(), name='channel_list_create'),
    path('channels/<int:channel_id>/messages/', MessageListView.as_view(), name='message_list'),
    path('workspaces/<slug:workspace_slug>/direct-messages/', DirectMessageListView.as_view(), name='direct_message_list'),
    path('workspaces/<slug:workspace_slug>/direct-messages/<str:target_email>/', DirectMessageChannelView.as_view(), name='direct_message_channel'),
]
