from django.contrib import admin
from .models import Channel, ChannelMember, Message, MessageReaction

@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ('id', 'workspace', 'name', 'type', 'created_by', 'created_at')
    list_filter = ('type', 'workspace')
    search_fields = ('name', 'workspace__name')
    ordering = ('-created_at',)

@admin.register(ChannelMember)
class ChannelMemberAdmin(admin.ModelAdmin):
    list_display = ('id', 'channel', 'user', 'created_at')
    list_filter = ('channel__workspace',)
    search_fields = ('user__email', 'channel__name')
    ordering = ('-created_at',)

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'channel', 'sender', 'created_at', 'is_deleted')
    list_filter = ('channel__workspace',)
    search_fields = ('content', 'channel__name')
    ordering = ('-created_at',)

@admin.register(MessageReaction)
class MessageReactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'message', 'user', 'emoji', 'created_at')
    search_fields = ('user__email', 'emoji')
    ordering = ('-created_at',)
