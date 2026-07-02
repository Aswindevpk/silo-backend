from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.workspaces.models import Workspace, WorkspaceMember
from .models import Channel, Topic, Reply
from .serializers import ChannelSerializer, TopicSerializer, ReplySerializer

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

class TopicListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, channel_id):
        channel = get_object_or_404(Channel, id=channel_id)
        if not check_channel_access(request.user, channel):
            return Response({"detail": "Access denied to this channel."}, status=status.HTTP_403_FORBIDDEN)

        topics = channel.topics.all()
        serializer = TopicSerializer(topics, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, channel_id):
        channel = get_object_or_404(Channel, id=channel_id)
        if not check_channel_access(request.user, channel):
            return Response({"detail": "Access denied to this channel."}, status=status.HTTP_403_FORBIDDEN)

        serializer = TopicSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        topic = serializer.save(channel=channel, created_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class ReplyListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, topic_id):
        topic = get_object_or_404(Topic, id=topic_id)
        if not check_channel_access(request.user, topic.channel):
            return Response({"detail": "Access denied to this channel."}, status=status.HTTP_403_FORBIDDEN)

        replies = topic.replies.all().order_by('created_at')
        serializer = ReplySerializer(replies, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, topic_id):
        topic = get_object_or_404(Topic, id=topic_id)
        if not check_channel_access(request.user, topic.channel):
            return Response({"detail": "Access denied to this channel."}, status=status.HTTP_403_FORBIDDEN)

        serializer = ReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            reply = serializer.save(topic=topic, created_by=request.user)
            topic.last_reply_at = timezone.now()
            topic.replies_count += 1
            topic.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)
