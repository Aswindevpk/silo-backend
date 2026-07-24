from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Channel, ChannelMessage, DirectMessage

User = get_user_model()

class ChannelSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)

    class Meta:
        model = Channel
        fields = ['id', 'name', 'description', 'is_private', 'created_at', 'created_by_email']
        read_only_fields = ['id', 'created_at']

class ChannelMessageSerializer(serializers.ModelSerializer):
    sender_email = serializers.EmailField(source='sender.email', read_only=True)

    class Meta:
        model = ChannelMessage
        fields = ['id', 'channel', 'sender_email', 'content', 'created_at']
        read_only_fields = ['id', 'created_at']

class DirectMessageSerializer(serializers.ModelSerializer):
    sender_email = serializers.EmailField(source='sender.email', read_only=True)
    receiver_email = serializers.EmailField(source='receiver.email', read_only=True)

    class Meta:
        model = DirectMessage
        fields = ['id', 'sender_email', 'receiver_email', 'content', 'created_at']
        read_only_fields = ['id', 'created_at']
