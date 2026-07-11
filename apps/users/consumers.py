import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from apps.chats.models import Reply, Topic
from apps.workspaces.models import WorkspaceMember
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model

User = get_user_model()

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
                user_id = access_token.payload.get('user_id')
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
        await self.send(text_data=json.dumps({"stream": "system", "payload": {"type": "auth_success", "message": "Authentication successful!"}}))

    async def disconnect(self, close_code):
        """Executes strict garbage collection routines to preserve memory integrity."""
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(self.user_group_name, self.channel_name)

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
                    await self.channel_layer.group_add(self.current_channel_group, self.channel_name)
            elif action == "ping":
                await self.send(text_data=json.dumps({"stream": "system", "payload": {"type": "pong"}}))
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

        if action == "send_reply":
            reply_dataset = await self.commit_reply_mutation(
                user=self.user,
                topic_id=payload.get("topic_id"),
                content=payload.get("content")
            )
            await self.channel_layer.group_send(
                broadcast_group,
                {
                    "type": "chat.broadcast_message",
                    "action": "new_reply",
                    "data": reply_dataset
                }
            )
        elif action == "typing_indicator":
            await self.channel_layer.group_send(
                broadcast_group,
                {
                    "type": "chat.broadcast_ephemeral",
                    "action": "user_typing",
                    "sender_id": self.user.id,
                    "is_typing": payload.get("is_typing", False)
                }
            )
        elif action == "ephemeral_chat":
            receiver_email = payload.get("receiver_email")
            content = payload.get("content")
            if receiver_email and content:
                receiver_id = await self.get_user_id_by_email(receiver_email)
                if receiver_id:
                    await self.channel_layer.group_send(
                        f"user_{receiver_id}",
                        {
                            "type": "chat.broadcast_direct",
                            "sender_email": self.user.email,
                            "content": content
                        }
                    )

    async def process_call_stream(self, action, workspace_id, channel_id, payload):
        """Asymmetric target router for establishing WebRTC direct media tracks."""
        target_user_id = payload.get("receiver_id") or payload.get("target_user_id")
        if not target_user_id:
            return

        targeted_routing_layer = f"user_{target_user_id}"

        await self.channel_layer.group_send(
            targeted_routing_layer,
            {
                "type": "call.broadcast_signal",
                "sender_id": self.user.id,
                "channel_id": channel_id,
                "signal_data": payload
            }
        )

    # --- Channel Layer Event Broadcast Handlers ---
    async def chat_broadcast_message(self, event):
        await self.send(text_data=json.dumps({
            "stream": "chat",
            "payload": {
                "type": event["action"],
                "data": event["data"]
            }
        }))

    async def chat_broadcast_ephemeral(self, event):
        await self.send(text_data=json.dumps({
            "stream": "chat",
            "payload": {
                "type": event["action"],
                "user_id": event["sender_id"],
                "is_typing": event["is_typing"]
            }
        }))

    async def chat_broadcast_direct(self, event):
        await self.send(text_data=json.dumps({
            "stream": "chat",
            "payload": {
                "type": "ephemeral_chat",
                "sender_email": event["sender_email"],
                "content": event["content"]
            }
        }))

    async def call_broadcast_signal(self, event):
        payload = event.get("signal_data", {})
        payload["sender_id"] = event.get("sender_id")
        await self.send(text_data=json.dumps({
            "stream": "calls",
            "payload": payload
        }))

    # --- Asynchronous Thread Boundary Isolation Methods ---
    @database_sync_to_async
    def verify_workspace_membership(self, user, workspace_id):
        return WorkspaceMember.objects.filter(user=user, workspace_id=workspace_id).exists()

    @database_sync_to_async
    def commit_reply_mutation(self, user, topic_id, content):
        target_topic = Topic.objects.get(id=topic_id)
        new_reply = Reply.objects.create(
            topic=target_topic,
            created_by=user,
            content=content
        )
        target_topic.last_reply_at = timezone.now()
        target_topic.replies_count += 1
        target_topic.save(update_fields=['last_reply_at', 'replies_count'])

        return {
            "id": str(new_reply.id),
            "topic": str(target_topic.id),
            "content": new_reply.content,
            "created_by": {
                "id": user.id,
                "username": user.username
            },
            "timestamp": new_reply.created_at.isoformat()
        }

    @database_sync_to_async
    def get_user_id_by_email(self, email):
        try:
            from django.contrib.auth import get_user_model
            return get_user_model().objects.get(email=email).id
        except:
            return None
