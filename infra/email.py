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
    def get_base_html_template(content):
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600&display=swap" rel="stylesheet">
            <style>
                body {{
                    font-family: 'Poppins', sans-serif;
                    background-color: #ffffff;
                    margin: 0;
                    padding: 40px 20px;
                    color: #18181b;
                }}
                .container {{
                    max-width: 500px;
                    margin: 0 auto;
                    background-color: #ffffff;
                    border-radius: 12px;
                    padding: 40px 0;
                    text-align: center;
                }}
                .logo {{
                    margin-bottom: 32px;
                    text-align: center;
                }}
                .logo img {{
                    height: 40px;
                    width: auto;
                    display: block;
                    margin: 0 auto;
                }}
                .content h1 {{
                    font-size: 20px;
                    font-weight: 600;
                    margin-bottom: 16px;
                }}
                .content p {{
                    font-size: 14px;
                    line-height: 1.6;
                    color: #52525b;
                    margin-bottom: 24px;
                }}
                .btn {{
                    display: inline-block;
                    background-color: #2563eb;
                    color: #ffffff !important;
                    text-decoration: none;
                    font-weight: 500;
                    font-size: 14px;
                    padding: 12px 28px;
                    border-radius: 100px;
                    margin-bottom: 32px;
                }}
                .footer {{
                    margin-top: 32px;
                    padding-top: 24px;
                    border-top: 1px solid #e4e4e7;
                    font-size: 12px;
                    color: #a1a1aa;
                    text-align: left;
                    line-height: 1.5;
                }}
                .footer a {{
                    color: #2563eb;
                    text-decoration: none;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="logo">
                    <img src="https://silo.aswindev.in/silo.png" alt="Silo Logo">
                </div>
                <div class="content">
                    {content}
                </div>
                <div class="footer">
                    If you did not initiate this request, please contact us at <a href="mailto:support@silo.aswindev.in">support@silo.aswindev.in</a><br><br>
                    Thanks,<br>
                    The Silo Team<br><br>
                    © 2026 Silo
                </div>
            </div>
        </body>
        </html>
        """

    @staticmethod
    def send_verification_email(user):
        """
        Creates/updates an EmailVerificationToken for the user,
        and sends a real email if configured, otherwise prints it.
        """
        token_obj, created = EmailVerificationToken.objects.update_or_create(
            user=user,
            defaults={'token': uuid.uuid4()}
        )

        verification_link = f"{settings.FRONTEND_URL}/register/verify-email/?token={token_obj.token}"

        content = f"""
            <h1>Hi {user.username},</h1>
            <p>Welcome to Silo! We are delighted to have you join our community.</p>
            <p>To get started and unlock all features, please verify your email address by clicking the button below.</p>
            <a href="{verification_link}" class="btn">Verify Email</a>
        """
        html_content = EmailManager.get_base_html_template(content)

        resend.api_key = settings.RESEND_API_KEY
        try:
            resend.Emails.send({
                "from": "Silo <noreply@silo.aswindev.in>",
                "to": user.email,
                "subject": "Verify your email",
                "html": html_content
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

        content = f"""
            <h1>Hi {user.username},</h1>
            <p>Need to reset password? No problem. Just click the button below to choose a new one.</p>
            <a href="{reset_link}" class="btn">Reset password</a>
        """
        html_content = EmailManager.get_base_html_template(content)

        resend.api_key = settings.RESEND_API_KEY
        try:
            resend.Emails.send({
                "from": "Silo <noreply@silo.aswindev.in>",
                "to": user.email,
                "subject": "Reset your password",
                "html": html_content
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
