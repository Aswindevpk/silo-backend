import os
from pathlib import Path
from .base import *
import environ

# 1. Load the production environment variables
env = environ.Env()

# Prevent silent failures by enforcing required production environment variables
REQUIRED_ENV_VARS = [
    'SECRET_KEY',
    'DB_NAME',
    'DB_USER',
    'DB_PASSWORD',
    'DB_HOST',
    'REDIS_URL',
    'ALLOWED_HOSTS',
    'CORS_ALLOWED_ORIGINS',
    'CSRF_TRUSTED_ORIGINS',
]

missing_vars = [var for var in REQUIRED_ENV_VARS if not os.environ.get(var)]
if missing_vars:
    raise ValueError(f"CRITICAL ERROR: Missing required production environment variables: {', '.join(missing_vars)}")


SECRET_KEY = env('SECRET_KEY')

# Absolute security imperative for production
DEBUG = False

# Explicitly define your domain variants via environment variables.
# Format in .env: ALLOWED_HOSTS=silo-api.aswindev.in,api.example.com
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

# Format in .env: CORS_ALLOWED_ORIGINS=https://silo.aswindev.in,https://example.com
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS')

# If you are passing HTTP cookies or Authorization headers:
CORS_ALLOW_CREDENTIALS = True

# Format in .env: CSRF_TRUSTED_ORIGINS=https://silo.aswindev.in,https://silo-api.aswindev.in
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS')

# 2. --- PRODUCTION DATABASE (PostgreSQL Required)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME'),  
        'USER': env('DB_USER'),  
        'PASSWORD': env('DB_PASSWORD'), 
        'HOST': env('DB_HOST'),
        'PORT': env('DB_PORT', default='5432'),
        # Performance optimization: Keeps database connections alive
        'CONN_MAX_AGE': 600, 
    }
}

#Redis Configuration
REDIS_URL = env('REDIS_URL')

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
            # Production connection tuning
            "symmetric_encryption_keys": [env("SECRET_KEY")],
            "capacity": 1500,  # Max messages per channel before dropping
            "expiry": 60,      # Seconds a message lives in a channel
        },
    },
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

