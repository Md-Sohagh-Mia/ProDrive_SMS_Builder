"""
URL configuration for the ProDrive SMS Builder project.
"""

from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/', include('auth_system.urls', namespace='auth_system')),
    # Redirect root to the login page
    path('', RedirectView.as_view(url='/auth/login/', permanent=False)),
]
