from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Channel, Topic, Reply

User = get_user_model()

class ChannelSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)

    class Meta:
        model = Channel
        fields = ['id', 'name', 'description', 'is_private', 'created_at', 'created_by_email']
        read_only_fields = ['id', 'created_at']

class TopicSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    replies_count = serializers.IntegerField(read_only=True)
    last_reply_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Topic
        fields = ['id', 'title', 'content', 'status', 'last_reply_at', 'replies_count', 'created_at', 'created_by_email']
        read_only_fields = ['id', 'created_at', 'last_reply_at', 'replies_count']

class ReplySerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)

    class Meta:
        model = Reply
        fields = ['id', 'content', 'created_at', 'created_by_email']
        read_only_fields = ['id', 'created_at']
