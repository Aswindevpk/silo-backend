import os
from pathlib import Path
import environ
from celery import Celery

# Load .env file explicitly if it exists so we can grab DJANGO_SETTINGS_MODULE
env = environ.Env()
env_file = Path(__file__).resolve().parent.parent / '.env'
if env_file.exists():
    environ.Env.read_env(env_file)

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', env('DJANGO_SETTINGS_MODULE', default='config.settings.development'))

# Initialize Celery app
app = Celery('silo')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()
