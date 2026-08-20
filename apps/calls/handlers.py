from .services import CallService
from apps.calls.cloudflare_sfu import CloudflareSFUClient
from apps.core.redis_client import redis_client
from channels.db import database_sync_to_async
import logging

logger = logging.getLogger(__name__)

class CallHandler:
    def __init__(self, consumer):
        self.consumer = consumer
        self.user = consumer.user

    async def handle_event(self, event_type, workspace_id, channel_id, payload):
        if event_type in ["webrtc.call_offer", "webrtc.call_answer", "webrtc.ice_candidate"]:
            await self.consumer.channel_layer.group_send(
                f"channel_{channel_id}",
                {
                    "type": "webrtc_relay",
                    "event_type": event_type,
                    "channel_id": channel_id,
                    "payload": payload,
                    "sender_id": str(self.user.id),
                },
            )

        elif event_type in [
            "sfu_huddle.joined",
            "sfu_huddle.left",
            "sfu_huddle.mute_toggled",
            "sfu_huddle.publish_tracks",
            "sfu_huddle.request_tracks",
        ]:
            user_info = {
                "id": str(self.user.id),
                "username": self.user.username,
                "avatar": self.user.profile_picture.url if getattr(self.user, 'profile_picture', None) else None,
            }
            logger.info(f"SFU Event {event_type} for user {self.user.username} in channel {channel_id}")
            
            await self.consumer.channel_layer.group_send(
                f"channel_{channel_id}",
                {
                    "type": "sfu_relay",
                    "event_type": event_type,
                    "channel_id": channel_id,
                    "payload": {**payload, "user": user_info},
                    "sender_id": str(self.user.id),
                },
            )
            
        elif event_type == "sfu_huddle.new_session":
            offer_sdp = payload.get("sdp")
            action = payload.get("action", "join")
            try:
                call_info = await CallService.handle_sfu_call_db(channel_id, self.user, cloudflare_session_id=None, action=action)
                
                cf_result = await database_sync_to_async(CloudflareSFUClient.new_session)(offer_sdp)
                await CallService.update_participant_session(call_info["call_id"], self.user, cf_result.get("sessionId"))
                
                cf_result["call_id"] = call_info["call_id"]
                cf_result["creator_id"] = call_info["creator_id"]
                call_id = call_info.get("call_id")
                
                self.consumer.current_call_id = call_id
                self.consumer.current_channel_id = channel_id
                
                active_participants = await CallService.get_active_participants(call_id)
                cf_result["participants"] = active_participants
                
                await self.consumer.send_json({
                    "type": "sfu_huddle.new_session_success",
                    "payload": cf_result
                })
                
                if call_info.get("created") and call_info.get("message_payload"):
                    await self.consumer.channel_layer.group_send(
                        f"channel_{channel_id}",
                        {
                            "type": "chat_message_broadcast",
                            "workspace_id": workspace_id,
                            "channel_id": channel_id,
                            "payload": call_info["message_payload"],
                        }
                    )
            except Exception as e:
                logger.error(f"Error handling new_session: {str(e)}")
                await self.consumer.send_json({
                    "type": "sfu_huddle.error",
                    "payload": {"message": str(e)}
                })

    async def process_huddle_leave(self):
        if hasattr(self.consumer, 'current_call_id') and self.consumer.current_call_id:
            call_id = self.consumer.current_call_id
            channel_id = getattr(self.consumer, 'current_channel_id', None)
            user_id = str(self.user.id)
            
            redis_client.srem(f"huddle:{call_id}:active_users", user_id)
            active_count = redis_client.scard(f"huddle:{call_id}:active_users")
            
            if channel_id:
                user_info = {
                    "id": user_id,
                    "username": self.user.username,
                    "avatar": self.user.profile_picture.url if getattr(self.user, 'profile_picture', None) else None,
                }
                await self.consumer.channel_layer.group_send(
                    f"channel_{channel_id}",
                    {
                        "type": "sfu_relay",
                        "event_type": "sfu_huddle.left",
                        "channel_id": channel_id,
                        "payload": {"user": user_info, "call_id": call_id},
                        "sender_id": user_id,
                    }
                )
                
            if active_count == 0:
                msg, duration, workspace_id = await CallService.auto_end_sfu_call_db(call_id)
                if msg and channel_id:
                    logger.info(f"SFU call {call_id} automatically ended")
                    redis_client.delete(f"huddle:{call_id}:active_users")
                    
                    await self.consumer.channel_layer.group_send(
                        f"channel_{channel_id}",
                        {
                            "type": "sfu_relay",
                            "event_type": "sfu_huddle.call_ended",
                            "channel_id": channel_id,
                            "payload": {
                                "call_id": call_id, 
                                "duration_seconds": duration,
                                "auto_ended": True
                            },
                            "sender_id": "system",
                        }
                    )
                    
                    serialized_msg = await CallService._serialize_message_async(msg)
                    await self.consumer.channel_layer.group_send(
                        f"channel_{channel_id}",
                        {
                            "type": "chat_edit_broadcast",
                            "workspace_id": workspace_id,
                            "channel_id": channel_id,
                            "payload": serialized_msg,
                        }
                    )
            
            self.consumer.current_call_id = None
            self.consumer.current_channel_id = None
