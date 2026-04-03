"""
URL configuration for prodrive_sms project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
"""
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    # Root redirect to the login page
    path('', lambda request: redirect('accounts:login'), name='home'),
]
