import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from django.utils import timezone
from django.db import transaction

User = get_user_model()

@database_sync_to_async
def get_user_from_token(token_string):
    try:
        access_token = AccessToken(token_string.strip())
        user_id = access_token.payload.get('user_id')
        user = User.objects.get(id=user_id)
        if user.is_active:
            return user
    except Exception:
        pass
    return None

@database_sync_to_async
def verify_channel_access(user, channel_id):
    try:
        from apps.chats.models import Channel
        from apps.workspaces.models import WorkspaceMember
        channel = Channel.objects.get(id=channel_id)
        member = WorkspaceMember.objects.filter(workspace=channel.workspace, user=user).first()
        if not member:
            return False
        if channel.is_private:
            if not channel.allowed_members.filter(id=member.id).exists():
                return False
        return True
    except Exception:
        return False

@database_sync_to_async
def save_reply(user, topic_id, content):
    try:
        from apps.chats.models import Topic, Reply
        topic = Topic.objects.get(id=topic_id)
        with transaction.atomic():
            reply = Reply.objects.create(topic=topic, content=content, created_by=user)
            topic.last_reply_at = timezone.now()
            topic.replies_count += 1
            topic.save()
        return {
            "id": reply.id,
            "topic_id": topic.id,
            "content": reply.content,
            "created_at": reply.created_at.isoformat(),
            "created_by_email": user.email
        }
    except Exception:
        return None

class UserConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.authenticated = False
        self.user = None
        self.current_channel_group = None
        self.auth_timeout_task = asyncio.create_task(self.auth_timeout_check())
        await self.send(text_data=json.dumps({
            "message": "Connection established. Please authenticate by sending your access token."
        }))

    async def auth_timeout_check(self):
        try:
            await asyncio.sleep(10)
            if not self.authenticated:
                await self.send(text_data=json.dumps({
                    "error": "Authentication timeout. Connection closing."
                }))
                await self.close(code=4408)
        except asyncio.CancelledError:
            pass

    async def disconnect(self, close_code):
        if hasattr(self, 'auth_timeout_task'):
            self.auth_timeout_task.cancel()
        
        # Discard from user and channel groups
        if self.user:
            await self.channel_layer.group_discard(f"user_{self.user.id}", self.channel_name)
        if self.current_channel_group:
            await self.channel_layer.group_discard(self.current_channel_group, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            if not self.authenticated:
                await self.send(text_data=json.dumps({
                    "error": "Invalid JSON. Connection closing."
                }))
                await self.close(code=4401)
                return
            data = {}

        if not self.authenticated:
            # Handle Authentication
            if data.get("type") == "auth" and "token" in data:
                token = data["token"]
                user = await get_user_from_token(token)
                if user:
                    self.authenticated = True
                    self.user = user
                    if hasattr(self, 'auth_timeout_task'):
                        self.auth_timeout_task.cancel()
                    
                    # Join user-specific signaling group
                    await self.channel_layer.group_add(f"user_{self.user.id}", self.channel_name)
                    
                    await self.send(text_data=json.dumps({
                        "message": f"Authentication successful! Welcome {user.email}."
                    }))
                else:
                    await self.send(text_data=json.dumps({
                        "error": "Invalid token. Connection closing."
                    }))
                    await self.close(code=4401)
            else:
                await self.send(text_data=json.dumps({
                    "error": "Authentication required. Connection closing."
                }))
                await self.close(code=4401)
        else:
            action_type = data.get("type")

            # Handle Channel Subscription
            if action_type == "subscribe":
                channel_id = data.get("channel_id")
                if not channel_id:
                    await self.send(text_data=json.dumps({"error": "channel_id is required."}))
                    return

                has_access = await verify_channel_access(self.user, channel_id)
                if has_access:
                    # Discard from previous channel group
                    if self.current_channel_group:
                        await self.channel_layer.group_discard(self.current_channel_group, self.channel_name)
                    
                    self.current_channel_group = f"channel_{channel_id}"
                    await self.channel_layer.group_add(self.current_channel_group, self.channel_name)
                    await self.send(text_data=json.dumps({
                        "status": "success",
                        "message": f"Subscribed to channel {channel_id}"
                    }))
                else:
                    await self.send(text_data=json.dumps({"error": "Access denied to this channel."}))

            # Handle Posting a Reply (instantly broadcasted to all channel subscribers)
            elif action_type == "new_reply":
                topic_id = data.get("topic_id")
                content = data.get("content")
                if not topic_id or not content:
                    await self.send(text_data=json.dumps({"error": "topic_id and content are required."}))
                    return

                reply_data = await save_reply(self.user, topic_id, content)
                if reply_data and self.current_channel_group:
                    await self.channel_layer.group_send(
                        self.current_channel_group,
                        {
                            "type": "channel_message",
                            "message": reply_data
                        }
                    )
                else:
                    await self.send(text_data=json.dumps({"error": "Failed to save reply or not subscribed."}))

            # Handle P2P Call Signaling (relay directly to recipient user group)
            elif action_type == "call_signal":
                receiver_id = data.get("receiver_id")
                if not receiver_id:
                    await self.send(text_data=json.dumps({"error": "receiver_id is required."}))
                    return

                await self.channel_layer.group_send(
                    f"user_{receiver_id}",
                    {
                        "type": "user_signal",
                        "sender_id": self.user.id,
                        "signal_data": data
                    }
                )

    # Receive message from channel group
    async def channel_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "new_reply_broadcast",
            "data": event["message"]
        }))

    # Receive WebRTC signaling message
    async def user_signal(self, event):
        await self.send(text_data=json.dumps({
            "type": "call_signal_relay",
            "sender_id": event["sender_id"],
            "signal_data": event["signal_data"]
        }))
