import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from apps.chats.models import Message, Channel, MessageReaction
from apps.chats.serializers import MessageSerializer
from apps.workspaces.models import WorkspaceMember

User = get_user_model()

import redis
from django.conf import settings
redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)
PRESENCE_KEY = "silo_online_users"


class GlobalConsumer(AsyncJsonWebsocketConsumer):
    """
    Unified Multiplexed WebSocket Consumer handling Chat, Notifications,
    Presence, and WebRTC Audio/Video Signaling.
    """

    async def connect(self):
        self.user = AnonymousUser()

        # Strictly read JWT token from cookies for security
        token = None
        headers = dict(self.scope.get("headers", []))
        if b"cookie" in headers:
            cookies = headers[b"cookie"].decode("utf-8").split(";")
            for cookie in cookies:
                if "access=" in cookie.strip():
                    token = cookie.split("access=")[1].strip()
                    break

        if token:
            try:
                access_token = AccessToken(token)
                user_id = access_token.payload.get("user_id")
                user = await database_sync_to_async(User.objects.get)(id=user_id)
                if user.is_active:
                    self.user = user
            except Exception:
                pass

        if not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.user_group = f"user_{self.user.id}"
        await self.channel_layer.group_add(self.user_group, self.channel_name)
        await self.accept()

        # Broadcast online presence state
        redis_client.sadd(PRESENCE_KEY, str(self.user.id))
        await self.broadcast_presence("online")

    async def disconnect(self, close_code):
        if hasattr(self, "user_group"):
            redis_client.srem(PRESENCE_KEY, str(self.user.id))
            await self.broadcast_presence("offline")
            await self.channel_layer.group_discard(self.user_group, self.channel_name)

    async def receive_json(self, content):
        """Multiplexing Event Router"""
        event_type = content.get("type")
        workspace_id = content.get("workspace_id")
        channel_id = content.get("channel_id")
        payload = content.get("payload", {})

        # 1. Room Subscription Handlers
        if event_type == "room.subscribe":
            await self.channel_layer.group_add(
                f"channel_{channel_id}", self.channel_name
            )
            return

        elif event_type == "room.unsubscribe":
            await self.channel_layer.group_discard(
                f"channel_{channel_id}", self.channel_name
            )
            return

        # 2. Messaging Handler
        elif event_type == "chat.send_message":
            msg_obj = await self.save_message(
                workspace_id=workspace_id,
                channel_id=channel_id,
                content=payload.get("content"),
                attachments=payload.get("attachments", []),
                client_msg_id=payload.get("client_msg_id"),
                mentions=payload.get("mentions", []),
                link_previews=payload.get("link_previews", []),
                parent_message_id=payload.get("parent_message_id"),
            )

            # Broadcast to Redis group
            await self.channel_layer.group_send(
                f"channel_{channel_id}",
                {
                    "type": "chat_message_broadcast",
                    "workspace_id": workspace_id,
                    "channel_id": channel_id,
                    "payload": msg_obj,
                },
            )

        elif event_type == "chat.message_reaction":
            message_id = payload.get("message_id")
            emoji = payload.get("emoji")
            msg_obj = await self.toggle_reaction(channel_id, message_id, emoji)
            if msg_obj:
                await self.channel_layer.group_send(
                    f"channel_{channel_id}",
                    {
                        "type": "chat_reaction_broadcast",
                        "workspace_id": workspace_id,
                        "channel_id": channel_id,
                        "payload": msg_obj,
                    },
                )

        elif event_type == "chat.message_edit":
            message_id = payload.get("message_id")
            content = payload.get("content")
            msg_obj = await self.edit_message(channel_id, message_id, content)
            if msg_obj:
                await self.channel_layer.group_send(
                    f"channel_{channel_id}",
                    {
                        "type": "chat_edit_broadcast",
                        "workspace_id": workspace_id,
                        "channel_id": channel_id,
                        "payload": msg_obj,
                    },
                )

        elif event_type == "chat.message_delete":
            message_id = payload.get("message_id")
            msg_obj = await self.delete_message(channel_id, message_id)
            if msg_obj:
                await self.channel_layer.group_send(
                    f"channel_{channel_id}",
                    {
                        "type": "chat_delete_broadcast",
                        "workspace_id": workspace_id,
                        "channel_id": channel_id,
                        "payload": msg_obj,
                    },
                )

        elif event_type == "chat.message_pin":
            message_id = payload.get("message_id")
            msg_obj = await self.toggle_pin(channel_id, message_id)
            if msg_obj:
                await self.channel_layer.group_send(
                    f"channel_{channel_id}",
                    {
                        "type": "chat_pin_broadcast",
                        "workspace_id": workspace_id,
                        "channel_id": channel_id,
                        "payload": msg_obj,
                    },
                )

        # 3. WebRTC Call Signaling Handler
        elif event_type in [
            "webrtc.call_offer",
            "webrtc.call_answer",
            "webrtc.ice_candidate",
        ]:
            await self.channel_layer.group_send(
                f"channel_{channel_id}",
                {
                    "type": "webrtc_relay",
                    "event_type": event_type,
                    "channel_id": channel_id,
                    "payload": payload,
                    "sender_id": str(self.user.id),
                },
            )

    # --- Group Broadcast Relay Functions ---

    async def chat_message_broadcast(self, event):
        """Relays chat payloads down to WebSocket clients."""
        await self.send_json(
            {
                "type": "chat.message_received",
                "workspace_id": event["workspace_id"],
                "channel_id": event["channel_id"],
                "payload": event["payload"],
            }
        )

    async def chat_reaction_broadcast(self, event):
        await self.send_json(
            {
                "type": "chat.reaction_updated",
                "workspace_id": event["workspace_id"],
                "channel_id": event["channel_id"],
                "payload": event["payload"],
            }
        )

    async def chat_edit_broadcast(self, event):
        await self.send_json(
            {
                "type": "chat.message_edited",
                "workspace_id": event["workspace_id"],
                "channel_id": event["channel_id"],
                "payload": event["payload"],
            }
        )

    async def chat_delete_broadcast(self, event):
        await self.send_json(
            {
                "type": "chat.message_deleted",
                "workspace_id": event["workspace_id"],
                "channel_id": event["channel_id"],
                "payload": event["payload"],
            }
        )

    async def chat_pin_broadcast(self, event):
        await self.send_json(
            {
                "type": "chat.message_pinned",
                "workspace_id": event["workspace_id"],
                "channel_id": event["channel_id"],
                "payload": event["payload"],
            }
        )

    async def webrtc_relay(self, event):
        """Relays WebRTC signals to channel peers (excluding sender)."""
        if event["sender_id"] != str(self.user.id):
            await self.send_json(
                {
                    "type": event["event_type"],
                    "channel_id": event["channel_id"],
                    "payload": event["payload"],
                }
            )

    async def broadcast_presence(self, status):
        """Notifies user groups of status updates."""
        await self.send_json(
            {
                "type": "presence.status_change",
                "payload": {"user_id": str(self.user.id), "status": status},
            }
        )

    @database_sync_to_async
    def save_message(
        self, workspace_id, channel_id, content, attachments, client_msg_id, 
        mentions=[], link_previews=[], parent_message_id=None
    ):
        msg = Message.objects.create(
            workspace_id=workspace_id,
            channel_id=channel_id,
            sender=self.user,
            content=content,
            attachments=attachments,
            mentions=mentions,
            link_previews=link_previews,
            parent_message_id=parent_message_id
        )
        
        if parent_message_id:
            parent = Message.objects.get(id=parent_message_id)
            parent.reply_count += 1
            parent.latest_reply_at = msg.created_at
            parent.save(update_fields=['reply_count', 'latest_reply_at'])
            
        return {
            "id": str(msg.id),
            "channel": channel_id,
            "client_msg_id": client_msg_id,
            "sender": {"id": str(self.user.id), "username": self.user.username, "email": self.user.email},
            "content": msg.content,
            "attachments": msg.attachments,
            "mentions": msg.mentions,
            "link_previews": msg.link_previews,
            "parent_message": parent_message_id,
            "reply_count": msg.reply_count,
            "latest_reply_at": msg.latest_reply_at.isoformat() if msg.latest_reply_at else None,
            "is_pinned": msg.is_pinned,
            "is_edited": msg.is_edited,
            "is_deleted": msg.is_deleted,
            "reactions": [],
            "created_at": msg.created_at.isoformat(),
        }

    @database_sync_to_async
    def toggle_reaction(self, channel_id, message_id, emoji):
        try:
            message = Message.objects.get(id=message_id, channel_id=channel_id)
            existing = MessageReaction.objects.filter(message=message, user=self.user, emoji=emoji).first()
            if existing:
                existing.delete()
            else:
                MessageReaction.objects.create(message=message, user=self.user, emoji=emoji)
            return self._serialize_message(message)
        except Message.DoesNotExist:
            return None

    @database_sync_to_async
    def edit_message(self, channel_id, message_id, content):
        try:
            msg = Message.objects.get(id=message_id, channel_id=channel_id, sender=self.user)
            msg.content = content
            msg.is_edited = True
            msg.save()
            return self._serialize_message(msg)
        except Message.DoesNotExist:
            return None

    @database_sync_to_async
    def delete_message(self, channel_id, message_id):
        try:
            msg = Message.objects.get(id=message_id, channel_id=channel_id, sender=self.user)
            msg.is_deleted = True
            msg.content = "This message was deleted."
            msg.attachments = []
            msg.link_previews = []
            msg.save()
            return self._serialize_message(msg)
        except Message.DoesNotExist:
            return None

    @database_sync_to_async
    def toggle_pin(self, channel_id, message_id):
        try:
            msg = Message.objects.get(id=message_id, channel_id=channel_id)
            if msg.is_pinned:
                msg.is_pinned = False
                msg.pinned_by = None
            else:
                msg.is_pinned = True
                msg.pinned_by = self.user
            msg.save()
            return self._serialize_message(msg)
        except Message.DoesNotExist:
            return None

    def _serialize_message(self, msg):
        return MessageSerializer(msg).data
