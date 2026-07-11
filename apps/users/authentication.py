from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from django.conf import settings

class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        # Extract the token from the cookie
        # print('COOKIES RECEIVED:', request.COOKIES)
        raw_token = request.COOKIES.get(settings.SIMPLE_JWT.get('AUTH_COOKIE', 'access'))

        if raw_token is None:
            return None

        try:
            validated_token = self.get_validated_token(raw_token)
        except InvalidToken:
            raise AuthenticationFailed('Token is invalid or expired')
        except AuthenticationFailed as e:
            raise e

        return self.get_user(validated_token), validated_token

    def authenticate_header(self, request):
        return 'Bearer realm="api"'
