import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
import asyncio
import websockets
import json

User = get_user_model()

def get_token():
    user, _ = User.objects.get_or_create(username='wstestuser', email='wstestuser@example.com')
    return AccessToken.for_user(user)

async def test(token):
    uri = f"ws://localhost:8000/ws/users/?token={token}"
    print(f"Connecting to {uri}")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to websocket!")
            
            # Wait for auth success message
            response = await websocket.recv()
            print(f"Initial response: {response}")
            
            # Send ping
            msg = json.dumps({"stream": "system", "payload": {"type": "ping"}})
            await websocket.send(msg)
            print(f"Sent: {msg}")
            
            # Wait for pong
            response = await websocket.recv()
            print(f"Received: {response}")
            
            print("Test successful!")
    except Exception as e:
        print(f"Failed to connect or test: {e}")

if __name__ == "__main__":
    token = get_token()
    asyncio.run(test(token))
