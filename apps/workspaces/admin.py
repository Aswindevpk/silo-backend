from django.contrib import admin
from .models import Workspace, WorkspaceMember, WorkspaceInvitation, WorkspaceSubscription

@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'slug', 'created_by', 'created_at')
    search_fields = ('name', 'slug')
    ordering = ('-created_at',)

@admin.register(WorkspaceMember)
class WorkspaceMemberAdmin(admin.ModelAdmin):
    list_display = ('id', 'workspace', 'user', 'role', 'joined_at')
    list_filter = ('role', 'workspace')
    search_fields = ('user__email', 'workspace__name')
    ordering = ('-joined_at',)

@admin.register(WorkspaceInvitation)
class WorkspaceInvitationAdmin(admin.ModelAdmin):
    list_display = ('id', 'workspace', 'email', 'invited_by', 'role', 'is_accepted', 'expires_at')
    list_filter = ('is_accepted', 'workspace')
    search_fields = ('email', 'workspace__name')
    ordering = ('-created_at',)

@admin.register(WorkspaceSubscription)
class WorkspaceSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'workspace', 'tier', 'status', 'auto_renew', 'current_period_end')
    list_filter = ('tier', 'status', 'auto_renew')
    search_fields = ('workspace__name', 'stripe_subscription_id')
    ordering = ('-created_at',)
