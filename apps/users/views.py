from django.contrib.auth import get_user_model
from apps.users.models import CustomUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .serializers import RegisterSerializer, ResendVerificationEmailSerializer, ForgotPasswordSerializer, ResetPasswordSerializer, LoginSerializer, GoogleLoginSerializer
from rest_framework import status
from utils.exceptions import CustomAPIException



class RegisterAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        from apps.users.tasks import send_verification_email_task
        send_verification_email_task.delay(user.id)
        return Response(
            {
                "message": "Registration successful. Please check your email to verify your account.",
                "data": {
                    "user": {
                        "username": user.username,
                        "email": user.email,
                    }
                }
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyEmailAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        token = request.query_params.get('token')
        if not token:
            raise CustomAPIException(
                message="Token is required",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        from .models import EmailVerificationToken
        token_obj = EmailVerificationToken.objects.filter(token=token).first()
        if not token_obj:
            raise CustomAPIException(
                message="Invalid token",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        
        if token_obj.is_expired():
            token_obj.delete()
            raise CustomAPIException(
                message="Invalid or expired token.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        user = token_obj.user
        user.is_verified = True
        user.save()
        token_obj.delete()
        return Response(
            {
                "message": "Email verified successfully",
                "data": {}
            },
            status=status.HTTP_200_OK,
        )


class ResendVerificationEmailAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = ResendVerificationEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        user = CustomUser.objects.get(email=email)
        if user.is_verified:
            raise CustomAPIException(
                message="Email is already verified",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        
        from django.utils import timezone as tz
        from datetime import timedelta
        
        if hasattr(user, 'email_verification_token'):
            existing = user.email_verification_token
            if not existing.is_expired():
                cooldown_until = existing.created_at + timedelta(minutes=2)
                if tz.now() < cooldown_until:
                    seconds_left = int((cooldown_until - tz.now()).total_seconds())
                    raise CustomAPIException(
                        message=f"Please wait {seconds_left} seconds before requesting another email.",
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    )
            existing.delete()
        
        from apps.users.tasks import send_verification_email_task
        send_verification_email_task.delay(user.id)
        return Response(
            {
                "message": "Verification email sent successfully",
            },
            status=status.HTTP_200_OK,
        )


class ForgotPasswordAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            return Response(
                {
                    "message": "If an account with this email exists, a password reset link has been sent.",
                    "data": {}
                },
                status=status.HTTP_200_OK,
            )

        from django.utils import timezone as tz
        from datetime import timedelta

        if hasattr(user, 'password_reset_token'):
            existing = user.password_reset_token
            if not existing.is_expired():
                cooldown_until = existing.created_at + timedelta(minutes=2)
                if tz.now() < cooldown_until:
                    seconds_left = int((cooldown_until - tz.now()).total_seconds())
                    raise CustomAPIException(
                        message=f"Please wait {seconds_left} seconds before requesting another email.",
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    )
            existing.delete()

        from apps.users.tasks import send_password_reset_email_task
        send_password_reset_email_task.delay(user.id)
        return Response(
            {
                "success": True,
                "message": "If an account with this email exists, a password reset link has been sent.",
                "data": {}
            },
            status=status.HTTP_200_OK,
        )


class ResetPasswordAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data['token']
        password = serializer.validated_data['password']

        from .models import PasswordResetToken
        token_obj = PasswordResetToken.objects.filter(token=token).first()
        if not token_obj:
            raise CustomAPIException(
                message="Invalid token",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        if token_obj.is_expired():
            token_obj.delete()
            raise CustomAPIException(
                message="Invalid or expired token.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        user = token_obj.user
        user.set_password(password)
        user.save()
        token_obj.delete()

        return Response(
            {
                "success": True,
                "message": "Password has been reset successfully",
                "data": {}
            },
            status=status.HTTP_200_OK,
        )


from rest_framework_simplejwt.tokens import RefreshToken

from django.contrib.auth import authenticate

class StandardLoginView(APIView):
    """Standard Login API View that returns tokens along with user information"""
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        
        # 1. ACCCOUNT EXISTENCE CHECK
        user = CustomUser.objects.filter(email=email).first()
        if not user:
            raise CustomAPIException(
                message="Invalid email or password.", 
                status_code=status.HTTP_401_UNAUTHORIZED
            )
            
        # 2. UNUSABLE PASSWORD PROTECTION (Social-Only Accounts)
        if not user.has_usable_password():
            raise CustomAPIException(
                message="This account uses Google Sign-In. Please log in with Google.", 
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # 2.5 ACTIVE STATUS CHECK
        if not user.is_active:
            if user.check_password(password):
                raise CustomAPIException(
                    message="Your account has been deactivated (this may be due to email delivery failures). Please contact support.", 
                    status_code=status.HTTP_403_FORBIDDEN
                )
            else:
                raise CustomAPIException(
                    message="Invalid email or password.", 
                    status_code=status.HTTP_401_UNAUTHORIZED
                )

        # 3. CREDENTIAL AUTHENTICATION
        authenticated_user = authenticate(email=email, password=password)
        if not authenticated_user:
            raise CustomAPIException(
                message="Invalid email or password.", 
                status_code=status.HTTP_401_UNAUTHORIZED
            )

        if not authenticated_user.is_verified:
            raise CustomAPIException(
                message="Email is not verified. Please verify your email to log in.", 
                errors={
                    "code": "EMAIL_NOT_VERIFIED",
                },
                status_code=status.HTTP_401_UNAUTHORIZED
            )

        # Generate tokens manually
        refresh = RefreshToken.for_user(authenticated_user)

        response = Response(
            {
                "message": "Login successful.",
                "data": {
                    "user": {
                        "username": authenticated_user.username,
                        "email": authenticated_user.email,
                    }
                }
            },
            status=status.HTTP_200_OK,
        )
        response.set_cookie(
            'access',
            str(refresh.access_token),
            max_age=int(settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds()),
            httponly=True,
            samesite='None' if not settings.DEBUG else 'Lax', secure=not settings.DEBUG
        )
        response.set_cookie(
            'refresh',
            str(refresh),
            max_age=int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()),
            httponly=True,
            samesite='None' if not settings.DEBUG else 'Lax', secure=not settings.DEBUG
        )
        return response


from django.conf import settings

User = get_user_model()
import requests
import secrets
from urllib.parse import urlencode
from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied
from django.urls import reverse

class GoogleLoginView(APIView):
    """
    Initiates the Google OAuth 2.0 login flow.
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request, *args, **kwargs):
        # 1. Generate a secure, random state string
        state = secrets.token_urlsafe(32)
        
        # 2. Store the state in the Django session (Anti-CSRF)
        request.session['oauth_state'] = state
        
        # 3. Construct the Google Authorization URL
        client_id = settings.GOOGLE_OAUTH2_CLIENT_ID
        redirect_uri = request.build_absolute_uri(reverse('google-callback'))
        
        # Store redirect_uri in session to use in callback for token exchange
        request.session['oauth_redirect_uri'] = redirect_uri
        
        scope = "openid email profile"
        
        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': scope,
            'state': state,
            'access_type': 'offline',
            'prompt': 'consent',
        }
        
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
        
        # Redirect the user to Google's authorization endpoint
        return redirect(auth_url)


class GoogleCallbackView(APIView):
    """
    Handles the callback from Google, verifies state, exchanges code for tokens, 
    and issues local JWT tokens.
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        # 1. Verify the state parameter against the session (Anti-CSRF)
        session_state = request.session.get('oauth_state')
        returned_state = request.GET.get('state')
        
        if not session_state or session_state != returned_state:
            raise PermissionDenied("Invalid or missing state parameter. CSRF validation failed.")
            
        # Clean up state from session
        del request.session['oauth_state']
        
        code = request.GET.get('code')
        if not code:
            return Response({
                "success": False,
                "message": "Authorization code is required",
                "data": {}
            }, status=status.HTTP_400_BAD_REQUEST)
            
        redirect_uri = request.session.get('oauth_redirect_uri', request.build_absolute_uri(reverse('google-callback')))

        # 2. Exchange authorization code for access token & ID token from Google
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            'code': code,
            'client_id': settings.GOOGLE_OAUTH2_CLIENT_ID,
            'client_secret': settings.GOOGLE_OAUTH2_CLIENT_SECRET,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code',
        }

        token_response = requests.post(token_url, data=data)
        token_data = token_response.json()

        if 'error' in token_data:
            return Response({
                "success": False,
                "message": "Failed to exchange code with Google",
                "data": {"details": token_data}
            }, status=status.HTTP_400_BAD_REQUEST)

        access_token = token_data.get('access_token')

        # 3. Use the token to fetch user profile info from Google
        user_info_url = "https://www.googleapis.com/oauth2/v3/userinfo"
        user_info_response = requests.get(user_info_url, headers={'Authorization': f'Bearer {access_token}'})
        user_info = user_info_response.json()

        if 'error' in user_info:
            return Response({
                "success": False,
                "message": "Failed to fetch user info from Google",
                "data": {}
            }, status=status.HTTP_400_BAD_REQUEST)

        email = user_info.get('email')
        if not email:
            return Response({
                "success": False,
                "message": "Email not provided by Google account",
                "data": {}
            }, status=status.HTTP_400_BAD_REQUEST)

        # Build username from Google name or email prefix
        google_name = user_info.get('name')
        username = google_name if google_name else email.split('@')[0]

        # 4. User Lifecycle: Create or fetch the user from database
        user = User.objects.filter(email=email).first()
        
        if user:
            if user.has_usable_password():
                import urllib.parse
                frontend_url = settings.FRONTEND_URL
                error_msg = urllib.parse.quote("This email is already associated with a standard account. Please log in using your email and password.")
                return redirect(f"{frontend_url}/auth/google/callback?error={error_msg}")
            
        else:
            user = User.objects.create(
                email=email,
                username=username,
                is_verified=True,
            )
            user.set_unusable_password()
            user.save()

        # 5. JWT Token Issuance (Production Standard)
        refresh = RefreshToken.for_user(user)

        # Redirect the user back to the frontend with the tokens
        frontend_url = settings.FRONTEND_URL
        
        import json
        import base64
        
        user_data = {
            'email': user.email,
            'username': user.username
        }
        user_data_b64 = base64.urlsafe_b64encode(json.dumps(user_data).encode()).decode()
        
        redirect_url = f"{frontend_url}/auth/google/callback?user={user_data_b64}"
        
        response = redirect(redirect_url)
        response.set_cookie(
            'access',
            str(refresh.access_token),
            max_age=int(settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds()),
            httponly=True,
            samesite='None' if not settings.DEBUG else 'Lax', secure=not settings.DEBUG
        )
        response.set_cookie(
            'refresh',
            str(refresh),
            max_age=int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()),
            httponly=True,
            samesite='None' if not settings.DEBUG else 'Lax', secure=not settings.DEBUG
        )
        return response

from rest_framework_simplejwt.views import TokenRefreshView

class CookieTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('refresh')
        if not refresh_token:
            return Response({
                "success": False,
                "message": "No refresh token provided.",
                "data": {}
            }, status=status.HTTP_401_UNAUTHORIZED)
        request.data['refresh'] = refresh_token
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 200:
            access_token = response.data.get('access')
            if access_token:
                response.set_cookie(
                    'access',
                    access_token,
                    max_age=int(settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds()),
                    httponly=True,
                    samesite='Lax', secure=not settings.DEBUG
                )
            # Remove tokens from JSON response
            if 'access' in response.data:
                del response.data['access']
            if 'refresh' in response.data:
                del response.data['refresh']
            
            response.data = {
                "message": "Token refreshed successfully.",
                "data": response.data
            }
        else:
            message = response.data.get("detail", "Token refresh failed.") if isinstance(response.data, dict) else "Token refresh failed."
            response.data = {
                "success": False,
                "message": message,
                "data": response.data
            }
                
        return response

class LogoutAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        from rest_framework_simplejwt.tokens import RefreshToken, TokenError
        response = Response({
            "message": "Successfully logged out.",
            "data": {}
        }, status=status.HTTP_200_OK)

        # 1. Grab the refresh token from the incoming cookie
        refresh_token = request.COOKIES.get('refresh')
        
        if refresh_token:
            try:
                # 2. Blacklist it in the database so it can never generate new access tokens
                token = RefreshToken(refresh_token)
                token.blacklist()
            except TokenError:
                # Token is already invalid/expired, skip safely
                pass

        # 3. Wipe the client-side cookies (make sure path/domain match your login settings)
        response.delete_cookie('access', samesite='None', path='/')
        response.delete_cookie('refresh', samesite='None', path='/')
        
        return response

import logging
from svix.webhooks import Webhook, WebhookVerificationError

logger = logging.getLogger(__name__)

class ResendWebhookView(APIView):
    """
    Handles incoming webhook events from Resend securely via Svix signatures.
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        payload = request.body
        headers = request.headers
        
        # Get the secret
        secret = getattr(settings, 'RESEND_WEBHOOK_SECRET', '')
        if not secret:
            logger.error("RESEND_WEBHOOK_SECRET is not configured.")
            return Response({"error": "Configuration error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        wh = Webhook(secret)
        
        try:
            event = wh.verify(payload, headers)
        except WebhookVerificationError as e:
            logger.warning(f"Webhook signature verification failed: {str(e)}")
            return Response({"error": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST)
        
        event_type = event.get('type')
        data = event.get('data', {})
        
        if event_type == 'email.bounced':
            bounce_data = data.get('bounce', {})
            if bounce_data.get('type') == 'Permanent':
                to_emails = data.get('to', [])
                if to_emails:
                    target_email = to_emails[0]
                    # Update database directly
                    updated_count = CustomUser.objects.filter(email=target_email).update(is_active=False)
                    if updated_count:
                        logger.info(f"Deactivated user {target_email} due to permanent bounce.")
                    else:
                        logger.info(f"Permanent bounce received for {target_email} but no user found.")

        elif event_type == 'email.delivery_delayed':
            to_emails = data.get('to', [])
            target_email = to_emails[0] if to_emails else 'Unknown'
            logger.warning(f"Email delivery delayed for {target_email}. Payload: {data}")
            
        # Always return 200 for verified requests to prevent infinite retries
        return Response({"status": "success"}, status=status.HTTP_200_OK)

class PresenceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .consumers import redis_client, PRESENCE_KEY
        online_users = list(redis_client.smembers(PRESENCE_KEY))
        # Convert to integers
        online_users = [int(uid) for uid in online_users if uid.isdigit()]
        return Response({
            "success": True,
            "message": "Fetched online users.",
            "data": online_users
        }, status=status.HTTP_200_OK)
