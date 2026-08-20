import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def generate_cloudflare_turn_credentials():
    """
    Generates a set of short-lived ICE server credentials from Cloudflare TURN service.
    Returns a dictionary matching the expected structure of iceServers, or None on failure.
    """
    key_id = settings.CLOUDFLARE_TURN_KEY_ID
    token = settings.CLOUDFLARE_TURN_API_TOKEN

    if not key_id or not token:
        logger.error("Cloudflare TURN credentials are not configured in settings.")
        return None

    url = f"https://rtc.live.cloudflare.com/v1/turn/keys/{key_id}/credentials/generate-ice-servers"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    # Provide a 24 hour TTL for these credentials
    data = {
        "ttl": 86400
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=5)
        response.raise_for_status()
        
        result = response.json()
        # The expected return payload has an 'iceServers' key
        if "iceServers" in result:
            return result
        elif "result" in result and "iceServers" in result["result"]:
            # Depending on Cloudflare API wrapping format
            return result["result"]
        else:
            # If the format differs, just return the raw object and let the frontend adapt
            return result
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to generate Cloudflare TURN credentials: {e}")
        return None

from asgiref.sync import sync_to_async
from django.utils import timezone
from .models import ChannelSFUCall, SFUCallParticipant
from apps.chats.models import Channel, Message
from apps.chats.serializers import MessageSerializer
from django.core.exceptions import ObjectDoesNotExist

class CallService:
    @staticmethod
    @sync_to_async
    def handle_sfu_call_db(channel_id, user, cloudflare_session_id=None, action="join"):
        channel = Channel.objects.get(id=channel_id)
        
        call, created = ChannelSFUCall.objects.get_or_create(
            channel=channel,
            is_active=True,
            defaults={'started_by': user}
        )
        
        message_payload = None
        if created:
            msg = Message.objects.create(
                workspace=channel.workspace,
                channel=channel,
                sender=user,
                content="Started a huddle"
            )
            call.message = msg
            call.save(update_fields=['message'])
            message_payload = MessageSerializer(msg).data
            
        participant, p_created = SFUCallParticipant.objects.get_or_create(
            call=call,
            user=user,
            defaults={'cloudflare_session_id': cloudflare_session_id}
        )
        
        if not p_created and cloudflare_session_id:
            participant.cloudflare_session_id = cloudflare_session_id
            participant.left_at = None
            participant.save(update_fields=['cloudflare_session_id', 'left_at'])
            
        return {
            "call_id": call.id,
            "creator_id": str(call.started_by.id) if call.started_by else None,
            "created": created,
            "message_payload": message_payload
        }

    @staticmethod
    @sync_to_async
    def update_participant_session(call_id, user, session_id):
        SFUCallParticipant.objects.filter(
            call_id=call_id, user=user
        ).update(cloudflare_session_id=session_id)

    @staticmethod
    @sync_to_async
    def get_active_participants(call_id):
        participants = SFUCallParticipant.objects.filter(
            call_id=call_id, left_at__isnull=True
        ).select_related('user')
        
        return [
            {
                "id": str(p.user.id),
                "username": p.user.username,
                "avatar": p.user.profile_picture.url if getattr(p.user, 'profile_picture', None) else None,
            } for p in participants
        ]

    @staticmethod
    @sync_to_async
    def auto_end_sfu_call_db(call_id):
        try:
            call = ChannelSFUCall.objects.select_related('channel', 'message').get(id=call_id)
            if call.is_active:
                call.is_active = False
                call.ended_at = timezone.now()
                call.save(update_fields=['is_active', 'ended_at'])
                
                SFUCallParticipant.objects.filter(call=call, left_at__isnull=True).update(left_at=timezone.now())
                
                duration = int((call.ended_at - call.created_at).total_seconds())
                
                if call.message:
                    call.message.content = f"Huddle ended (Duration: {duration}s)"
                    call.message.save(update_fields=['content'])
                    return call.message, duration, call.channel.workspace_id
                
                return None, duration, call.channel.workspace_id
        except ObjectDoesNotExist:
            pass
            
        return None, 0, None

    @staticmethod
    @sync_to_async
    def _serialize_message_async(msg):
        if not msg: return None
        return MessageSerializer(msg).data
