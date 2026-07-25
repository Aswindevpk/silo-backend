from django.shortcuts import get_object_or_404
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.workspaces.models import Workspace, WorkspaceMember
from .models import Channel, Message
from .serializers import ChannelSerializer, MessageSerializer

class ChannelListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, workspace_slug):
        workspace = get_object_or_404(Workspace, slug=workspace_slug)
        member = WorkspaceMember.objects.filter(workspace=workspace, user=request.user).first()
        if not member:
            return Response({"detail": "You are not a member of this workspace."}, status=status.HTTP_403_FORBIDDEN)

        channels = Channel.objects.filter(workspace=workspace).exclude(type=Channel.ChannelType.DIRECT)
        accessible_channels = []
        for ch in channels:
            if ch.type == Channel.ChannelType.PUBLIC:
                accessible_channels.append(ch)
            else:
                if ch.memberships.filter(user=request.user).exists():
                    accessible_channels.append(ch)

        serializer = ChannelSerializer(accessible_channels, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, workspace_slug):
        workspace = get_object_or_404(Workspace, slug=workspace_slug)
        member = WorkspaceMember.objects.filter(workspace=workspace, user=request.user).first()
        if not member:
            return Response({"detail": "You are not a member of this workspace."}, status=status.HTTP_403_FORBIDDEN)

        serializer = ChannelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        channel = serializer.save(workspace=workspace, created_by=request.user)
        
        from .models import ChannelMember
        ChannelMember.objects.create(channel=channel, user=request.user)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

class MessageListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, channel_id):
        channel = get_object_or_404(Channel, id=channel_id)
        
        messages = channel.messages.all().order_by('created_at')
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

from django.contrib.auth import get_user_model
User = get_user_model()

class DirectMessageListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, workspace_slug):
        workspace = get_object_or_404(Workspace, slug=workspace_slug)
        if not WorkspaceMember.objects.filter(workspace=workspace, user=request.user).exists():
            return Response({"detail": "You are not a member of this workspace."}, status=status.HTTP_403_FORBIDDEN)
            
        dm_channels = Channel.objects.filter(
            workspace=workspace, 
            type=Channel.ChannelType.DIRECT,
            memberships__user=request.user
        )
        
        serializer = ChannelSerializer(dm_channels, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

class DirectMessageChannelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, workspace_slug, target_email):
        workspace = get_object_or_404(Workspace, slug=workspace_slug)
        
        # Verify current user is in workspace
        if not WorkspaceMember.objects.filter(workspace=workspace, user=request.user).exists():
            return Response({"detail": "You are not a member of this workspace."}, status=status.HTTP_403_FORBIDDEN)
            
        target_user = get_object_or_404(User, email=target_email)
        
        # Verify target user is in workspace
        if not WorkspaceMember.objects.filter(workspace=workspace, user=target_user).exists():
            return Response({"detail": "Target user is not a member of this workspace."}, status=status.HTTP_404_NOT_FOUND)
            
        from django.db.models import Count, Q
        from .models import ChannelMember
        
        if request.user.id == target_user.id:
            # Self-chat needs exactly 1 member
            dm_channels = Channel.objects.filter(
                workspace=workspace, 
                type=Channel.ChannelType.DIRECT
            ).annotate(
                member_count=Count('memberships')
            ).filter(
                member_count=1,
                memberships__user=request.user
            )
            
            channel = dm_channels.first()
            if not channel:
                channel = Channel.objects.create(workspace=workspace, type=Channel.ChannelType.DIRECT, created_by=request.user)
                ChannelMember.objects.create(channel=channel, user=request.user)
        else:
            # Find existing DM channel with exactly these two users
            dm_channels = Channel.objects.filter(
                workspace=workspace, 
                type=Channel.ChannelType.DIRECT
            ).annotate(
                member_count=Count('memberships')
            ).filter(
                member_count=2,
                memberships__user=request.user
            ).filter(
                memberships__user=target_user
            )
            
            channel = dm_channels.first()
            if not channel:
                channel = Channel.objects.create(workspace=workspace, type=Channel.ChannelType.DIRECT, created_by=request.user)
                ChannelMember.objects.create(channel=channel, user=request.user)
                ChannelMember.objects.create(channel=channel, user=target_user)
                
        serializer = ChannelSerializer(channel, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


