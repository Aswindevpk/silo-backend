from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Workspace, WorkspaceMember, WorkspaceInvitation, WorkspaceSubscription

User = get_user_model()

class WorkspaceSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)

    class Meta:
        model = Workspace
        fields = ['id', 'name', 'slug', 'created_at', 'created_by_email']
        read_only_fields = ['id', 'created_at']

class NestedUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']

class WorkspaceMemberSerializer(serializers.ModelSerializer):
    user = NestedUserSerializer(read_only=True)

    class Meta:
        model = WorkspaceMember
        fields = ['id', 'user', 'role', 'joined_at']
        read_only_fields = ['id', 'joined_at']

class WorkspaceInvitationSerializer(serializers.ModelSerializer):
    invited_by_email = serializers.EmailField(source='invited_by.email', read_only=True)

    class Meta:
        model = WorkspaceInvitation
        fields = ['id', 'email', 'role', 'token', 'created_at', 'expires_at', 'invited_by_email']
        read_only_fields = ['id', 'token', 'created_at', 'expires_at']

    def validate(self, attrs):
        workspace = self.context.get('workspace')
        email = attrs.get('email')

        # 1. Check if user is already a member
        if WorkspaceMember.objects.filter(workspace=workspace, user__email=email).exists():
            raise serializers.ValidationError("User is already a member of this workspace.")

        # 2. Check if a pending active invitation exists
        inv = WorkspaceInvitation.objects.filter(workspace=workspace, email=email, is_accepted=False).first()
        if inv and not inv.is_expired():
            raise serializers.ValidationError("A pending invitation already exists for this email.")

        return attrs

class WorkspaceSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkspaceSubscription
        fields = ['tier', 'status', 'auto_renew', 'current_period_end']
        read_only_fields = ['tier', 'status', 'current_period_end']
