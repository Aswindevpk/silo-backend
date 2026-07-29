import uuid
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Workspace, WorkspaceMember, WorkspaceInvitation, Plan
from .serializers import WorkspaceSerializer, WorkspaceMemberSerializer, WorkspaceInvitationSerializer
from .permissions import IsWorkspaceMember, IsWorkspaceAdminOrOwner

def verify_member_limit_guard(workspace):
    if not workspace.plan or workspace.plan.slug == 'free':
        active_member_count = workspace.memberships.count()
        if active_member_count >= (workspace.plan.max_members if workspace.plan else 2):
            raise PermissionDenied(
                "This workspace has reached the limit of members allowed on the Free plan. "
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
        # Check how many free workspaces the user has created
        created_workspaces_count = Workspace.objects.filter(
            owner=request.user, 
            plan__slug='free'
        ).count()

        if created_workspaces_count >= 2:
            return Response(
                {"detail": "Free users can only create up to 2 workspaces. Please upgrade to create more."}, 
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = WorkspaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Fetch or create a default free plan
        free_plan, _ = Plan.objects.get_or_create(slug='free', defaults={'name': 'Free', 'max_members': 2})
        workspace = serializer.save(owner=request.user, plan=free_plan)
        
        # Check if user already has a default workspace
        has_default = WorkspaceMember.objects.filter(user=request.user, is_default=True).exists()

        # Creator automatically becomes the Owner
        WorkspaceMember.objects.create(
            workspace=workspace,
            user=request.user,
            role=WorkspaceMember.Role.OWNER,
            is_default=not has_default
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)

class WorkspaceMembersListView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsWorkspaceMember]

    def get(self, request, slug):
        workspace = get_object_or_404(Workspace, slug=slug)
        memberships = WorkspaceMember.objects.filter(workspace=workspace).select_related('user')
        serializer = WorkspaceMemberSerializer(memberships, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

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
        # auto_renew is no longer on the workspace schema
        return Response({
            "detail": "Autopay settings not supported in this schema yet.",
            "auto_renew": True
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
                workspace = Workspace.objects.filter(id=workspace_id).first()
                if workspace:
                    premium_plan, _ = Plan.objects.get_or_create(slug='premium', defaults={'name': 'Premium', 'price_monthly': 10})
                    workspace.plan = premium_plan
                    workspace.subscription_status = 'active'
                    workspace.stripe_subscription_id = data_obj.get('id')
                    workspace.stripe_customer_id = data_obj.get('customer')
                    workspace.save()
                    return Response({"detail": "Subscription activated successfully."}, status=status.HTTP_200_OK)

        elif event_type == 'customer.subscription.deleted':
            data_obj = payload.get('data', {}).get('object', {})
            sub_id = data_obj.get('id')
            if sub_id:
                workspace = Workspace.objects.filter(stripe_subscription_id=sub_id).first()
                if workspace:
                    free_plan, _ = Plan.objects.get_or_create(slug='free', defaults={'name': 'Free', 'max_members': 2})
                    workspace.plan = free_plan
                    workspace.subscription_status = 'canceled'
                    workspace.save()
                    return Response({"detail": "Subscription canceled successfully."}, status=status.HTTP_200_OK)

        return Response({"detail": "Webhook received but no action taken."}, status=status.HTTP_200_OK)

class SetDefaultWorkspaceView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsWorkspaceMember]

    def post(self, request, slug):
        workspace = get_object_or_404(Workspace, slug=slug)
        # Unset all other defaults
        WorkspaceMember.objects.filter(user=request.user).update(is_default=False)
        # Set new default
        member = WorkspaceMember.objects.get(workspace=workspace, user=request.user)
        member.is_default = True
        member.save()
        return Response({"detail": "Default workspace updated successfully."}, status=status.HTTP_200_OK)

class WorkspaceInvitationsListView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsWorkspaceMember]

    def get(self, request, slug):
        workspace = get_object_or_404(Workspace, slug=slug)
        invitations = WorkspaceInvitation.objects.filter(workspace=workspace, is_accepted=False)
        # Filter out expired in python or let them show but maybe annotate? We'll just serialize all pending.
        serializer = WorkspaceInvitationSerializer(invitations, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class DeleteWorkspaceInvitationView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsWorkspaceAdminOrOwner]

    def delete(self, request, slug, pk):
        workspace = get_object_or_404(Workspace, slug=slug)
        invitation = get_object_or_404(WorkspaceInvitation, workspace=workspace, id=pk)
        invitation.delete()
        return Response({"detail": "Invitation revoked."}, status=status.HTTP_204_NO_CONTENT)

class RemoveWorkspaceMemberView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsWorkspaceAdminOrOwner]

    def delete(self, request, slug, user_id):
        workspace = get_object_or_404(Workspace, slug=slug)
        
        # Don't allow removing oneself via this endpoint (or handle it with care)
        if str(request.user.id) == str(user_id):
            return Response({"detail": "You cannot remove yourself. Leave the workspace instead."}, status=status.HTTP_400_BAD_REQUEST)

        member = get_object_or_404(WorkspaceMember, workspace=workspace, user_id=user_id)
        if member.role == WorkspaceMember.Role.OWNER:
            return Response({"detail": "Cannot remove the workspace owner."}, status=status.HTTP_400_BAD_REQUEST)
        
        member.delete()
        return Response({"detail": "Member removed."}, status=status.HTTP_204_NO_CONTENT)
