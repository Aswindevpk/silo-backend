import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from apps.users.handlers import PresenceHandler
from apps.chats.handlers import ChatHandler
from apps.calls.handlers import CallHandler
from apps.chats.models import ChannelMember
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)

class GlobalMultiplexConsumer(AsyncJsonWebsocketConsumer):
    """
    Unified Multiplexed WebSocket Consumer handling Chat,
    Presence, and WebRTC Audio/Video Signaling via handlers.
    """

    async def connect(self):
        print(self)
        try:
            if 'user' not in self.scope or not self.scope['user'].is_authenticated:
                await self.close(code=4001)
                return

            self.user = self.scope['user']
            await self.accept()

            # Automatically subscribe the user to all their channels
            channel_ids = await sync_to_async(list)(
                ChannelMember.objects.filter(user=self.user).values_list('channel_id', flat=True)
            )
            self.subscribed_channels = channel_ids
            for channel_id in channel_ids:
                await self.channel_layer.group_add(
                    f"channel_{channel_id}", self.channel_name
                )

            self.presence_handler = PresenceHandler(self)
            self.chat_handler = ChatHandler(self)
            self.call_handler = CallHandler(self)
            await self.presence_handler.handle_connect()
        except Exception as e:
            raise

    async def disconnect(self, close_code):
        if hasattr(self, 'subscribed_channels'):
            for channel_id in self.subscribed_channels:
                await self.channel_layer.group_discard(
                    f"channel_{channel_id}", self.channel_name
                )
        
        if hasattr(self, 'presence_handler'):
            await self.presence_handler.handle_disconnect()
        if hasattr(self, 'call_handler'):
            await self.call_handler.process_huddle_leave()

    async def receive_json(self, content):
        """Multiplexing Event Router"""
        event_type = content.get("type")
        workspace_id = content.get("workspace_id")
        channel_id = content.get("channel_id")
        payload = content.get("payload", {})

        # Auto-subscribe dynamically if the user interacts with a new channel they aren't subscribed to yet
        if channel_id:
            try:
                cid = int(channel_id)
                if hasattr(self, 'subscribed_channels') and cid not in self.subscribed_channels:
                    await self.channel_layer.group_add(f"channel_{cid}", self.channel_name)
                    self.subscribed_channels.append(cid)
            except (ValueError, TypeError):
                pass

        # if event_type == "room.subscribe":
        #     await self.channel_layer.group_add(
        #         f"channel_{channel_id}", self.channel_name
        #     )
        #     return
        # elif event_type == "room.unsubscribe":
        #     await self.channel_layer.group_discard(
        #         f"channel_{channel_id}", self.channel_name
        #     )
        #     return
        if event_type == "system.ping":
            await self.send_json({"type": "system.pong"})
            return

        if event_type.startswith("chat."):
            await self.chat_handler.handle_event(event_type, workspace_id, channel_id, payload)
        elif event_type.startswith("webrtc.") or event_type.startswith("sfu"):
            await self.call_handler.handle_event(event_type, workspace_id, channel_id, payload)

    # --- Relay methods invoked via channel_layer.group_send ---
    async def presence_status_broadcast(self, event):
        await self.send_json({
            "type": "presence.status_change",
            "payload": event["payload"],
        })

    async def chat_message_broadcast(self, event):
        await self.send_json({
            "type": "chat.message_received",
            "workspace_id": event["workspace_id"],
            "channel_id": event["channel_id"],
            "payload": event["payload"],
        })

    async def chat_reaction_broadcast(self, event):
        await self.send_json({
            "type": "chat.reaction_updated",
            "workspace_id": event["workspace_id"],
            "channel_id": event["channel_id"],
            "payload": event["payload"],
        })

    async def chat_edit_broadcast(self, event):
        await self.send_json({
            "type": "chat.message_edited",
            "workspace_id": event["workspace_id"],
            "channel_id": event["channel_id"],
            "payload": event["payload"],
        })

    async def chat_delete_broadcast(self, event):
        await self.send_json({
            "type": "chat.message_deleted",
            "workspace_id": event["workspace_id"],
            "channel_id": event["channel_id"],
            "payload": event["payload"],
        })

    async def chat_pin_broadcast(self, event):
        await self.send_json({
            "type": "chat.message_pinned",
            "workspace_id": event["workspace_id"],
            "channel_id": event["channel_id"],
            "payload": event["payload"],
        })

    async def webrtc_relay(self, event):
        if event["sender_id"] != str(self.user.id):
            await self.send_json({
                "type": "webrtc_relay",
                "event_type": event["event_type"],
                "channel_id": event["channel_id"],
                "payload": event["payload"],
            })

    async def sfu_relay(self, event):
        if event["sender_id"] != str(self.user.id):
            await self.send_json({
                "type": "sfu_relay",
                "event_type": event["event_type"],
                "channel_id": event["channel_id"],
                "payload": event["payload"],
            })
