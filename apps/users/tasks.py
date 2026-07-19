import logging
from celery import shared_task
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from infra.email import EmailManager

logger = logging.getLogger(__name__)
CustomUser = get_user_model()

@shared_task(acks_late=True)
def send_verification_email_task(user_id):
    try:
        user = CustomUser.objects.get(id=user_id)
        EmailManager.send_verification_email(user)
        logger.info(f"Verification email task completed for user {user_id}")
    except ObjectDoesNotExist:
        logger.error(f"User {user_id} does not exist for verification email task")
    except Exception as e:
        logger.error(f"Error sending verification email to user {user_id}: {str(e)}")
        raise e

@shared_task(acks_late=True)
def send_password_reset_email_task(user_id):
    try:
        user = CustomUser.objects.get(id=user_id)
        EmailManager.send_password_reset_email(user)
        logger.info(f"Password reset email task completed for user {user_id}")
    except ObjectDoesNotExist:
        logger.error(f"User {user_id} does not exist for password reset email task")
    except Exception as e:
        logger.error(f"Error sending password reset email to user {user_id}: {str(e)}")
        raise e
