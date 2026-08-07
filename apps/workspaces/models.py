import uuid
from datetime import timedelta
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

User = get_user_model()

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class Plan(TimeStampedModel):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    max_members = models.PositiveIntegerField(default=10)
    max_storage_mb = models.PositiveIntegerField(default=5000)
    message_history_days = models.PositiveIntegerField(null=True, blank=True)
    allow_custom_roles = models.BooleanField(default=False)
    stripe_price_id_monthly = models.CharField(max_length=255, blank=True, null=True)
    stripe_price_id_yearly = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)

class Workspace(TimeStampedModel):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='owned_workspaces', null=True)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='workspaces', null=True, blank=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True)
    subscription_status = models.CharField(max_length=50, default='active')

    def __str__(self):
        return self.name

class WorkspaceMember(TimeStampedModel):
    class Role(models.TextChoices):
        OWNER = 'OWNER', 'Owner'
        ADMIN = 'ADMIN', 'Admin'
        MEMBER = 'MEMBER', 'Member'
        GUEST = 'GUEST', 'Guest'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        ACTIVE = 'ACTIVE', 'Active'
        REVOKED = 'REVOKED', 'Revoked'

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='workspace_memberships', null=True, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    
    # Invitation fields
    email = models.EmailField(db_index=True, null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    token = models.UUIDField(unique=True, editable=False, null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name='sent_invitations', null=True, blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(is_default=True),
                name='unique_default_workspace_per_user'
            ),
            models.UniqueConstraint(
                fields=['workspace', 'email'],
                condition=models.Q(status='PENDING'),
                name='unique_pending_invitation_per_workspace'
            ),
            models.UniqueConstraint(
                fields=['workspace', 'user'],
                condition=models.Q(user__isnull=False),
                name='unique_workspace_user'
            )
        ]
        indexes = [
            models.Index(fields=['token', 'status']),
        ]

    def clean(self):
        super().clean()
        if self.email:
            self.email = self.email.lower().strip()
        if not self.user and not self.email:
            from django.core.exceptions import ValidationError
            raise ValidationError("Either user or email must be provided.")

    def save(self, *args, **kwargs):
        if not self.token and self.status == self.Status.PENDING:
            self.token = uuid.uuid4()
            
        self.clean()
        if self.is_default and self.user:
            WorkspaceMember.objects.filter(user=self.user, is_default=True).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return self.status == self.Status.PENDING and not self.is_expired

    def __str__(self):
        if self.user:
            return f"{self.user.email} in {self.workspace.name} ({self.role})"
        return f"Invite to {self.email} for {self.workspace.name} ({self.role})"

def default_invitation_expiry():
    return timezone.now() + timedelta(days=7)
