import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()

@database_sync_to_async
def get_user_from_token(token_string):
    try:
        access_token = AccessToken(token_string.strip())
        user_id = access_token.payload.get('user_id')
        user = User.objects.get(id=user_id)
        if user.is_active:
            return user
    except Exception:
        pass
    return None

class UserConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.authenticated = False
        self.user = None
        # Start a background task for the timeout (10 seconds)
        self.auth_timeout_task = asyncio.create_task(self.auth_timeout_check())
        # Request authentication from client
        await self.send(text_data=json.dumps({
            "message": "Connection established. Please authenticate by sending your access token."
        }))

    async def auth_timeout_check(self):
        try:
            await asyncio.sleep(10)
            if not self.authenticated:
                await self.send(text_data=json.dumps({
                    "error": "Authentication timeout. Connection closing."
                }))
                await self.close(code=4408)  # Custom close code for timeout
        except asyncio.CancelledError:
            pass

    async def disconnect(self, close_code):
        # Cancel the timeout task if running
        if hasattr(self, 'auth_timeout_task'):
            self.auth_timeout_task.cancel()

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            if not self.authenticated:
                await self.send(text_data=json.dumps({
                    "error": "Invalid JSON. Connection closing."
                }))
                await self.close(code=4401)
                return
            data = {}

        if not self.authenticated:
            # First message must be authentication
            if data.get("type") == "auth" and "token" in data:
                token = data["token"]
                user = await get_user_from_token(token)
                if user:
                    self.authenticated = True
                    self.user = user
                    # Cancel the timeout task
                    if hasattr(self, 'auth_timeout_task'):
                        self.auth_timeout_task.cancel()
                    await self.send(text_data=json.dumps({
                        "message": f"Authentication successful! Welcome {user.email}."
                    }))
                else:
                    await self.send(text_data=json.dumps({
                        "error": "Invalid token. Connection closing."
                    }))
                    await self.close(code=4401)
            else:
                await self.send(text_data=json.dumps({
                    "error": "Authentication required. Connection closing."
                }))
                await self.close(code=4401)
        else:
            # Echo back normal messages
            await self.send(text_data=json.dumps({
                "message": "Echo from consumer",
                "payload": data
            }))
