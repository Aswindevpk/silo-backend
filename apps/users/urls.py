from django.urls import path

from .views import (
    RegisterAPIView,
    VerifyEmailAPIView,
    ResendVerificationEmailAPIView,
    ForgotPasswordAPIView,
    ResetPasswordAPIView,
    StandardLoginView,
    GoogleLoginView,
    GoogleCallbackView,
    CookieTokenRefreshView,
    LogoutAPIView,
)

urlpatterns = [
    path('register/', RegisterAPIView.as_view(), name='register'),
    path('register/verify-email/', VerifyEmailAPIView.as_view(), name='verify-email'),
    path('register/resend-verification-email/', ResendVerificationEmailAPIView.as_view(), name='resend-verification-email'),
    path('forgot-password/', ForgotPasswordAPIView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordAPIView.as_view(), name='reset-password'),
    path('login/', StandardLoginView.as_view(), name='login'),
    path('token/refresh/', CookieTokenRefreshView.as_view(), name='token-refresh'),
    path('logout/', LogoutAPIView.as_view(), name='logout'),
    path('auth/google/login', GoogleLoginView.as_view(), name='google-login'),
    path('auth/google/callback', GoogleCallbackView.as_view(), name='google-callback'),
]
