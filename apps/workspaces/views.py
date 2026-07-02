import uuid
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Workspace, WorkspaceMember, WorkspaceInvitation, WorkspaceSubscription
from .serializers import WorkspaceSerializer, WorkspaceMemberSerializer, WorkspaceInvitationSerializer, WorkspaceSubscriptionSerializer
from .permissions import IsWorkspaceMember, IsWorkspaceAdminOrOwner

def verify_member_limit_guard(workspace):
    try:
        sub = workspace.subscription
    except WorkspaceSubscription.DoesNotExist:
        sub = WorkspaceSubscription.objects.create(workspace=workspace, tier=WorkspaceSubscription.Tier.FREE)

    if not sub.is_premium():
        active_member_count = workspace.memberships.count()
        if active_member_count >= 2:
            raise PermissionDenied(
                "This workspace has reached the limit of 2 members allowed on the Free plan. "
                "Please upgrade your subscription to invite more members."
            )

class WorkspaceListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # List workspaces where user is a member
        memberships = WorkspaceMember.objects.filter(user=request.user)
        workspaces = [m.workspace for m in memberships]
        serializer = WorkspaceSerializer(workspaces, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = WorkspaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        workspace = serializer.save(created_by=request.user)
        
        # Creator automatically becomes the Owner
        WorkspaceMember.objects.create(
            workspace=workspace,
            user=request.user,
            role=WorkspaceMember.Role.OWNER
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class WorkspaceInviteView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsWorkspaceAdminOrOwner]

    def post(self, request, slug):
        workspace = get_object_or_404(Workspace, slug=slug)
        try:
            verify_member_limit_guard(workspace)
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

        serializer = WorkspaceInvitationSerializer(data=request.data, context={'workspace': workspace})
        serializer.is_valid(raise_exception=True)
        invitation = serializer.save(workspace=workspace, invited_by=request.user)

        return Response({
            "detail": "Invitation created successfully.",
            "token": str(invitation.token)
        }, status=status.HTTP_201_CREATED)

class WorkspaceAcceptInviteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        token = request.data.get('token')
        if not token:
            return Response({"detail": "Token is required."}, status=status.HTTP_400_BAD_REQUEST)

        inv = WorkspaceInvitation.objects.filter(token=token, is_accepted=False).first()
        if not inv or inv.is_expired():
            return Response({"detail": "Invalid or expired invitation token."}, status=status.HTTP_400_BAD_REQUEST)

        member, created = WorkspaceMember.objects.get_or_create(
            workspace=inv.workspace,
            user=request.user,
            defaults={'role': inv.role}
        )

        inv.is_accepted = True
        inv.accepted_by = request.user
        inv.save()

        return Response({
            "detail": f"Successfully joined workspace '{inv.workspace.name}'.",
            "role": member.role
        }, status=status.HTTP_200_OK)

class ToggleAutopayView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsWorkspaceAdminOrOwner]

    def post(self, request, slug):
        workspace = get_object_or_404(Workspace, slug=slug)
        sub = workspace.subscription
        sub.auto_renew = not sub.auto_renew
        sub.save()
        return Response({
            "detail": "Autopay settings updated.",
            "auto_renew": sub.auto_renew
        }, status=status.HTTP_200_OK)

class CreateCheckoutSessionView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsWorkspaceAdminOrOwner]

    def post(self, request, slug):
        workspace = get_object_or_404(Workspace, slug=slug)
        checkout_url = f"https://checkout.stripe.com/pay/mock_session_{uuid.uuid4()}"
        return Response({
            "detail": "Mock checkout session created.",
            "checkout_url": checkout_url
        }, status=status.HTTP_200_OK)

@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        payload = request.data
        event_type = payload.get('type')

        if event_type == 'customer.subscription.created':
            data_obj = payload.get('data', {}).get('object', {})
            metadata = data_obj.get('metadata', {})
            workspace_id = metadata.get('workspace_id')
            if workspace_id:
                sub = WorkspaceSubscription.objects.filter(workspace_id=workspace_id).first()
                if sub:
                    sub.tier = WorkspaceSubscription.Tier.PREMIUM
                    sub.status = WorkspaceSubscription.Status.ACTIVE
                    sub.stripe_subscription_id = data_obj.get('id')
                    sub.stripe_customer_id = data_obj.get('customer')
                    sub.save()
                    return Response({"detail": "Subscription activated successfully."}, status=status.HTTP_200_OK)

        elif event_type == 'customer.subscription.deleted':
            data_obj = payload.get('data', {}).get('object', {})
            sub_id = data_obj.get('id')
            if sub_id:
                sub = WorkspaceSubscription.objects.filter(stripe_subscription_id=sub_id).first()
                if sub:
                    sub.tier = WorkspaceSubscription.Tier.FREE
                    sub.status = WorkspaceSubscription.Status.CANCELED
                    sub.save()
                    return Response({"detail": "Subscription canceled successfully."}, status=status.HTTP_200_OK)

        return Response({"detail": "Webhook received but no action taken."}, status=status.HTTP_200_OK)
