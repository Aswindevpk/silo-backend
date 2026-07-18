from django.contrib import admin
from .models import Channel, Topic, Reply

@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ('id', 'workspace', 'name', 'is_private', 'created_by', 'created_at')
    list_filter = ('is_private', 'workspace')
    search_fields = ('name', 'workspace__name')
    ordering = ('-created_at',)

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('id', 'channel', 'title', 'status', 'replies_count', 'last_reply_at', 'created_by', 'created_at')
    list_filter = ('status', 'channel__workspace')
    search_fields = ('title', 'channel__name')
    ordering = ('-last_reply_at',)

@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = ('id', 'topic', 'created_by', 'created_at')
    search_fields = ('topic__title', 'created_by__email')
    ordering = ('-created_at',)
