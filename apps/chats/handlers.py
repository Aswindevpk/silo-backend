
from .services import ChatService
import logging

logger = logging.getLogger(__name__)

class ChatHandler:
    def __init__(self, consumer):
        self.consumer = consumer
        self.user = consumer.user

    async def handle_event(self, event_type, workspace_id, channel_id, payload):
        if event_type == "chat.send_message":
            msg_obj = await ChatService.create_message(
                channel_id,
                self.user,
                payload.get("content", ""),
                payload.get("parent_id") or payload.get("parent_message_id"),
                payload.get("attachments", []),
                payload.get("client_msg_id")
            )

            await self.consumer.channel_layer.group_send(
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
            msg_obj = await ChatService.toggle_reaction(channel_id, self.user, message_id, emoji)
            if msg_obj:
                await self.consumer.channel_layer.group_send(
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
            msg_obj = await ChatService.edit_message(channel_id, self.user, message_id, content)
            if msg_obj:
                await self.consumer.channel_layer.group_send(
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
            msg_obj = await ChatService.delete_message(channel_id, self.user, message_id)
            if msg_obj:
                await self.consumer.channel_layer.group_send(
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
            msg_obj = await ChatService.toggle_pin(channel_id, self.user, message_id)
            if msg_obj:
                await self.consumer.channel_layer.group_send(
                    f"channel_{channel_id}",
                    {
                        "type": "chat_pin_broadcast",
                        "workspace_id": workspace_id,
                        "channel_id": channel_id,
                        "payload": msg_obj,
                    },
                )
