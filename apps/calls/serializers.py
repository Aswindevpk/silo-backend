from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import CallSession

User = get_user_model()

class CallSessionSerializer(serializers.ModelSerializer):
    caller_email = serializers.EmailField(source='caller.email', read_only=True)
    receiver_email = serializers.EmailField(source='receiver.email', read_only=True)
    workspace_name = serializers.CharField(source='workspace.name', read_only=True)

    class Meta:
        model = CallSession
        fields = [
            'id', 'workspace_name', 'caller_email', 'receiver_email', 
            'status', 'started_at', 'ended_at', 'duration_seconds'
        ]
        read_only_fields = ['id', 'started_at', 'ended_at', 'duration_seconds']
