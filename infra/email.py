import logging
import uuid
import resend
from django.conf import settings
from apps.users.models import EmailVerificationToken, PasswordResetToken

logger = logging.getLogger(__name__)

class EmailManager:
    """
    Infrastructure service to manage sending system emails using Resend.
    Falls back to printing if RESEND_API_KEY is not set.
    """

    @staticmethod
    def send_verification_email(user):
        """
        Creates/updates an EmailVerificationToken for the user,
        and sends a real email if configured, otherwise prints it.
        """
        # Create or update the email verification token for the user.
        # Since the token field has default=uuid.uuid4, update_or_create needs
        # to explicitly set a new uuid on update if we want to regenerate it.
        token_obj, created = EmailVerificationToken.objects.update_or_create(
            user=user,
            defaults={'token': uuid.uuid4()}
        )

        verification_link = f"{settings.FRONTEND_URL}/register/verify-email/?token={token_obj.token}"


        resend.api_key = settings.RESEND_API_KEY
        try:
            resend.Emails.send({
                "from": "Silo <noreply@silo.aswindev.in>",
                "to": user.email,
                "subject": "Verify your email",
                "html": f"<p>Please verify your email by clicking <a href='{verification_link}'>here</a>.</p>"
            })
            logger.info(f"Verification email sent to {user.email}")
        except Exception as e:
            logger.error(f"Failed to send verification email to {user.email}: {e}")

        message = (
                f"\n"
                f"========================================================================\n"
                f"EMAIL SIMULATION: Verification Email\n"
                f"To: {user.email}\n"
                f"User: {user.username}\n"
                f"Verification Link: {verification_link}\n"
                f"========================================================================"
            )
        print(message)
        logger.info(f"Verification token for {user.email}: {token_obj.token}")
            
        return token_obj

    @staticmethod
    def send_password_reset_email(user):
        """
        Creates/updates a PasswordResetToken for the user,
        and sends a real email if configured, otherwise prints it.
        """
        token_obj, created = PasswordResetToken.objects.update_or_create(
            user=user,
            defaults={'token': uuid.uuid4()}
        )

        reset_link = f"{settings.FRONTEND_URL}/reset-password/?token={token_obj.token}"

        resend.api_key = settings.RESEND_API_KEY
        try:
            resend.Emails.send({
                "from": "Silo <noreply@silo.aswindev.in>",
                "to": user.email,
                "subject": "Reset your password",
                "html": f"<p>Please reset your password by clicking <a href='{reset_link}'>here</a>.</p>"
                })
            logger.info(f"Password reset email sent to {user.email}")
        except Exception as e:
            logger.error(f"Failed to send password reset email to {user.email}: {e}")

        message = (
                f"\n"
                f"========================================================================\n"
                f"EMAIL SIMULATION: Password Reset Email\n"
                f"To: {user.email}\n"
                f"User: {user.username}\n"
                f"Reset Link: {reset_link}\n"
                f"========================================================================"
            )
        print(message)
        logger.info(f"Password reset token for {user.email}: {token_obj.token}")
            
        return token_obj
