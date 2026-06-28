from django.contrib.auth import get_user_model
from apps.users.models import CustomUser
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import RegisterSerializer, ResendVerificationEmailSerializer, ForgotPasswordSerializer, ResetPasswordSerializer, LoginSerializer, GoogleLoginSerializer
from rest_framework import status


class RegisterAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        from infra.email import EmailManager
        EmailManager.send_verification_email(user)
        return Response(
            {
                "detail": "Registration successful. Please check your email to verify your account."
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyEmailAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        token = request.query_params.get('token')
        if not token:
            return Response(
                {
                    "detail": "Token is required"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        from .models import EmailVerificationToken
        token_obj = EmailVerificationToken.objects.filter(token=token).first()
        if not token_obj:
            return Response(
                {
                    "detail": "Invalid token"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        if token_obj.is_expired():
            token_obj.delete()
            return Response({'detail': 'Invalid or expired token.'}, status=status.HTTP_400_BAD_REQUEST)

        user = token_obj.user
        user.is_verified = True
        user.save()
        token_obj.delete()
        return Response(
            {
                "detail": "Email verified successfully"
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
            return Response(
                {
                    "detail": "Email is already verified"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
            
        from infra.email import EmailManager
        EmailManager.send_verification_email(user)
        return Response(
            {
                "detail": "Verification email sent successfully"
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
        user = CustomUser.objects.get(email=email)
        from infra.email import EmailManager
        EmailManager.send_password_reset_email(user)
        return Response(
            {
                "detail": "Password reset email sent successfully"
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
            return Response(
                {
                    "detail": "Invalid token"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if token_obj.is_expired():
            token_obj.delete()
            return Response({'detail': 'Invalid or expired token.'}, status=status.HTTP_400_BAD_REQUEST)

        user = token_obj.user
        user.set_password(password)
        user.save()
        token_obj.delete()

        return Response(
            {
                "detail": "Password has been reset successfully"
            },
            status=status.HTTP_200_OK,
        )


from rest_framework_simplejwt.tokens import RefreshToken

class LoginAPIView(APIView):
    """Custom Login API View that returns tokens along with user information"""
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        user = CustomUser.objects.filter(email=email).first()


        if not user or not user.check_password(password):
            return Response(
                {"detail": "Unable to log in with provided credentials."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_verified :
            return Response(
                {"detail": "Email is not verified. Please verify your email to log in."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Generate tokens manually
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "username": user.username,
                    "email": user.email,
                }
            },
            status=status.HTTP_200_OK,
        )


from django.conf import settings

User = get_user_model()
import requests
class GoogleLoginView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        code = request.data.get('code')
        redirect_uri = request.data.get('redirect_uri', 'http://localhost:3000')
        if not code:
            return Response({"error": "Authorization code is required"}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Exchange authorization code for access token & ID token from Google
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
            return Response({"error": "Failed to exchange code with Google", "details": token_data}, status=status.HTTP_400_BAD_REQUEST)

        access_token = token_data.get('access_token')

        # 2. Use the token to fetch user profile info from Google
        user_info_url = "https://www.googleapis.com/oauth2/v3/userinfo"
        user_info_response = requests.get(user_info_url, headers={'Authorization': f'Bearer {access_token}'})
        user_info = user_info_response.json()

        if 'error' in user_info:
            return Response({"error": "Failed to fetch user info from Google"}, status=status.HTTP_400_BAD_REQUEST)

        email = user_info.get('email')
        if not email:
            return Response({"error": "Email not provided by Google account"}, status=status.HTTP_400_BAD_REQUEST)

        # Build username from Google name or email prefix
        google_name = user_info.get('name')
        username = google_name if google_name else email.split('@')[0]

        # 3. Create or fetch the user from database
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': username,
                'is_verified': True, # Email is verified by Google
            }
        )

        # 4. Generate local application JWT pair
        refresh = RefreshToken.for_user(user)

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'email': user.email,
                'username': user.username,
                'is_new': created
            }
        }, status=status.HTTP_200_OK)