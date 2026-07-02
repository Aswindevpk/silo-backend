from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from apps.workspaces.models import Workspace, WorkspaceMember
from .models import CallSession
from .serializers import CallSessionSerializer

User = get_user_model()

class CallSessionListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, workspace_slug):
        workspace = get_object_or_404(Workspace, slug=workspace_slug)
        if not WorkspaceMember.objects.filter(workspace=workspace, user=request.user).exists():
            return Response({"detail": "You are not a member of this workspace."}, status=status.HTTP_403_FORBIDDEN)

        calls = CallSession.objects.filter(workspace=workspace).filter(
            Q(caller=request.user) | Q(receiver=request.user)
        )
        serializer = CallSessionSerializer(calls, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, workspace_slug):
        workspace = get_object_or_404(Workspace, slug=workspace_slug)
        if not WorkspaceMember.objects.filter(workspace=workspace, user=request.user).exists():
            return Response({"detail": "You are not a member of this workspace."}, status=status.HTTP_403_FORBIDDEN)

        receiver_email = request.data.get('receiver_email')
        if not receiver_email:
            return Response({"detail": "receiver_email is required."}, status=status.HTTP_400_BAD_REQUEST)

        receiver = get_object_or_404(User, email=receiver_email)
        if not WorkspaceMember.objects.filter(workspace=workspace, user=receiver).exists():
            return Response({"detail": "Receiver is not a member of this workspace."}, status=status.HTTP_400_BAD_REQUEST)

        # Create session
        session = CallSession.objects.create(
            workspace=workspace,
            caller=request.user,
            receiver=receiver,
            status=CallSession.Status.RINGING
        )
        serializer = CallSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class CallSessionAcceptView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        session = get_object_or_404(CallSession, id=session_id)
        if session.receiver != request.user:
            return Response({"detail": "You are not the receiver of this call."}, status=status.HTTP_403_FORBIDDEN)

        if session.status != CallSession.Status.RINGING:
            return Response({"detail": "Call is not ringing."}, status=status.HTTP_400_BAD_REQUEST)

        session.status = CallSession.Status.CONNECTED
        session.started_at = timezone.now()
        session.save()

        serializer = CallSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_200_OK)

class CallSessionEndView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        session = get_object_or_404(CallSession, id=session_id)
        if request.user not in [session.caller, session.receiver]:
            return Response({"detail": "You are not a participant in this call."}, status=status.HTTP_403_FORBIDDEN)

        if session.status not in [CallSession.Status.RINGING, CallSession.Status.CONNECTED]:
            return Response({"detail": "Call is not active."}, status=status.HTTP_400_BAD_REQUEST)

        if session.status == CallSession.Status.RINGING:
            session.status = CallSession.Status.MISSED
            session.save()
        else:
            session.status = CallSession.Status.COMPLETED
            session.ended_at = timezone.now()
            if session.started_at:
                diff = session.ended_at - session.started_at
                session.duration_seconds = int(diff.total_seconds())
            session.save()

        serializer = CallSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_200_OK)
