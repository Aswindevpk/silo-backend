from .base import *
import environ

# Load environment variables from .env file
env = environ.Env()

SECRET_KEY = env('SECRET_KEY')

DEBUG = True

ALLOWED_HOSTS = ['192.168.27.52','localhost','127.0.0.1','*']

if env('DB_NAME'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': env('DB_NAME'),  
            'USER': env('DB_USER'),  
            'PASSWORD': env('DB_PASSWORD'), 
            'HOST': env('DB_HOST'),
            'PORT': '5432',  
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
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
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://192.168.1.2:5173",
    "http://localhost:3000",
]

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": ["redis://127.0.0.1:6379/0"],
        },
    },
}
