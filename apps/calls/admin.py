from django.contrib import admin
from .models import CallSession

@admin.register(CallSession)
class CallSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'workspace', 'caller', 'receiver', 'status', 'started_at', 'ended_at', 'duration_seconds')
    list_filter = ('status', 'workspace')
    search_fields = ('caller__email', 'receiver__email', 'workspace__name')
    ordering = ('-started_at',)
