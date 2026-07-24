from django.db import models
from django.conf import settings
from apps.workspaces.models import Workspace, WorkspaceMember

class Channel(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='channels')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')
    is_private = models.BooleanField(default=False)
    
    # Private Channel allowed workspace members
    allowed_members = models.ManyToManyField(
        WorkspaceMember,
        blank=True,
        related_name='allowed_private_channels'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_channels"
    )

    class Meta:
        unique_together = ('workspace', 'name')

    def __str__(self):
        return f"#{self.name} in {self.workspace.name}"

class ChannelMessage(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="channel_messages"
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        sender_email = self.sender.email if self.sender else 'Unknown'
        return f"Message by {sender_email} in #{self.channel.name}"

class DirectMessage(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='direct_messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_direct_messages')
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_direct_messages')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"DM from {self.sender.email} to {self.receiver.email} in {self.workspace.name}"
