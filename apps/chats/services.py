from asgiref.sync import sync_to_async
from django.core.exceptions import ObjectDoesNotExist
from .models import Channel, Message, MessageReaction
from .serializers import MessageSerializer

class ChatService:
    @staticmethod
    @sync_to_async
    def create_message(channel_id, user, content, parent_id=None, attachments=None, client_msg_id=None):
        try:
            channel = Channel.objects.get(id=channel_id)
            parent = None
            if parent_id:
                parent = Message.objects.filter(id=parent_id).first()
                if parent and parent.channel_id != channel.id:
                    parent = None
            
            message = Message.objects.create(
                workspace_id=channel.workspace_id,
                channel=channel,
                sender=user,
                content=content,
                parent_message=parent,
                attachments=attachments or []
            )
            
            if parent:
                parent.reply_count = Message.objects.filter(parent_message=parent).count()
                parent.latest_reply_at = message.created_at
                parent.save(update_fields=['reply_count', 'latest_reply_at'])
                
            serializer = MessageSerializer(message)
            data = serializer.data
            if client_msg_id:
                data['client_msg_id'] = client_msg_id
            return data
        except ObjectDoesNotExist:
            return None

    @staticmethod
    @sync_to_async
    def toggle_reaction(channel_id, user, message_id, emoji):
        try:
            message = Message.objects.get(id=message_id, channel_id=channel_id)
            reaction, created = MessageReaction.objects.get_or_create(
                message=message,
                user=user,
                emoji=emoji
            )
            if not created:
                reaction.delete()
                
            serializer = MessageSerializer(message)
            return serializer.data
        except ObjectDoesNotExist:
            return None

    @staticmethod
    @sync_to_async
    def edit_message(channel_id, user, message_id, content):
        try:
            message = Message.objects.get(id=message_id, channel_id=channel_id, sender=user, is_deleted=False)
            message.content = content
            message.is_edited = True
            message.save(update_fields=['content', 'is_edited', 'updated_at'])
            
            serializer = MessageSerializer(message)
            return serializer.data
        except ObjectDoesNotExist:
            return None

    @staticmethod
    @sync_to_async
    def delete_message(channel_id, user, message_id):
        try:
            message = Message.objects.get(id=message_id, channel_id=channel_id, sender=user, is_deleted=False)
            message.is_deleted = True
            message.content = "This message was deleted."
            message.attachments = []
            message.save(update_fields=['is_deleted', 'content', 'attachments', 'updated_at'])
            
            serializer = MessageSerializer(message)
            return serializer.data
        except ObjectDoesNotExist:
            return None

    @staticmethod
    @sync_to_async
    def toggle_pin(channel_id, user, message_id):
        try:
            message = Message.objects.get(id=message_id, channel_id=channel_id, is_deleted=False)
            message.is_pinned = not message.is_pinned
            message.pinned_by = user if message.is_pinned else None
            message.save(update_fields=['is_pinned', 'pinned_by', 'updated_at'])
            
            serializer = MessageSerializer(message)
            return serializer.data
        except ObjectDoesNotExist:
            return None
