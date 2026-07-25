import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.users.views import StandardLoginView
from rest_framework.test import APIRequestFactory
import traceback

factory = APIRequestFactory()
request = factory.post('/api/v1/users/login/', {'email': 'aswin@example.com', 'password': 'password123'}, format='json')

view = StandardLoginView.as_view()
def custom_handle(self, exc):
    import traceback
    with open('error_trace.txt', 'w') as f:
        traceback.print_exc(file=f)
    raise exc
StandardLoginView.handle_exception = custom_handle

try:
    response = view(request)
except Exception:
    pass

with open('error_trace.txt', 'r') as f:
    print(f.read())
