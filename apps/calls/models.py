from django.db import models
from django.conf import settings
from apps.workspaces.models import Workspace, TimeStampedModel
from apps.chats.models import Channel, Message
class CallSession(models.Model):
    class Status(models.TextChoices):
        RINGING = 'RINGING', 'Ringing'
        CONNECTED = 'CONNECTED', 'Connected'
        MISSED = 'MISSED', 'Missed'
        REJECTED = 'REJECTED', 'Rejected'
        COMPLETED = 'COMPLETED', 'Completed'

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='calls')
    caller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="initiated_calls"
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="received_calls"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RINGING)
    
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        caller_email = self.caller.email if self.caller else "Anonymous"
        receiver_email = self.receiver.email if self.receiver else "Anonymous"
        return f"Call in {self.workspace.name}: {caller_email} -> {receiver_email} ({self.status})"

class ChannelSFUCall(TimeStampedModel):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='sfu_calls')
    message = models.OneToOneField(Message, on_delete=models.SET_NULL, null=True, blank=True, related_name='sfu_call')
    is_active = models.BooleanField(default=True)
    started_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"SFU Call in {self.channel.name or self.channel.id} (Active: {self.is_active})"

class SFUCallParticipant(TimeStampedModel):
    call = models.ForeignKey(ChannelSFUCall, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    cloudflare_session_id = models.CharField(max_length=255, blank=True, null=True)
    is_muted = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} in call {self.call.id}"
