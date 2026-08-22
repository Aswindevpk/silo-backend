import json
import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from apps.users.handlers import PresenceHandler
from apps.chats.handlers import ChatHandler
from apps.calls.handlers import CallHandler

logger = logging.getLogger(__name__)

class GlobalMultiplexConsumer(AsyncJsonWebsocketConsumer):
    """
    Unified Multiplexed WebSocket Consumer handling Chat,
    Presence, and WebRTC Audio/Video Signaling via handlers.
    """

    async def connect(self):
        try:
            if 'user' not in self.scope or not self.scope['user'].is_authenticated:
                print("CONSUMER REJECTING: User not authenticated")
                await self.close(code=4001)
                return

            self.user = self.scope['user']
            print("CONSUMER CALLING ACCEPT")
            await self.accept()
            print("CONSUMER ACCEPTED")

            self.presence_handler = PresenceHandler(self)
            self.chat_handler = ChatHandler(self)
            self.call_handler = CallHandler(self)

            print("CONSUMER CALLING PRESENCE HANDLER")
            await self.presence_handler.handle_connect()
            print("CONSUMER FULLY CONNECTED")
        except Exception as e:
            print(f"CONSUMER EXCEPTION IN CONNECT: {e}")
            raise

    async def disconnect(self, close_code):
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
        elif event_type == "system.ping":
            await self.send_json({"type": "system.pong"})
            return

        if event_type.startswith("chat."):
            await self.chat_handler.handle_event(event_type, workspace_id, channel_id, payload)
        elif event_type.startswith("webrtc.") or event_type.startswith("sfu"):
            await self.call_handler.handle_event(event_type, workspace_id, channel_id, payload)

    # --- Relay methods invoked via channel_layer.group_send ---
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
