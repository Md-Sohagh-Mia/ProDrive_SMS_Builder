from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(UserAdmin):
    """Admin interface for Customer management."""

    list_display = ('email', 'full_name', 'company_name', 'phone_number', 'is_active', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'date_joined')
    search_fields = ('email', 'username', 'full_name', 'company_name', 'abn')
    ordering = ('-date_joined',)
    readonly_fields = ('created_at', 'updated_at', 'date_joined', 'last_login')

    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'phone_number')}),
        ('Company Details', {'fields': ('company_name', 'abn', 'address', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'date_joined', 'created_at', 'updated_at')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'full_name', 'company_name', 'password1', 'password2'),
        }),
    )
