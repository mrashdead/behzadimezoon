from .base import *

# production overrides - ensure you set secure values in env
DEBUG = False
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='').split(',') if config('ALLOWED_HOSTS', default='') else []

# recommended production hardening (examples)
SECURE_HSTS_SECONDS = 60
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = 'DENY'
