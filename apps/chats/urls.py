from django.urls import path
from .views import ChannelListCreateView, TopicListCreateView, ReplyListCreateView

urlpatterns = [
    path('workspaces/<slug:workspace_slug>/channels/', ChannelListCreateView.as_view(), name='channel-list-create'),
    path('channels/<int:channel_id>/topics/', TopicListCreateView.as_view(), name='topic-list-create'),
    path('topics/<int:topic_id>/replies/', ReplyListCreateView.as_view(), name='reply-list-create'),
]
