from .base import *
import environ
import os

# Load environment variables from .env file
env = environ.Env()

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
    raise ValueError(f"CRITICAL ERROR: Missing required development environment variables: {', '.join(missing_vars)}")

SECRET_KEY = env('SECRET_KEY')

DEBUG = True

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME'),  
        'USER': env('DB_USER'),  
        'PASSWORD': env('DB_PASSWORD'), 
        'HOST': env('DB_HOST'),
        'PORT': env('DB_PORT', default='5432'),
    }
}


#static files directory in the project
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
    
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Dev-only Installed Apps
INSTALLED_APPS += [
    'drf_spectacular',
    'silk',
]

# Dev-only Middleware (prepend SilkyMiddleware)
MIDDLEWARE = [
    'silk.middleware.SilkyMiddleware',
] + MIDDLEWARE

# DRF Spectacular Configuration
REST_FRAMEWORK.update({
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
})

SPECTACULAR_SETTINGS = {
    'TITLE': 'Silo API',
    'DESCRIPTION': 'API for Silo application',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# Set exact origins to allow credentials (cookies) in dev
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS')

CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS')

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [env('REDIS_URL')],
        },
    },
}
