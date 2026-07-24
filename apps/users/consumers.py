import json
import logging
import redis
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from apps.workspaces.models import WorkspaceMember
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()

def get_redis_client():
    try:
        hosts = settings.CHANNEL_LAYERS["default"]["CONFIG"]["hosts"]
        host = hosts[0]
        if isinstance(host, str):
            return redis.Redis.from_url(host, decode_responses=True)
    except:
        pass
    return redis.Redis(host='127.0.0.1', port=6379, decode_responses=True)

redis_client = get_redis_client()
PRESENCE_KEY = "global_online_users"


class SiloGatewayConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """Initializes the secure, multi-tenant persistent background presence gateway."""
        self.user = None

        # Try to parse JWT token from query string or cookies
        from urllib.parse import parse_qs

        query_string = self.scope.get("query_string", b"").decode("utf-8")
        query_params = parse_qs(query_string)

        token = None
        if "token" in query_params:
            token = query_params["token"][0]
        else:
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

        if not self.user:
            await self.close(code=4003)
            return

        # Provision a targeted personal routing group signature for private signals (e.g., call rings)
        self.user_group_name = f"user_{self.user.id}"
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        await self.accept()
        from asgiref.sync import sync_to_async
        # Add user to global presence pool
        await sync_to_async(redis_client.sadd)(PRESENCE_KEY, self.user.id)
        
        # Add to global presence broadcast group
        self.presence_group = "presence_global"
        await self.channel_layer.group_add(self.presence_group, self.channel_name)

        # Broadcast joining to everyone else
        await self.channel_layer.group_send(
            self.presence_group,
            {
                "type": "presence_broadcast",
                "action": "user_joined",
                "user_id": self.user.id,
            }
        )

        await self.send(
            text_data=json.dumps(
                {
                    "stream": "system",
                    "payload": {
                        "type": "auth_success",
                        "message": "Authentication successful!",
                    },
                }
            )
        )

    async def disconnect(self, close_code):
        """Teardown handler for connection closures."""
        if self.user:
            from asgiref.sync import sync_to_async
            # Remove user from global presence pool
            await sync_to_async(redis_client.srem)(PRESENCE_KEY, self.user.id)
            
            # Broadcast leaving to everyone else
            if hasattr(self, "presence_group"):
                await self.channel_layer.group_send(
                    self.presence_group,
                    {
                        "type": "presence_broadcast",
                        "action": "user_left",
                        "user_id": self.user.id,
                    }
                )
                await self.channel_layer.group_discard(self.presence_group, self.channel_name)

        if hasattr(self, "current_channel_group"):
            await self.channel_layer.group_discard(
                self.current_channel_group, self.channel_name
            )
        if hasattr(self, "user_group_name"):
            await self.channel_layer.group_discard(
                self.user_group_name, self.channel_name
            )

    async def receive(self, text_data):
        """Central demultiplexing hub processing incoming communication frames."""
        try:
            packet = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"error": "Malformed JSON layout."}))
            return

        stream = packet.get("stream")
        payload = packet.get("payload", {})
        action = payload.get("type") or packet.get("action")
        workspace_id = payload.get("workspace_id")
        channel_id = payload.get("channel_id")

        if stream == "system":
            if action == "subscribe":
                if channel_id:
                    # Optional: Verify workspace membership
                    # is_authenticated_member = await self.verify_workspace_membership(self.user, workspace_id)
                    # if is_authenticated_member:
                    self.current_channel_group = f"channel_{channel_id}"
                    await self.channel_layer.group_add(
                        self.current_channel_group, self.channel_name
                    )
            elif action == "ping":
                await self.send(
                    text_data=json.dumps(
                        {"stream": "system", "payload": {"type": "pong"}}
                    )
                )
            return

        # Security perimeter check
        # is_authenticated_member = await self.verify_workspace_membership(self.user, workspace_id)
        # if not is_authenticated_member:
        #     await self.send(text_data=json.dumps({"error": "Access Denied."}))
        #     return

        if stream == "chat":
            await self.process_chat_stream(action, workspace_id, channel_id, payload)
        elif stream == "calls":
            await self.process_call_stream(action, workspace_id, channel_id, payload)

    async def process_chat_stream(self, action, workspace_id, channel_id, payload):
        """Routes persistent chat mutations and volatile browser telemetry indicators."""
        broadcast_group = f"channel_{channel_id}"

        if action == "send_channel_message":
            msg_dataset = await self.commit_channel_message(
                user=self.user,
                channel_id=channel_id,
                content=payload.get("content"),
            )
            await self.channel_layer.group_send(
                broadcast_group,
                {
                    "type": "chat.broadcast_message",
                    "action": "new_channel_message",
                    "data": msg_dataset,
                },
            )
        elif action == "ephemeral_chat":
            receiver_email = payload.get("receiver_email")
            content = payload.get("content")
            workspace_slug = payload.get("workspace_slug")
            
            if receiver_email and content and workspace_slug:
                # Synchronously commit the message
                message_dataset = await self.commit_direct_message(
                    sender=self.user,
                    receiver_email=receiver_email,
                    workspace_slug=workspace_slug,
                    content=content,
                )
                
                if message_dataset:
                    # Broadcast to receiver
                    receiver_id = message_dataset["receiver_id"]
                    await self.channel_layer.group_send(
                        f"user_{receiver_id}",
                        {
                            "type": "chat.broadcast_direct",
                            "message_data": message_dataset,
                        },
                    )
                    
                    # If it's a self-chat, we don't need to send it again
                    # But if it's not, we might want to broadcast back to the sender 
                    # so they have the official DB ID/timestamp. For now, the frontend 
                    # will append locally and sync on refresh, or we can broadcast to sender.
                    if receiver_id != self.user.id:
                        await self.channel_layer.group_send(
                            f"user_{self.user.id}",
                            {
                                "type": "chat.broadcast_direct",
                                "message_data": message_dataset,
                            },
                        )

    async def process_call_stream(self, action, workspace_id, channel_id, payload):
        """Asymmetric target router for establishing WebRTC direct media tracks."""
        target_user_id = payload.get("receiver_id") or payload.get("target_user_id")
        
        if not target_user_id and payload.get("receiver_email"):
            target_user_id = await self.get_user_id_by_email(payload.get("receiver_email"))
            
        if not target_user_id:
            return

        targeted_routing_layer = f"user_{target_user_id}"

        await self.channel_layer.group_send(
            targeted_routing_layer,
            {
                "type": "call.broadcast_signal",
                "sender_id": self.user.id,
                "channel_id": channel_id,
                "signal_data": payload,
            },
        )

    # --- Channel Layer Event Broadcast Handlers ---
    async def chat_broadcast_message(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "stream": "chat",
                    "payload": {"type": event["action"], "data": event["data"]},
                }
            )
        )

    async def chat_broadcast_ephemeral(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "stream": "chat",
                    "payload": {
                        "type": event["action"],
                        "user_id": event["sender_id"],
                        "is_typing": event["is_typing"],
                    },
                }
            )
        )

    async def chat_broadcast_direct(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "stream": "chat",
                    "payload": {
                        "type": "ephemeral_chat",
                        "message_data": event.get("message_data", {}),
                    },
                }
            )
        )

    async def call_broadcast_signal(self, event):
        payload = event.get("signal_data", {})
        payload["sender_id"] = event.get("sender_id")
        await self.send(text_data=json.dumps({"stream": "calls", "payload": payload}))

    async def user_signal(self, event):
        payload = event.get("signal_data", {})
        payload["sender_id"] = event.get("sender_id")
        stream = event.get("stream", "system")
        await self.send(text_data=json.dumps({"stream": stream, "payload": payload}))

    async def presence_broadcast(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "stream": "system",
                    "payload": {
                        "type": "presence_update",
                        "action": event.get("action"),
                        "user_id": event.get("user_id"),
                    },
                }
            )
        )

    # --- Asynchronous Thread Boundary Isolation Methods ---
    @database_sync_to_async
    def verify_workspace_membership(self, user, workspace_id):
        return WorkspaceMember.objects.filter(
            user=user, workspace_id=workspace_id
        ).exists()

    @database_sync_to_async
    def commit_channel_message(self, user, channel_id, content):
        from apps.chats.models import Channel, ChannelMessage
        target_channel = Channel.objects.get(id=channel_id)
        new_msg = ChannelMessage.objects.create(
            channel=target_channel, sender=user, content=content
        )

        return {
            "id": str(new_msg.id),
            "channel": str(target_channel.id),
            "content": new_msg.content,
            "sender_email": user.email,
            "timestamp": new_msg.created_at.isoformat(),
        }

    @database_sync_to_async
    def get_user_id_by_email(self, email):
        try:
            from django.contrib.auth import get_user_model

            return get_user_model().objects.get(email=email).id
        except:
            return None

    @database_sync_to_async
    def commit_direct_message(self, sender, receiver_email, workspace_slug, content):
        try:
            from django.contrib.auth import get_user_model
            from apps.chats.models import DirectMessage
            from apps.workspaces.models import Workspace
            
            receiver = get_user_model().objects.get(email=receiver_email)
            workspace = Workspace.objects.get(slug=workspace_slug)
            
            message = DirectMessage.objects.create(
                workspace=workspace,
                sender=sender,
                receiver=receiver,
                content=content
            )
            
            return {
                "id": str(message.id),
                "sender_email": sender.email,
                "receiver_email": receiver.email,
                "receiver_id": receiver.id,
                "content": message.content,
                "timestamp": message.created_at.isoformat(),
            }
        except Exception as e:
            return None
