from rest_framework import serializers
from .models import CustomUser

class RegisterSerializer(serializers.Serializer):
    """Serializer for user registration"""
    username = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        """Validate that the username and email are unique"""
        if CustomUser.objects.filter(username=attrs['username']).exists():
            raise serializers.ValidationError("Username already exists")
        if CustomUser.objects.filter(email=attrs['email']).exists():
            raise serializers.ValidationError("Email already exists")
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
            raise serializers.ValidationError("User with this email does not exist.")
        return value


class ForgotPasswordSerializer(serializers.Serializer):
    """Serializer for requesting password reset"""
    email = serializers.EmailField()

    def validate_email(self, value):
        if not CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email does not exist.")
        return value


class ResetPasswordSerializer(serializers.Serializer):
    """Serializer for resetting user password"""
    token = serializers.UUIDField()
    password = serializers.CharField(write_only=True, min_length=8)


class LoginSerializer(serializers.Serializer):
    """Serializer for manual login authentication"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
