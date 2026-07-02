from rest_framework import permissions
from .models import WorkspaceMember

class IsWorkspaceMember(permissions.BasePermission):
    """
    Allows access only to authenticated users who are members of the target workspace.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        workspace_id = view.kwargs.get('workspace_id') or view.kwargs.get('workspace_pk')
        workspace_slug = view.kwargs.get('workspace_slug') or view.kwargs.get('slug')
        
        if workspace_id:
            return WorkspaceMember.objects.filter(workspace_id=workspace_id, user=request.user).exists()
        if workspace_slug:
            return WorkspaceMember.objects.filter(workspace__slug=workspace_slug, user=request.user).exists()
            
        return True

class IsWorkspaceAdminOrOwner(permissions.BasePermission):
    """
    Allows access only to authenticated users who have ADMIN or OWNER roles in the target workspace.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        workspace_id = view.kwargs.get('workspace_id') or view.kwargs.get('workspace_pk')
        workspace_slug = view.kwargs.get('workspace_slug') or view.kwargs.get('slug')
        
        roles = [WorkspaceMember.Role.OWNER, WorkspaceMember.Role.ADMIN]
        if workspace_id:
            return WorkspaceMember.objects.filter(workspace_id=workspace_id, user=request.user, role__in=roles).exists()
        if workspace_slug:
            return WorkspaceMember.objects.filter(workspace__slug=workspace_slug, user=request.user, role__in=roles).exists()
            
        return True
