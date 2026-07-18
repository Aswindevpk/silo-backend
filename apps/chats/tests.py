from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from apps.workspaces.models import Workspace, WorkspaceMember
from .models import Channel, Topic, Reply

User = get_user_model()

class ChatsTestCase(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="owner@silo.app", username="owner", password="password123")
        self.owner.is_verified = True
        self.owner.save()

        self.member = User.objects.create_user(email="member@silo.app", username="member", password="password123")
        self.member.is_verified = True
        self.member.save()

        self.outsider = User.objects.create_user(email="outsider@silo.app", username="outsider", password="password123")
        self.outsider.is_verified = True
        self.outsider.save()
        
        self.workspace = Workspace.objects.create(name="Acme Corp", slug="acme", created_by=self.owner)
        WorkspaceMember.objects.create(workspace=self.workspace, user=self.owner, role=WorkspaceMember.Role.OWNER)
        self.member_membership = WorkspaceMember.objects.create(workspace=self.workspace, user=self.member, role=WorkspaceMember.Role.MEMBER)

    def test_channels_topics_replies(self):
        # 1. Create Public Channel (Owner)
        self.client.force_authenticate(user=self.owner)
        url = reverse('channel-list-create', kwargs={"workspace_slug": "acme"})
        response = self.client.post(url, {"name": "general", "is_private": False})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        channel = Channel.objects.get(name="general")

        # 2. Create Private Channel (Owner)
        response = self.client.post(url, {"name": "secret", "is_private": True})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        private_channel = Channel.objects.get(name="secret")

        # 3. List channels as Member (should see general but not secret)
        self.client.force_authenticate(user=self.member)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [ch['name'] for ch in response.data]
        self.assertIn("general", names)
        self.assertNotIn("secret", names)

        # 4. List channels as Outsider (should be blocked)
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # 5. Create Topic in public channel
        self.client.force_authenticate(user=self.member)
        topic_url = reverse('topic-list-create', kwargs={"channel_id": channel.id})
        response = self.client.post(topic_url, {"title": "Hello World", "content": "Initial topic post"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        topic = Topic.objects.get(title="Hello World")

        # 6. Post Reply in topic and check cache increments
        reply_url = reverse('reply-list-create', kwargs={"topic_id": topic.id})
        response = self.client.post(reply_url, {"content": "First reply"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        topic.refresh_from_db()
        self.assertEqual(topic.replies_count, 1)
        self.assertIsNotNone(topic.last_reply_at)
