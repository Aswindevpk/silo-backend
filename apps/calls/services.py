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
