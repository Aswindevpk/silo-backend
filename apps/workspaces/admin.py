from django.contrib import admin
from .models import Workspace, WorkspaceMember, WorkspaceInvitation, Plan

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'slug', 'price_monthly', 'max_members', 'is_active')
    search_fields = ('name', 'slug')

@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'slug', 'owner', 'plan', 'created_at')
    search_fields = ('name', 'slug')
    ordering = ('-created_at',)

@admin.register(WorkspaceMember)
class WorkspaceMemberAdmin(admin.ModelAdmin):
    list_display = ('id', 'workspace', 'user', 'role', 'created_at')
    list_filter = ('role', 'workspace')
    search_fields = ('user__email', 'workspace__name')
    ordering = ('-created_at',)

@admin.register(WorkspaceInvitation)
class WorkspaceInvitationAdmin(admin.ModelAdmin):
    list_display = ('id', 'workspace', 'email', 'invited_by', 'role', 'is_accepted', 'expires_at')
    list_filter = ('is_accepted', 'workspace')
    search_fields = ('email', 'workspace__name')
    ordering = ('-created_at',)
