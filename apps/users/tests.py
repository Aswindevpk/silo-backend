import logging  # 1. Import logging
from unittest.mock import patch
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from apps.users.models import CustomUser, EmailVerificationToken, PasswordResetToken

# 2. Instantiate the logger
logger = logging.getLogger(__name__)

class RegisterAPITestCase(APITestCase):
    def setUp(self):
        # The URL name 'register' is used inside apps/users/urls.py
        self.register_url = reverse('register')
        self.resend_url = reverse('resend-verification-email')
        self.verify_url = reverse('verify-email')
        self.forgot_url = reverse('forgot-password')
        self.reset_url = reverse('reset-password')
        self.login_url = reverse('login')
        self.refresh_url = reverse('token-refresh')
        self.google_login_url = reverse('google-login')
        self.valid_payload = {
            'username': 'testuser',
            'email': 'testuser@example.com',
            'password': 'StrongPassword123'
        }

    def test_register_user_success(self):
        """Test successful user registration creates user and token"""
        logger.info("Starting test_register_user_success...")
        
        response = self.client.post(self.register_url, self.valid_payload, format='json')
        
        # 3. Log data to inspect response payloads or intermediate states
        logger.info(f"Response status: {response.status_code}")
        logger.info(f"Response data: {response.data}")
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data['detail'],
            "Registration successful. Please check your email to verify your account."
        )
        
        # Verify user was created in the database
        user_exists = CustomUser.objects.filter(email='testuser@example.com').exists()
        self.assertTrue(user_exists)
        
        user = CustomUser.objects.get(email='testuser@example.com')
        self.assertEqual(user.username, 'testuser')
        
        # Verify EmailVerificationToken was created
        token_exists = EmailVerificationToken.objects.filter(user=user).exists()
        self.assertTrue(token_exists)

        token = EmailVerificationToken.objects.get(user=user)
        
        # Log the generated token to ensure it's behaving correctly
        logger.info(f"Generated verification token in test database: {token.token}")

    def test_register_user_duplicate_email(self):
        """Test registration fails if email already exists"""
        # Create an existing user first
        CustomUser.objects.create_user(
            username='existinguser',
            email='testuser@example.com',
            password='Password123'
        )
        
        payload = self.valid_payload.copy()
        payload['username'] = 'differentusername'  # Only email is duplicate

        response = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Verify no new user was created
        self.assertFalse(CustomUser.objects.filter(username='differentusername').exists())

    def test_register_user_duplicate_username(self):
        """Test registration fails if username already exists"""
        CustomUser.objects.create_user(
            username='testuser',
            email='existinguser@example.com',
            password='Password123'
        )

        payload = self.valid_payload.copy()
        payload['email'] = 'differentemail@example.com'  # Only username is duplicate

        response = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_user_missing_fields(self):
        """Test registration fails when fields are missing"""
        payload = {
            'username': 'testuser'
            # email and password missing
        }
        response = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resend_verification_email_success(self):
        """Test successful request to resend verification email"""
        # Create user
        user = CustomUser.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='StrongPassword123'
        )
        response = self.client.post(self.resend_url, {'email': 'testuser@example.com'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['detail'], "Verification email sent successfully")
        
        # Verify token exists
        token_exists = EmailVerificationToken.objects.filter(user=user).exists()
        self.assertTrue(token_exists)

    def test_resend_verification_email_not_found(self):
        """Test resend verification email fails if user email does not exist"""
        response = self.client.post(self.resend_url, {'email': 'nonexistent@example.com'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_verify_email_success(self):
        """Test successful email verification sets is_verified=True and deletes token"""
        user = CustomUser.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='StrongPassword123'
        )
        # Create token
        token_obj = EmailVerificationToken.objects.create(user=user)
        
        response = self.client.get(f"{self.verify_url}?token={token_obj.token}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['detail'], "Email verified successfully")
        
        # Verify user is verified
        user.refresh_from_db()
        self.assertTrue(user.is_verified)
        
        # Verify token was deleted
        self.assertFalse(EmailVerificationToken.objects.filter(user=user).exists())

    def test_verify_email_missing_token(self):
        """Test verification fails if no token is provided"""
        response = self.client.get(self.verify_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], "Token is required")

    def test_verify_email_invalid_token(self):
        """Test verification fails if token is invalid"""
        import uuid
        response = self.client.get(f"{self.verify_url}?token={uuid.uuid4()}")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], "Invalid token")

    def test_verify_email_expired_token(self):
        """Test verification fails if token is expired"""
        from django.utils import timezone
        from datetime import timedelta
        user = CustomUser.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='StrongPassword123'
        )
        token_obj = EmailVerificationToken.objects.create(user=user)
        # Manually backdate the created_at timestamp to make it expired (>24 hours)
        token_obj.created_at = timezone.now() - timedelta(hours=25)
        token_obj.save()
        
        response = self.client.get(f"{self.verify_url}?token={token_obj.token}")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], "Invalid or expired token.")
        
        # Verify token was deleted
        self.assertFalse(EmailVerificationToken.objects.filter(user=user).exists())

    def test_forgot_password_success(self):
        """Test successful request to forgot password creates reset token"""
        user = CustomUser.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='StrongPassword123'
        )
        response = self.client.post(self.forgot_url, {'email': 'testuser@example.com'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['detail'], "Password reset email sent successfully")
        
        # Verify token exists
        token_exists = PasswordResetToken.objects.filter(user=user).exists()
        self.assertTrue(token_exists)

    def test_forgot_password_user_not_found(self):
        """Test forgot password fails if user email does not exist"""
        response = self.client.post(self.forgot_url, {'email': 'nonexistent@example.com'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_reset_password_success(self):
        """Test successful password reset changes user password and deletes token"""
        user = CustomUser.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='OldPassword123'
        )
        token_obj = PasswordResetToken.objects.create(user=user)
        
        payload = {
            'token': token_obj.token,
            'password': 'NewPassword123'
        }
        response = self.client.post(self.reset_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['detail'], "Password has been reset successfully")
        
        # Verify password changed
        user.refresh_from_db()
        self.assertTrue(user.check_password('NewPassword123'))
        
        # Verify token deleted
        self.assertFalse(PasswordResetToken.objects.filter(user=user).exists())

    def test_reset_password_invalid_token(self):
        """Test password reset fails with invalid token"""
        import uuid
        payload = {
            'token': uuid.uuid4(),
            'password': 'NewPassword123'
        }
        response = self.client.post(self.reset_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], "Invalid token")

    def test_reset_password_expired_token(self):
        """Test password reset fails with expired token"""
        from django.utils import timezone
        from datetime import timedelta
        user = CustomUser.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='OldPassword123'
        )
        token_obj = PasswordResetToken.objects.create(user=user)
        # Manually backdate to expire (>1 hour)
        token_obj.created_at = timezone.now() - timedelta(hours=2)
        token_obj.save()
        
        payload = {
            'token': token_obj.token,
            'password': 'NewPassword123'
        }
        response = self.client.post(self.reset_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], "Invalid or expired token.")
        
        # Verify token deleted
        self.assertFalse(PasswordResetToken.objects.filter(user=user).exists())

    def test_login_success(self):
        """Test successful login returns access and refresh tokens"""
        # Create user
        user = CustomUser.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='StrongPassword123'
        )
        user.is_verified = True
        user.save()
        payload = {
            'email': 'testuser@example.com',
            'password': 'StrongPassword123'
        }
        response = self.client.post(self.login_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_login_invalid_credentials(self):
        """Test login fails with incorrect password"""
        CustomUser.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='StrongPassword123'
        )
        payload = {
            'email': 'testuser@example.com',
            'password': 'WrongPassword123'
        }
        response = self.client.post(self.login_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_unverified_user(self):
        """Test login fails if user is not verified"""
        CustomUser.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='StrongPassword123'
        )
        payload = {
            'email': 'testuser@example.com',
            'password': 'StrongPassword123'
        }
        response = self.client.post(self.login_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['detail'], "Email is not verified. Please verify your email to log in.")

    def test_token_refresh_success(self):
        """Test successful token refresh returns new access token"""
        # Create user
        user = CustomUser.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='StrongPassword123'
        )
        user.is_verified = True
        user.save()
        # Login to get refresh token
        login_payload = {
            'email': 'testuser@example.com',
            'password': 'StrongPassword123'
        }
        login_response = self.client.post(self.login_url, login_payload, format='json')
        refresh_token = login_response.data['refresh']

        refresh_payload = {
            'refresh': refresh_token
        }
        response = self.client.post(self.refresh_url, refresh_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_token_refresh_invalid(self):
        """Test token refresh fails with invalid refresh token"""
        payload = {
            'refresh': 'invalid-refresh-token'
        }
        response = self.client.post(self.refresh_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('requests.post')
    @patch('requests.get')
    def test_google_login_success_new_user(self, mock_get, mock_post):
        """Test successful Google login creates a new user and returns JWT tokens"""
        # Mock token response
        mock_post.return_value.json.return_value = {
            'access_token': 'dummy_access_token',
        }
        # Mock user info response
        mock_get.return_value.json.return_value = {
            'email': 'googletest@example.com',
            'name': 'Google User',
        }

        payload = {'code': 'dummy_auth_code'}
        response = self.client.post(self.google_login_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['email'], 'googletest@example.com')
        self.assertEqual(response.data['user']['username'], 'Google User')

        # Verify user was created in the database
        user = CustomUser.objects.get(email='googletest@example.com')
        self.assertEqual(user.username, 'Google User')
        self.assertTrue(user.is_verified)

    @patch('requests.post')
    @patch('requests.get')
    def test_google_login_success_existing_user(self, mock_get, mock_post):
        """Test successful Google login with an existing user returns JWT tokens"""
        CustomUser.objects.create_user(
            username='Google User',
            email='googletest@example.com',
            password='Password123'
        )

        mock_post.return_value.json.return_value = {
            'access_token': 'dummy_access_token',
        }
        mock_get.return_value.json.return_value = {
            'email': 'googletest@example.com',
            'name': 'Google User',
        }

        payload = {'code': 'dummy_auth_code'}
        response = self.client.post(self.google_login_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

        # Ensure no duplicate user was created
        self.assertEqual(CustomUser.objects.filter(email='googletest@example.com').count(), 1)

    @patch('requests.post')
    def test_google_login_invalid_code(self, mock_post):
        """Test Google login fails when authorization code exchange fails"""
        mock_post.return_value.json.return_value = {
            'error': 'invalid_grant',
            'error_description': 'Bad Request'
        }

        payload = {'code': 'invalid_code'}
        response = self.client.post(self.google_login_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
