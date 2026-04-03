"""
WSGI config for ProDrive SMS Builder project.
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prodrive.settings')

application = get_wsgi_application()
