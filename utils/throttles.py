from rest_framework.throttling import UserRateThrottle

class TierBasedRateThrottle(UserRateThrottle):
    def allow_request(self, request, view):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            self.rate = '1000000/hour'
        else:
            # Check if user is part of any premium workspace
            # This provides higher limits for users associated with premium workspaces
            is_premium = user.workspace_memberships.filter(
                workspace__plan__slug='premium'
            ).exists()
            
            if is_premium:
                self.rate = '1000/hour'
            else:
                self.rate = '100/hour'
                
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)
