import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class CloudflareSFUClient:
    """
    Client for interacting with Cloudflare Realtime SFU API via rtc.live.cloudflare.com
    """
    
    @staticmethod
    def get_api_url():
        app_id = settings.CLOUDFLARE_SFU_APP_ID
        return f"https://rtc.live.cloudflare.com/v1/apps/{app_id}"
        
    @staticmethod
    def _send_request(url, body, method="POST"):
        headers = {
            "Authorization": f"Bearer {settings.CLOUDFLARE_SFU_API_TOKEN}",
            "Content-Type": "application/json"
        }
        try:
            if method == "POST":
                response = requests.post(url, headers=headers, json=body, timeout=10)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=body, timeout=10)
            else:
                raise ValueError("Unsupported HTTP method")
            
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            error_body = ""
            if hasattr(e, 'response') and e.response is not None:
                error_body = e.response.text
            logger.error(f"Cloudflare SFU API Error: {e}. Body: {error_body}")
            raise Exception(f"{e} - Body: {error_body}")

    @staticmethod
    def new_session(offer_sdp):
        """Creates a new session by sending an offer SDP."""
        url = f"{CloudflareSFUClient.get_api_url()}/sessions/new"
        body = {
            "sessionDescription": {
                "type": "offer",
                "sdp": offer_sdp
            }
        }
        return CloudflareSFUClient._send_request(url, body)

    @staticmethod
    def new_tracks(session_id, tracks, offer_sdp=None):
        """Shares local tracks or requests remote tracks."""
        url = f"{CloudflareSFUClient.get_api_url()}/sessions/{session_id}/tracks/new"
        body = {
            "tracks": tracks
        }
        if offer_sdp:
            body["sessionDescription"] = {
                "type": "offer",
                "sdp": offer_sdp
            }
        return CloudflareSFUClient._send_request(url, body)

    @staticmethod
    def renegotiate(session_id, answer_sdp):
        """Sends an answer SDP if a renegotiation is required."""
        url = f"{CloudflareSFUClient.get_api_url()}/sessions/{session_id}/renegotiate"
        body = {
            "sessionDescription": {
                "type": "answer",
                "sdp": answer_sdp
            }
        }
        return CloudflareSFUClient._send_request(url, body, method="PUT")
