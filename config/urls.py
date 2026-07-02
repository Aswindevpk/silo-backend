from django.contrib import admin
from django.urls import path, include
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/users/', include('apps.users.urls')),
    path('api/workspaces/', include('apps.workspaces.urls')),
    path('api/chats/', include('apps.chats.urls')),
    path('api/calls/', include('apps.calls.urls')),
]

if 'silk' in settings.INSTALLED_APPS:
    urlpatterns += [
        path('silk/', include('silk.urls', namespace='silk')),
    ]

if 'drf_spectacular' in settings.INSTALLED_APPS:
    from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
    urlpatterns += [
        # This downloads the raw schema file (YAML or JSON)
        path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
        # This gives you an interactive web UI (Swagger) to look at it locally
        path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    ]
