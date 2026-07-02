from django.db import models
from django.conf import settings
from apps.workspaces.models import Workspace

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
