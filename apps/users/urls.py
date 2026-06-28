from django.urls import path
from rest_framework_simplejwt.views import (
    TokenRefreshView,
)
from .views import (
    RegisterAPIView,
    VerifyEmailAPIView,
    ResendVerificationEmailAPIView,
    ForgotPasswordAPIView,
    ResetPasswordAPIView,
    LoginAPIView,
)

urlpatterns = [
    path('register/', RegisterAPIView.as_view(), name='register'),
    path('register/verify-email/', VerifyEmailAPIView.as_view(), name='verify-email'),
    path('register/resend-verification-email/', ResendVerificationEmailAPIView.as_view(), name='resend-verification-email'),
    path('forgot-password/', ForgotPasswordAPIView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordAPIView.as_view(), name='reset-password'),
    path('login/', LoginAPIView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
]
