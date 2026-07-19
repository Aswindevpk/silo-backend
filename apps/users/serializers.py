import re
import dns.resolver
from disposable_email_domains import blocklist
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import CustomUser
from rest_framework import status
from utils.exceptions import CustomAPIException

class RegisterSerializer(serializers.Serializer):
    """Serializer for user registration"""
    username = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        """Validate that the username and email are unique and formatted correctly"""
        conflict_errors = {}
        validation_errors = {}

        if CustomUser.objects.filter(username=attrs.get('username')).exists():
            conflict_errors['username'] = ["Username already exists"]
        if CustomUser.objects.filter(email=attrs.get('email')).exists():
            conflict_errors['email'] = ["Email already exists"]
            
        email = attrs.get('email', '')
        if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
            validation_errors['email'] = ["Invalid email address"]
        else:
            domain = email.split('@')[-1].lower()
            if domain in blocklist:
                if 'email' not in validation_errors:
                    validation_errors['email'] = []
                validation_errors['email'].append("Disposable or temporary emails are strictly prohibited.")
            else:
                try:
                    dns.resolver.resolve(domain, 'MX')
                except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.Timeout):
                    if 'email' not in validation_errors:
                        validation_errors['email'] = []
                    validation_errors['email'].append("This email domain does not exist or cannot receive mail.")
                
        if not re.match(r"^[a-zA-Z0-9]+$", attrs.get('username', '')):
            validation_errors['username'] = ["Invalid username"]    
        try:
            # We construct a temporary user instance to let UserAttributeSimilarityValidator do its job if needed
            temp_user = CustomUser(username=attrs.get('username'), email=attrs.get('email'))
            validate_password(attrs.get('password'), user=temp_user)
        except DjangoValidationError as e:
            validation_errors['password'] = list(e.messages)
        
        if conflict_errors:
            raise CustomAPIException(
                message="User already exists.",
                errors=conflict_errors,
                status_code=status.HTTP_409_CONFLICT
            )
            
        if validation_errors:
            raise CustomAPIException(
                message="Input validation failed.",
                errors=validation_errors,
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
            )
            
        return attrs
    
    def create(self, validated_data):
        """Create a new user"""
        user = CustomUser.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        return user


class ResendVerificationEmailSerializer(serializers.Serializer):
    """Serializer for resending verification email"""
    email = serializers.EmailField()

    def validate_email(self, value):
        if not CustomUser.objects.filter(email=value).exists():
            raise CustomAPIException(
                message="User with this email does not exist.",
                errors={"email": ["User with this email does not exist."]},
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
            )
        return value


class ForgotPasswordSerializer(serializers.Serializer):
    """Serializer for requesting password reset"""
    email = serializers.EmailField()

    def is_valid(self, *, raise_exception=False):
        valid = super().is_valid(raise_exception=False)
        if not valid and raise_exception:
            raise CustomAPIException(
                message="Invalid email address.",
                errors=self.errors,
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
            )
        return valid




class ResetPasswordSerializer(serializers.Serializer):
    """Serializer for resetting user password"""
    token = serializers.UUIDField()
    password = serializers.CharField(write_only=True, min_length=8)

    def is_valid(self, *, raise_exception=False):
        valid = super().is_valid(raise_exception=False)
        if not valid and raise_exception:
            raise CustomAPIException(
                message="Invalid token or password.",
                errors=self.errors,
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
            )
        return valid


class LoginSerializer(serializers.Serializer):
    """Serializer for manual login authentication"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


from google.oauth2 import id_token
from django.conf import settings

class GoogleLoginSerializer(serializers.Serializer):
    """Serializer for Google OAuth ID Token validation"""
    id_token = serializers.CharField()

    def validate_id_token(self, value):
        from google.auth.transport import requests
        try:
            # Verify the token against Google's servers
            id_info = id_token.verify_oauth2_token(
                value,
                requests.Request(),
                settings.GOOGLE_OAUTH2_CLIENT_ID
            )

            # Ensure token issuer is Google
            if id_info['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise serializers.ValidationError('Wrong token issuer.')

            return id_info
        except Exception as e:
            raise serializers.ValidationError(f'Invalid Google Token: {str(e)}')
