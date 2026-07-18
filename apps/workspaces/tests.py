from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .models import Workspace, WorkspaceMember, WorkspaceInvitation, WorkspaceSubscription

User = get_user_model()

class WorkspaceTestCase(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="owner@silo.app", username="owner", password="password123")
        self.owner.is_verified = True
        self.owner.save()
        
        self.user2 = User.objects.create_user(email="user2@silo.app", username="user2", password="password123")
        self.user2.is_verified = True
        self.user2.save()
        
        self.user3 = User.objects.create_user(email="user3@silo.app", username="user3", password="password123")
        self.user3.is_verified = True
        self.user3.save()
        
        self.user4 = User.objects.create_user(email="user4@silo.app", username="user4", password="password123")
        self.user4.is_verified = True
        self.user4.save()

    def test_workspace_lifecycle(self):
        # 1. Create Workspace
        self.client.force_authenticate(user=self.owner)
        url = reverse('workspace-list-create')
        data = {"name": "Acme Corp", "slug": "acme"}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        workspace = Workspace.objects.get(slug="acme")
        self.assertEqual(workspace.name, "Acme Corp")
        
        # Verify signal created free subscription
        sub = workspace.subscription
        self.assertEqual(sub.tier, WorkspaceSubscription.Tier.FREE)
        
        # Verify owner membership
        membership = WorkspaceMember.objects.get(workspace=workspace, user=self.owner)
        self.assertEqual(membership.role, WorkspaceMember.Role.OWNER)

        # 2. Invite User 2 (Should succeed since total members = 1)
        invite_url = reverse('workspace-invite', kwargs={"slug": "acme"})
        response = self.client.post(invite_url, {"email": "user2@silo.app", "role": "MEMBER"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        token = response.data['token']

        # Accept invite as User 2
        self.client.force_authenticate(user=self.user2)
        accept_url = reverse('workspace-accept-invite')
        response = self.client.post(accept_url, {"token": token})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(WorkspaceMember.objects.filter(workspace=workspace, user=self.user2).exists())

        # 3. Try to invite User 3 (Should fail because total members = 2 and plan is FREE)
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(invite_url, {"email": "user3@silo.app", "role": "MEMBER"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("limit of 2 members", response.data['detail'])

        # 4. Trigger Webhook to upgrade workspace to PREMIUM
        webhook_url = reverse('stripe-webhook')
        webhook_data = {
            "type": "customer.subscription.created",
            "data": {
                "object": {
                    "id": "sub_12345",
                    "customer": "cus_12345",
                    "metadata": {
                        "workspace_id": str(workspace.id)
                    }
                }
            }
        }
        self.client.force_authenticate(user=None)  # Webhook is public
        response = self.client.post(webhook_url, webhook_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify upgraded
        sub.refresh_from_db()
        self.assertEqual(sub.tier, WorkspaceSubscription.Tier.PREMIUM)
        self.assertEqual(sub.stripe_subscription_id, "sub_12345")

        # 5. Invite User 3 (Should now succeed because plan is PREMIUM)
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(invite_url, {"email": "user3@silo.app", "role": "MEMBER"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
