"""
ASGI config for ProDrive SMS Builder project.
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prodrive.settings')

application = get_asgi_application()
