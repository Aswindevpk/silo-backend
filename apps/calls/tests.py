from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from apps.workspaces.models import Workspace, WorkspaceMember
from .models import CallSession

User = get_user_model()

class CallsTestCase(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="owner@silo.app", username="owner", password="password123")
        self.owner.is_verified = True
        self.owner.save()

        self.member = User.objects.create_user(email="member@silo.app", username="member", password="password123")
        self.member.is_verified = True
        self.member.save()
        
        self.workspace = Workspace.objects.create(name="Acme Corp", slug="acme", created_by=self.owner)
        WorkspaceMember.objects.create(workspace=self.workspace, user=self.owner, role=WorkspaceMember.Role.OWNER)
        WorkspaceMember.objects.create(workspace=self.workspace, user=self.member, role=WorkspaceMember.Role.MEMBER)

    def test_call_lifecycle(self):
        # 1. Start Call (Owner -> Member)
        self.client.force_authenticate(user=self.owner)
        url = reverse('call-list-create', kwargs={"workspace_slug": "acme"})
        response = self.client.post(url, {"receiver_email": "member@silo.app"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        session_id = response.data['id']
        
        session = CallSession.objects.get(id=session_id)
        self.assertEqual(session.status, CallSession.Status.RINGING)

        # 2. Accept Call (Member)
        self.client.force_authenticate(user=self.member)
        accept_url = reverse('call-accept', kwargs={"session_id": session_id})
        response = self.client.post(accept_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        session.refresh_from_db()
        self.assertEqual(session.status, CallSession.Status.CONNECTED)
        self.assertIsNotNone(session.started_at)

        # 3. End Call (Owner)
        self.client.force_authenticate(user=self.owner)
        end_url = reverse('call-end', kwargs={"session_id": session_id})
        response = self.client.post(end_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        session.refresh_from_db()
        self.assertEqual(session.status, CallSession.Status.COMPLETED)
        self.assertIsNotNone(session.ended_at)
