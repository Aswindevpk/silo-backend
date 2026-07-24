from django.urls import path
from .views import CallSessionListCreateView, CallSessionAcceptView, CallSessionEndView, TurnCredentialsView

urlpatterns = [
    path('turn-credentials/', TurnCredentialsView.as_view(), name='turn-credentials'),
    path('workspaces/<slug:workspace_slug>/calls/', CallSessionListCreateView.as_view(), name='call-list-create'),
    path('<int:session_id>/accept/', CallSessionAcceptView.as_view(), name='call-accept'),
    path('<int:session_id>/end/', CallSessionEndView.as_view(), name='call-end'),
]
