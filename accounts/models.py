from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class CustomerManager(BaseUserManager):
    """Custom manager for the Customer model using email as the unique identifier."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field is required')
        email = self.normalize_email(email)
        extra_fields.setdefault('is_active', True)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self.create_user(email, password, **extra_fields)


class Customer(AbstractBaseUser, PermissionsMixin):
    """
    Customer user model for the ProDrive SMS Builder portal.

    Uses email as the primary login identifier.  Additional company and
    contact details are stored alongside the standard Django auth fields.
    """

    email = models.EmailField(unique=True, db_index=True)
    username = models.CharField(max_length=150, unique=True)

    # Personal details
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=30, blank=True)

    # Company details
    company_name = models.CharField(max_length=255)
    abn = models.CharField(max_length=20, blank=True, verbose_name='ABN')
    address = models.CharField(max_length=500, blank=True)
    role = models.CharField(max_length=150, blank=True, help_text='Job title / position at the company')

    # Status & timestamps
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomerManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'full_name', 'company_name']

    class Meta:
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.full_name} <{self.email}>'

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.full_name.split()[0] if self.full_name else self.email
