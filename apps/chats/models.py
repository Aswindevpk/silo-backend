from django.db import models
from django.conf import settings
from apps.workspaces.models import Workspace, TimeStampedModel
from django.contrib.auth import get_user_model

User = get_user_model()

class Channel(TimeStampedModel):
    class ChannelType(models.TextChoices):
        PUBLIC = 'PUBLIC', 'Public'
        PRIVATE = 'PRIVATE', 'Private'
        DIRECT = 'DIRECT', 'Direct Message'

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='channels')
    name = models.CharField(max_length=80, blank=True, null=True)
    type = models.CharField(max_length=15, choices=ChannelType.choices, default=ChannelType.PUBLIC)
    topic = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_channels')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['workspace', 'name'],
                condition=models.Q(type__in=['PUBLIC', 'PRIVATE']),
                name='unique_public_private_channel_per_workspace'
            )
        ]

class ChannelMember(TimeStampedModel):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='channel_memberships')
    last_read_message_id = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = ('channel', 'user')


class Message(TimeStampedModel):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='messages')
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    content = models.TextField(blank=True, default='')
    attachments = models.JSONField(default=list, blank=True)
    link_previews = models.JSONField(default=list, blank=True)
    mentions = models.JSONField(default=list, blank=True)
    parent_message = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    reply_count = models.PositiveIntegerField(default=0)
    latest_reply_at = models.DateTimeField(null=True, blank=True)
    is_pinned = models.BooleanField(default=False)
    pinned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='pinned_messages')
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['channel', '-id'], name='idx_channel_msg_cursor'),
            models.Index(fields=['parent_message', '-id'], name='idx_thread_msg_cursor'),
            models.Index(fields=['channel', 'is_pinned'], name='idx_pinned_channel_msgs'),
        ]


class MessageReaction(TimeStampedModel):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='message_reactions')
    emoji = models.CharField(max_length=50)

    class Meta:
        unique_together = ('message', 'user', 'emoji')
