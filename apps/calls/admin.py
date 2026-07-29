from django.contrib import admin
from .models import CallSession, ChannelSFUCall, SFUCallParticipant

@admin.register(CallSession)
class CallSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'workspace', 'caller', 'receiver', 'status', 'started_at', 'ended_at', 'duration_seconds')
    list_filter = ('status', 'workspace')
    search_fields = ('caller__email', 'receiver__email', 'workspace__name')
    ordering = ('-started_at',)

class SFUCallParticipantInline(admin.TabularInline):
    model = SFUCallParticipant
    extra = 0
    readonly_fields = ('joined_at', 'left_at')

@admin.register(ChannelSFUCall)
class ChannelSFUCallAdmin(admin.ModelAdmin):
    list_display = ('id', 'channel', 'is_active', 'started_by', 'created_at', 'ended_at')
    list_filter = ('is_active', 'channel')
    search_fields = ('channel__name', 'started_by__email')
    ordering = ('-created_at',)
    inlines = [SFUCallParticipantInline]

@admin.register(SFUCallParticipant)
class SFUCallParticipantAdmin(admin.ModelAdmin):
    list_display = ('id', 'call', 'user', 'is_muted', 'joined_at', 'left_at')
    list_filter = ('is_muted', 'call__channel')
    search_fields = ('user__email', 'user__username')
    ordering = ('-joined_at',)
