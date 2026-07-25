from rest_framework import serializers
from .models import Channel, ChannelMember, Message, MessageReaction

class ChannelSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    target_email = serializers.SerializerMethodField()
    target_user_id = serializers.SerializerMethodField()

    class Meta:
        model = Channel
        fields = ['id', 'workspace', 'name', 'display_name', 'target_email', 'target_user_id', 'type', 'topic', 'created_at', 'created_by']
        read_only_fields = ['id', 'created_at', 'created_by', 'workspace']

    def get_display_name(self, obj):
        if obj.type == 'DIRECT':
            request = self.context.get('request')
            if request and request.user:
                other_member = obj.memberships.exclude(user=request.user).first()
                if other_member:
                    return other_member.user.username
                return f"{request.user.username} (You)"
        return obj.name
        
    def get_target_email(self, obj):
        if obj.type == 'DIRECT':
            request = self.context.get('request')
            if request and request.user:
                other_member = obj.memberships.exclude(user=request.user).first()
                if other_member:
                    return other_member.user.email
                return request.user.email
        return None
        
    def get_target_user_id(self, obj):
        if obj.type == 'DIRECT':
            request = self.context.get('request')
            if request and request.user:
                other_member = obj.memberships.exclude(user=request.user).first()
                if other_member:
                    return str(other_member.user.id)
                return str(request.user.id)
        return None

class MessageReactionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = MessageReaction
        fields = ['id', 'emoji', 'user', 'username', 'created_at']

class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    reactions = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id', 'channel', 'sender', 'content', 'attachments', 'link_previews', 
            'mentions', 'parent_message', 'reply_count', 'latest_reply_at', 
            'is_pinned', 'pinned_by', 'is_edited', 'is_deleted', 'created_at', 'reactions'
        ]
        read_only_fields = ['id', 'created_at', 'reply_count', 'latest_reply_at']

    def get_sender(self, obj):
        return {
            "id": str(obj.sender.id),
            "username": obj.sender.username,
            "email": obj.sender.email
        }
        
    def get_reactions(self, obj):
        reactions = obj.reactions.select_related('user').all()
        # Group reactions by emoji for easier frontend rendering
        grouped = {}
        for rx in reactions:
            if rx.emoji not in grouped:
                grouped[rx.emoji] = {
                    'emoji': rx.emoji,
                    'count': 0,
                    'users': [],
                    'user_ids': []
                }
            grouped[rx.emoji]['count'] += 1
            grouped[rx.emoji]['users'].append(rx.user.username)
            grouped[rx.emoji]['user_ids'].append(str(rx.user.id))
        return list(grouped.values())
