import json
import asyncio
import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken

logger = logging.getLogger(__name__)
from apps.chats.models import Message, Channel, MessageReaction
from apps.calls.models import ChannelSFUCall, SFUCallParticipant
from apps.chats.serializers import MessageSerializer
from apps.workspaces.models import WorkspaceMember
from apps.calls.cloudflare_sfu import CloudflareSFUClient

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
        
        await self.process_huddle_leave()

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
            msg_obj = await self.create_message(
                channel_id,
                payload.get("content", ""),
                payload.get("parent_id") or payload.get("parent_message_id"),
                payload.get("attachments", []),
                payload.get("client_msg_id")
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

        # 4. SFU Call Signaling Handler
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
            
            await self.channel_layer.group_send(
                f"channel_{channel_id}",
                {
                    "type": "sfu_relay",
                    "event_type": event_type,
                    "channel_id": channel_id,
                    "payload": {
                        **payload,
                        "user": user_info
                    },
                    "sender_id": str(self.user.id),
                },
            )
            
        elif event_type == "sfu_huddle.new_session":
            offer_sdp = payload.get("sdp")
            action = payload.get("action", "join") # "start" or "join"
            try:
                # 1. Update database first (Start or Join rules)
                # We need to do this before hitting Cloudflare, so if it fails, we don't leak a session
                call_info = await self.handle_sfu_call_db(channel_id, None, action=action)
                logger.info(f"SFU Call DB update successful: call_id={call_info['call_id']}, created={call_info.get('created')}")
                
                # 2. Proxy to Cloudflare
                logger.info(f"Creating new SFU session on Cloudflare for channel {channel_id}")
                cf_result = await database_sync_to_async(CloudflareSFUClient.new_session)(offer_sdp)
                
                # 3. Update Participant with Session ID
                await self.update_participant_session(call_info["call_id"], cf_result.get("sessionId"))
                
                cf_result["call_id"] = call_info["call_id"]
                cf_result["creator_id"] = call_info["creator_id"]
                call_id = call_info.get("call_id")
                self.current_call_id = call_id
                self.current_channel_id = channel_id
                
                # Add user to active Redis set
                if call_id:
                    redis_client.sadd(f"huddle:{call_id}:active_users", str(self.user.id))
                    
                # Fetch currently active participants to send to the joiner
                active_participants = await self.get_active_participants(call_id)
                cf_result["participants"] = active_participants
                
                await self.send_json({
                    "type": "sfu_huddle.new_session_success",
                    "channel_id": channel_id,
                    "payload": cf_result,
                    "transaction_id": payload.get("transaction_id")
                })
                
                # If a new call was just created, broadcast the message to the channel
                if call_info.get("created") and call_info.get("message_payload"):
                    workspace_id = call_info.get("workspace_id")
                    if workspace_id:
                        await self.channel_layer.group_send(
                            f"channel_{channel_id}",
                            {
                                "type": "chat_message_broadcast",
                                "workspace_id": workspace_id,
                                "channel_id": channel_id,
                                "payload": call_info["message_payload"],
                            }
                        )
            except Exception as e:
                logger.error(f"Error starting/joining SFU call: {e}")
                err_msg = str(e)
                existing_call_id = None
                existing_creator_id = None
                if "|" in err_msg:
                    parts = err_msg.split("|")
                    err_msg = parts[0]
                    existing_call_id = int(parts[1]) if len(parts) > 1 else None
                    existing_creator_id = int(parts[2]) if len(parts) > 2 else None
                    
                await self.send_json({
                    "type": "sfu_huddle.error",
                    "error": err_msg,
                    "existing_call_id": existing_call_id,
                    "existing_creator_id": existing_creator_id,
                    "transaction_id": payload.get("transaction_id")
                })

        elif event_type == "sfu_huddle.new_tracks":
            session_id = payload.get("session_id")
            tracks = payload.get("tracks")
            offer_sdp = payload.get("sdp")
            try:
                cf_result = await database_sync_to_async(CloudflareSFUClient.new_tracks)(session_id, tracks, offer_sdp)
                await self.send_json({
                    "type": "sfu_huddle.new_tracks_success",
                    "payload": cf_result,
                    "transaction_id": payload.get("transaction_id")
                })
            except Exception as e:
                await self.send_json({
                    "type": "sfu_huddle.error",
                    "error": str(e),
                    "transaction_id": payload.get("transaction_id")
                })

        elif event_type == "sfu_huddle.leave":
            # The user explicitly left the huddle room
            logger.info(f"User {self.user.username} left SFU huddle in channel {channel_id}")
            call_id = payload.get("call_id") or getattr(self, "current_call_id", None)
            
            # Use process_huddle_leave to handle active user count decrement and auto-termination
            if call_id:
                # If current_call_id wasn't set somehow, set it so process_huddle_leave works
                self.current_call_id = call_id
                self.current_channel_id = channel_id
                await self.process_huddle_leave()

        elif event_type == "sfu_huddle.renegotiate":
            session_id = payload.get("session_id")
            answer_sdp = payload.get("sdp")
            try:
                cf_result = await database_sync_to_async(CloudflareSFUClient.renegotiate)(session_id, answer_sdp)
                await self.send_json({
                    "type": "sfu_huddle.renegotiate_success",
                    "payload": cf_result,
                    "transaction_id": payload.get("transaction_id")
                })
            except Exception as e:
                await self.send_json({
                    "type": "sfu_huddle.error",
                    "error": str(e),
                    "transaction_id": payload.get("transaction_id")
                })

        elif event_type == "sfu_huddle.end_call":
            call_id = payload.get("call_id")
            try:
                msg, workspace_id = await self.end_sfu_call_db(call_id)
                if msg:
                    logger.info(f"SFU call {call_id} ended manually by {self.user.username}")
                    # Delete redis tracker
                    redis_client.delete(f"huddle:{call_id}:active_users")
                    
                    # Notify everyone to stop their streams
                    await self.channel_layer.group_send(
                        f"channel_{channel_id}",
                        {
                            "type": "sfu_relay",
                            "event_type": "sfu_huddle.call_ended",
                            "channel_id": channel_id,
                            "payload": {"call_id": call_id, "auto_ended": False},
                            "sender_id": str(self.user.id),
                        }
                    )
                    
                    serialized_msg = await self._serialize_message_async(msg)
                    await self.channel_layer.group_send(
                        f"channel_{channel_id}",
                        {
                            "type": "chat_edit_broadcast",
                            "workspace_id": workspace_id,
                            "channel_id": channel_id,
                            "payload": serialized_msg,
                        }
                    )
                    
                    await self.send_json({
                        "type": "sfu_huddle.end_call_success",
                        "transaction_id": payload.get("transaction_id")
                    })
                else:
                    raise Exception("You do not have permission to end this call or it's already ended.")
            except Exception as e:
                logger.error(f"Error ending SFU call: {e}")
                await self.send_json({
                    "type": "sfu_huddle.error",
                    "error": str(e),
                    "transaction_id": payload.get("transaction_id")
                })

    async def process_huddle_leave(self):
        if hasattr(self, 'current_call_id') and self.current_call_id:
            call_id = self.current_call_id
            channel_id = getattr(self, 'current_channel_id', None)
            user_id = str(self.user.id)
            
            redis_client.srem(f"huddle:{call_id}:active_users", user_id)
            active_count = redis_client.scard(f"huddle:{call_id}:active_users")
            
            if channel_id:
                user_info = {
                    "id": user_id,
                    "username": self.user.username,
                    "avatar": self.user.profile_picture.url if getattr(self.user, 'profile_picture', None) else None,
                }
                # Broadcast participant_left
                await self.channel_layer.group_send(
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
                # Redis operations are atomic, the last person to leave will see count == 0
                msg, duration, workspace_id = await self.auto_end_sfu_call_db(call_id)
                if msg and channel_id:
                    logger.info(f"SFU call {call_id} automatically ended (last person left)")
                    redis_client.delete(f"huddle:{call_id}:active_users")
                    
                    # Broadcast huddle_ended
                    await self.channel_layer.group_send(
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
                    
                    serialized_msg = await self._serialize_message_async(msg)
                    await self.channel_layer.group_send(
                        f"channel_{channel_id}",
                        {
                            "type": "chat_edit_broadcast",
                            "workspace_id": workspace_id,
                            "channel_id": channel_id,
                            "payload": serialized_msg,
                        }
                    )
            
            self.current_call_id = None
            self.current_channel_id = None

    @database_sync_to_async
    def auto_end_sfu_call_db(self, call_id):
        from apps.calls.models import ChannelSFUCall
        from django.utils import timezone
        sfu_call = ChannelSFUCall.objects.filter(id=call_id, is_active=True).first()
        duration = 0
        if sfu_call:
            sfu_call.is_active = False
            sfu_call.ended_at = timezone.now()
            duration = int((sfu_call.ended_at - sfu_call.created_at).total_seconds())
            sfu_call.save(update_fields=["is_active", "ended_at"])
            
            if sfu_call.message:
                attachments = list(sfu_call.message.attachments)
                for att in attachments:
                    if att.get("type") == "sfu_call":
                        att["is_active"] = False
                        att["duration_seconds"] = duration
                sfu_call.message.attachments = attachments
                sfu_call.message.save(update_fields=["attachments"])
                return sfu_call.message, duration, str(sfu_call.channel.workspace.id)
        return None, 0, None

    @database_sync_to_async
    def handle_sfu_call_db(self, channel_id, cloudflare_session_id=None, action="join"):
        from apps.chats.models import Channel, Message
        from apps.calls.models import ChannelSFUCall, SFUCallParticipant
        from apps.chats.serializers import MessageSerializer
        from apps.workspaces.models import WorkspaceMember
        from django.shortcuts import get_object_or_404
        
        channel = get_object_or_404(Channel, id=channel_id)
        
        # Verify access
        is_member = channel.memberships.filter(user=self.user).exists()
        is_workspace_member = WorkspaceMember.objects.filter(workspace=channel.workspace, user=self.user).exists()
        
        if not is_member:
            if channel.type == Channel.ChannelType.PUBLIC and is_workspace_member:
                pass
            else:
                raise Exception("Not a member of this channel.")

        # Check for active call
        active_call = ChannelSFUCall.objects.filter(channel=channel, is_active=True).first()
        
        created = False
        message_payload = None
        
        if action == "start":
            if active_call:
                raise Exception(f"An active call already exists in this channel.|{active_call.id}|{active_call.started_by.id}")
            sfu_call = None
        elif action == "join":
            if not active_call:
                raise Exception("No active call found to join.")
            sfu_call = active_call
        else:
            if active_call:
                sfu_call = active_call
            else:
                sfu_call = None
        if not sfu_call:
            # Start new call
            message = Message.objects.create(
                workspace=channel.workspace,
                channel=channel,
                sender=self.user,
                content=f"{self.user.username} started a voice huddle.",
                attachments=[{"type": "sfu_call"}]
            )
            sfu_call = ChannelSFUCall.objects.create(
                channel=channel,
                message=message,
                started_by=self.user,
                is_active=True
            )
            message.attachments[0]["call_id"] = sfu_call.id
            message.save(update_fields=["attachments"])
            
            import json
            serializer = MessageSerializer(message, context={'request': None, 'user': self.user})
            message_payload = json.loads(json.dumps(serializer.data))
            created = True

        participant, p_created = SFUCallParticipant.objects.get_or_create(
            call=sfu_call,
            user=self.user,
            defaults={'cloudflare_session_id': cloudflare_session_id}
        )
        if not p_created and cloudflare_session_id:
            participant.cloudflare_session_id = cloudflare_session_id
            participant.save(update_fields=["cloudflare_session_id"])

        redis_client.sadd(f"huddle:{sfu_call.id}:active_users", str(self.user.id))

        return {
            "call_id": sfu_call.id,
            "creator_id": sfu_call.started_by.id,
            "created": created,
            "message_payload": message_payload,
            "workspace_id": str(channel.workspace.id)
        }
        
    @database_sync_to_async
    def end_sfu_call_db(self, call_id):
        from apps.calls.models import ChannelSFUCall
        from django.utils import timezone
        sfu_call = ChannelSFUCall.objects.filter(id=call_id, is_active=True).first()
        if sfu_call and sfu_call.started_by == self.user:
            sfu_call.is_active = False
            sfu_call.ended_at = timezone.now()
            sfu_call.save(update_fields=["is_active", "ended_at"])
            
            if sfu_call.message:
                attachments = list(sfu_call.message.attachments)
                for att in attachments:
                    if att.get("type") == "sfu_call":
                        att["is_active"] = False
                sfu_call.message.attachments = attachments
                sfu_call.message.save(update_fields=["attachments"])
                return sfu_call.message, str(sfu_call.channel.workspace.id)
        return None, None
        
    @database_sync_to_async
    def update_participant_session(self, call_id, session_id):
        from apps.calls.models import SFUCallParticipant
        participant = SFUCallParticipant.objects.filter(call_id=call_id, user=self.user).first()
        if participant:
            participant.cloudflare_session_id = session_id
            participant.save(update_fields=["cloudflare_session_id"])

    @database_sync_to_async
    def get_active_participants(self, call_id):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user_ids = redis_client.smembers(f"huddle:{call_id}:active_users")
        participants = []
        if user_ids:
            users = User.objects.filter(id__in=[int(uid) for uid in user_ids])
            for u in users:
                participants.append({
                    "userId": u.id,
                    "username": u.username,
                    "avatar": u.profile_picture.url if getattr(u, 'profile_picture', None) else None,
                    "isMuted": False # Will be updated via mute events, default to False for now
                })
        return participants

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

    async def sfu_relay(self, event):
        """Relays SFU Huddle signals to channel peers (excluding sender)."""
        if event["sender_id"] != str(self.user.id):
            await self.send_json(
                {
                    "type": "sfu_relay",
                    "event_type": event["event_type"],
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
    def create_message(self, channel_id, content, parent_id=None, attachments=None, client_msg_id=None):
        if attachments is None:
            attachments = []
        channel = Channel.objects.get(id=channel_id)
        msg = Message.objects.create(
            workspace_id=channel.workspace_id,
            channel=channel,
            sender=self.user,
            content=content,
            attachments=attachments,
            parent_message_id=parent_id
        )
        
        if parent_id:
            parent = Message.objects.get(id=parent_id)
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
            "parent_message": parent_id,
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
        import json
        return json.loads(json.dumps(MessageSerializer(msg).data))

    @database_sync_to_async
    def _serialize_message_async(self, msg):
        import json
        return json.loads(json.dumps(MessageSerializer(msg).data))
