from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Workspace, WorkspaceMember, WorkspaceInvitation, Plan

User = get_user_model()

class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ['id', 'name', 'slug', 'price_monthly', 'max_members', 'max_storage_mb']

class WorkspaceSerializer(serializers.ModelSerializer):
    owner_email = serializers.EmailField(source='owner.email', read_only=True)
    is_default = serializers.SerializerMethodField()
    plan = PlanSerializer(read_only=True)

    class Meta:
        model = Workspace
        fields = ['id', 'name', 'slug', 'created_at', 'owner_email', 'is_default', 'plan', 'subscription_status']
        read_only_fields = ['id', 'created_at', 'plan', 'subscription_status']

    def get_is_default(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        member = WorkspaceMember.objects.filter(workspace=obj, user=request.user).first()
        return member.is_default if member else False

class NestedUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']

class WorkspaceMemberSerializer(serializers.ModelSerializer):
    user = NestedUserSerializer(read_only=True)

    class Meta:
        model = WorkspaceMember
        fields = ['id', 'user', 'role', 'created_at']
        read_only_fields = ['id', 'created_at']

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
