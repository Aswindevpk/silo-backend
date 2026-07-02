from django.urls import path
from .views import (
    WorkspaceListCreateView,
    WorkspaceInviteView,
    WorkspaceAcceptInviteView,
    ToggleAutopayView,
    CreateCheckoutSessionView,
    StripeWebhookView,
)

urlpatterns = [
    path('', WorkspaceListCreateView.as_view(), name='workspace-list-create'),
    path('<slug:slug>/invite/', WorkspaceInviteView.as_view(), name='workspace-invite'),
    path('accept-invite/', WorkspaceAcceptInviteView.as_view(), name='workspace-accept-invite'),
    path('<slug:slug>/toggle-autopay/', ToggleAutopayView.as_view(), name='workspace-toggle-autopay'),
    path('<slug:slug>/checkout/', CreateCheckoutSessionView.as_view(), name='workspace-checkout'),
    path('webhook/', StripeWebhookView.as_view(), name='stripe-webhook'),
]
