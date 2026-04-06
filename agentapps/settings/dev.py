from .common import * 
from django.core.management.utils import get_random_secret_key
import os

DEBUG = True


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', default=get_random_secret_key())

ALLOWED_HOSTS = ['127.0.0.1']


CSRF_TRUSTED_ORIGINS = ['http://127.0.0.1']

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('redis', 6379)],
        },
    },
}

SITE_PUBLIC_KEY = os.getenv('SITE_PUBLIC_KEY', default='6Ld')
SITE_PRIVATE_KEY = os.getenv('SITE_PRIVATE_KEY', default='6Ld')
 
DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': lambda request: True 
}
