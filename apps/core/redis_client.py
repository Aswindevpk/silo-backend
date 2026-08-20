import redis
from django.conf import settings
import environ
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = environ.Env()
environ.Env.read_env(BASE_DIR / '.env')

try:
    redis_url = settings.REDIS_URL
except AttributeError:
    redis_url = env('REDIS_URL', default='redis://127.0.0.1:6379/0')

redis_client = redis.from_url(redis_url, decode_responses=True)
