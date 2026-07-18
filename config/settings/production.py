import os
from pathlib import Path
from .base import *
import environ


# 1. Load the production environment variables
env = environ.Env()

# Read the deployment SECRET_KEY (Fails explicitly if missing)
SECRET_KEY = env('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("CRITICAL: SECRET_KEY environment variable is missing on this production node!")

# Absolute security imperative for production
DEBUG = False

# Explicitly define your domain variants. Never leave a wildcard '*' active here.
ALLOWED_HOSTS = ['silo-api.aswindev.in']

CORS_ALLOWED_ORIGINS = [
    'https://silo.aswindev.in',
]
# If you are passing HTTP cookies or Authorization headers:
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    'https://silo.aswindev.in',      # Your React app
    'https://silo-api.aswindev.in',  # Your Django backend itself (for Admin/Forms)
]

# 2. --- DYNAMIC DATABASE SWITCHER (PSQL vs SQLITE) ---
if env('DB_NAME'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': env('DB_NAME'),  
            'USER': env('DB_USER'),  
            'PASSWORD': env('DB_PASSWORD'), 
            'HOST': env('DB_HOST', '127.0.0.1'),
            'PORT': env('DB_PORT', '5432'),
            # Performance optimization: Keeps database connections alive
            'CONN_MAX_AGE': 600, 
        }
    }
else:
    # Safe fallback to local SQLite if PostgreSQL env variables are absent
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# 3. --- BARE-METAL LOCAL STORAGE (Nginx Direct Handshake) ---
# No S3. Django will store files directly on your server's SSD inside the project root.
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# 4. --- PRODUCTION HTTP & GATEWAY SECURITY HARDENING ---
# Tells Django to look for the header Nginx sends to confirm the transmission was secure
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True

# Cookie Security (Prevent Session hijacking over public connections)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# HTTP Strict Transport Security (HSTS Rules)
SECURE_HSTS_SECONDS = 31536000  # 1 Full Year
SECURE_HSTS_PRELOAD = True
SECURE_HSTS_INCLUDE_SUBDOMAINS = True


# 5. --- LOGGING ENGINE ARCHITECTURE ---
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'production_errors.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': True,
        },
    },
}

# Production Redis URL structure: redis://:password@host:port/db_number
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
            # Production connection tuning
            "symmetric_encryption_keys": [os.getenv("SECRET_KEY")],
            "capacity": 1500,  # Max messages per channel before dropping
            "expiry": 60,      # Seconds a message lives in a channel
        },
    },
}