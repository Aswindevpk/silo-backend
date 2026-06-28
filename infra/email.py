import logging
import uuid
from apps.users.models import EmailVerificationToken, PasswordResetToken

logger = logging.getLogger(__name__)

class EmailManager:
    """
    Infrastructure service to manage sending system emails.
    Currently, it prints the tokens and actions instead of sending real emails.
    """

    @staticmethod
    def send_verification_email(user):
        """
        Creates/updates an EmailVerificationToken for the user,
        and prints/logs it (instead of sending a real email).
        """
        # Create or update the email verification token for the user.
        # Since the token field has default=uuid.uuid4, update_or_create needs
        # to explicitly set a new uuid on update if we want to regenerate it.
        token_obj, created = EmailVerificationToken.objects.update_or_create(
            user=user,
            defaults={'token': uuid.uuid4()}
        )

        message = (
            f"\n"
            f"========================================================================\n"
            f"EMAIL SIMULATION: Verification Email\n"
            f"To: {user.email}\n"
            f"User: {user.username}\n"
            f"Verification Link: http://localhost:8000/api/users/verify-email/?token={token_obj.token}\n"
            f"========================================================================"
        )
        print(message)
        logger.info(f"Verification token for {user.email}: {token_obj.token}")
        return token_obj

    @staticmethod
    def send_password_reset_email(user):
        """
        Creates/updates a PasswordResetToken for the user,
        and prints/logs it (instead of sending a real email).
        """
        token_obj, created = PasswordResetToken.objects.update_or_create(
            user=user,
            defaults={'token': uuid.uuid4()}
        )

        message = (
            f"\n"
            f"========================================================================\n"
            f"EMAIL SIMULATION: Password Reset Email\n"
            f"To: {user.email}\n"
            f"User: {user.username}\n"
            f"Reset Link: http://localhost:8000/api/users/reset-password/?token={token_obj.token}\n"
            f"========================================================================"
        )
        print(message)
        logger.info(f"Password reset token for {user.email}: {token_obj.token}")
        return token_obj
