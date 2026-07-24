from django.urls import path
from .views import ChannelListCreateView, ChannelMessageListView, DirectMessageListView

urlpatterns = [
    path('workspaces/<slug:workspace_slug>/channels/', ChannelListCreateView.as_view(), name='channel-list-create'),
    path('workspaces/<slug:workspace_slug>/direct-messages/<str:target_email>/', DirectMessageListView.as_view(), name='dm-list'),
    path('channels/<int:channel_id>/messages/', ChannelMessageListView.as_view(), name='channel-messages-list'),
]
