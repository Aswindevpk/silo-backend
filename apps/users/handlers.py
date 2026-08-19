from apps.core.redis_client import redis_client
import logging

logger = logging.getLogger(__name__)

PRESENCE_KEY = "silo_online_users"

class PresenceHandler:
    def __init__(self, consumer):
        self.consumer = consumer
        self.user = consumer.user
        self.user_group = f"user_{self.user.id}"

    async def handle_connect(self):
        await self.consumer.channel_layer.group_add(self.user_group, self.consumer.channel_name)
        redis_client.sadd(PRESENCE_KEY, str(self.user.id))
        await self.broadcast_presence("online")

    async def handle_disconnect(self):
        redis_client.srem(PRESENCE_KEY, str(self.user.id))
        await self.broadcast_presence("offline")
        await self.consumer.channel_layer.group_discard(self.user_group, self.consumer.channel_name)

    async def broadcast_presence(self, status):
        """Notifies user groups of status updates."""
        await self.consumer.send_json(
            {
                "type": "presence.status_change",
                "payload": {"user_id": str(self.user.id), "status": status},
            }
        )
