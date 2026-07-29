from django.urls import path
from .views import (
    WorkspaceListCreateView,
    WorkspaceMembersListView,
    WorkspaceInviteView,
    WorkspaceAcceptInviteView,
    ToggleAutopayView,
    CreateCheckoutSessionView,
    StripeWebhookView,
    SetDefaultWorkspaceView,
    WorkspaceInvitationsListView,
    DeleteWorkspaceInvitationView,
    RemoveWorkspaceMemberView,
)

urlpatterns = [
    path('', WorkspaceListCreateView.as_view(), name='workspace-list-create'),
    path('<slug:slug>/set-default/', SetDefaultWorkspaceView.as_view(), name='workspace-set-default'),
    path('<slug:slug>/members/', WorkspaceMembersListView.as_view(), name='workspace-members'),
    path('<slug:slug>/members/<int:user_id>/', RemoveWorkspaceMemberView.as_view(), name='workspace-member-remove'),
    path('<slug:slug>/invite/', WorkspaceInviteView.as_view(), name='workspace-invite'),
    path('<slug:slug>/invitations/', WorkspaceInvitationsListView.as_view(), name='workspace-invitations'),
    path('<slug:slug>/invitations/<int:pk>/', DeleteWorkspaceInvitationView.as_view(), name='workspace-invitation-delete'),
    path('accept-invite/', WorkspaceAcceptInviteView.as_view(), name='workspace-accept-invite'),
    path('<slug:slug>/toggle-autopay/', ToggleAutopayView.as_view(), name='workspace-toggle-autopay'),
    path('<slug:slug>/checkout/', CreateCheckoutSessionView.as_view(), name='workspace-checkout'),
    path('webhook/', StripeWebhookView.as_view(), name='stripe-webhook'),
]
