from django.contrib import admin
from .models import Channel, ChannelMessage, DirectMessage

@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ('id', 'workspace', 'name', 'is_private', 'created_by', 'created_at')
    list_filter = ('is_private', 'workspace')
    search_fields = ('name', 'workspace__name')
    ordering = ('-created_at',)

@admin.register(ChannelMessage)
class ChannelMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'channel', 'sender', 'created_at')
    list_filter = ('channel__workspace',)
    search_fields = ('content', 'channel__name')
    ordering = ('-created_at',)

@admin.register(DirectMessage)
class DirectMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'workspace', 'sender', 'receiver', 'created_at')
    search_fields = ('sender__email', 'receiver__email', 'content')
    ordering = ('-created_at',)
