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

class Topic(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        RESOLVED = 'RESOLVED', 'Resolved'
        CLOSED = 'CLOSED', 'Closed'

    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='topics')
    title = models.CharField(max_length=255)
    content = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    
    # Telemetry and Sorting Caches
    last_reply_at = models.DateTimeField(db_index=True, auto_now_add=True)
    replies_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_topics"
    )

    class Meta:
        ordering = ['-last_reply_at']

    def __str__(self):
        return f"{self.title} (Topic in #{self.channel.name})"

class Reply(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='replies')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="replies"
    )

    class Meta:
        verbose_name_plural = "Replies"

    def __str__(self):
        author = self.created_by.email if self.created_by else 'Unknown'
        return f"Reply by {author} on thread '{self.topic.title[:20]}...'"
