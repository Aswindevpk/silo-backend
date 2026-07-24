from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.workspaces.models import Workspace, WorkspaceMember
from .models import Channel, ChannelMessage, DirectMessage
from .serializers import ChannelSerializer, ChannelMessageSerializer, DirectMessageSerializer

def check_channel_access(user, channel):
    member = WorkspaceMember.objects.filter(workspace=channel.workspace, user=user).first()
    if not member:
        return False
    if channel.is_private:
        if not channel.allowed_members.filter(id=member.id).exists():
            return False
    return True

class ChannelListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, workspace_slug):
        workspace = get_object_or_404(Workspace, slug=workspace_slug)
        member = WorkspaceMember.objects.filter(workspace=workspace, user=request.user).first()
        if not member:
            return Response({"detail": "You are not a member of this workspace."}, status=status.HTTP_403_FORBIDDEN)

        channels = Channel.objects.filter(workspace=workspace)
        accessible_channels = []
        for ch in channels:
            if not ch.is_private or ch.allowed_members.filter(id=member.id).exists():
                accessible_channels.append(ch)

        serializer = ChannelSerializer(accessible_channels, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, workspace_slug):
        workspace = get_object_or_404(Workspace, slug=workspace_slug)
        member = WorkspaceMember.objects.filter(workspace=workspace, user=request.user).first()
        if not member:
            return Response({"detail": "You are not a member of this workspace."}, status=status.HTTP_403_FORBIDDEN)

        serializer = ChannelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        channel = serializer.save(workspace=workspace, created_by=request.user)

        if channel.is_private:
            channel.allowed_members.add(member)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

class ChannelMessageListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, channel_id):
        channel = get_object_or_404(Channel, id=channel_id)
        if not check_channel_access(request.user, channel):
            return Response({"detail": "Access denied to this channel."}, status=status.HTTP_403_FORBIDDEN)

        messages = channel.messages.all().order_by('created_at')
        serializer = ChannelMessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class DirectMessageListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, workspace_slug, target_email):
        workspace = get_object_or_404(Workspace, slug=workspace_slug)
        member = WorkspaceMember.objects.filter(workspace=workspace, user=request.user).first()
        if not member:
            return Response({"detail": "You are not a member of this workspace."}, status=status.HTTP_403_FORBIDDEN)

        from django.contrib.auth import get_user_model
        from django.db.models import Q
        User = get_user_model()
        
        target_user = get_object_or_404(User, email=target_email)
        
        messages = DirectMessage.objects.filter(
            workspace=workspace
        ).filter(
            Q(sender=request.user, receiver=target_user) | 
            Q(sender=target_user, receiver=request.user)
        ).order_by('created_at')

        serializer = DirectMessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
