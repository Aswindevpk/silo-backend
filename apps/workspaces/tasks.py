import logging
from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from infra.email import EmailManager
from .models import WorkspaceMember

logger = logging.getLogger(__name__)

@shared_task(acks_late=True)
def send_workspace_invitation_email_task(invitation_id):
    try:
        invitation = WorkspaceMember.objects.get(id=invitation_id)
        EmailManager.send_workspace_invitation_email(invitation)
        logger.info(f"Workspace invitation email task completed for invitation {invitation_id}")
    except ObjectDoesNotExist:
        logger.error(f"Invitation {invitation_id} does not exist for email task")
    except Exception as e:
        logger.error(f"Error sending workspace invitation email for invitation {invitation_id}: {str(e)}")
        raise e
