import urllib.parse
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
import jwt
from django.conf import settings

User = get_user_model()

@database_sync_to_async
def get_user_from_token(token_key):
    try:
        valid_token = UntypedToken(token_key)
        user_id = valid_token.get('user_id')
        if user_id:
            return User.objects.get(id=user_id)
    except (InvalidToken, TokenError, User.DoesNotExist):
        pass
    except jwt.PyJWTError:
        pass
    return AnonymousUser()

import logging
logger = logging.getLogger(__name__)

class JWTAuthMiddleware:
    """
    WebSocket Middleware that extracts JWT token from query string (?token=...)
    or cookies and authenticates the user.
    """
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        token = None
        
        # 1. Try to get token from query string
        query_string = scope.get('query_string', b'').decode('utf-8')
        query_params = urllib.parse.parse_qs(query_string)
        token = query_params.get('token', [None])[0]
        
        # 2. Try to get token from cookies
        if not token:
            for name, value in scope.get('headers', []):
                if name == b'cookie':
                    cookies = value.decode('utf-8').split(';')
                    for cookie in cookies:
                        cookie = cookie.strip()
                        if cookie.startswith(settings.SIMPLE_JWT.get('AUTH_COOKIE', 'access') + '='):
                            token = cookie.split('=', 1)[1]
                            break
                    break
        
        if token:
            print(f"MIDDLEWARE FOUND TOKEN: {token[:10]}...")
            user = await get_user_from_token(token)
            scope['user'] = user
            if user.is_authenticated:
                print(f"WebSocket authenticated for user: {user.username}")
            else:
                print("WebSocket token provided but user authentication failed (Invalid token).")
        else:
            print("WebSocket connection attempted with NO TOKEN PROVIDED.")
            scope['user'] = AnonymousUser()
            
        return await self.inner(scope, receive, send)

def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(inner)
