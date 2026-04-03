from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator


class CustomerManager(BaseUserManager):
    """Custom manager for the Customer model."""

    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field is required.')
        if not username:
            raise ValueError('The Username field is required.')
        email = self.normalize_email(email)
        extra_fields.setdefault('is_active', True)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, username, password, **extra_fields)


phone_validator = RegexValidator(
    regex=r'^\+?1?\d{9,15}$',
    message='Enter a valid phone number (e.g. +61412345678).',
)


class Customer(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model for ProDrive customers.

    Uses email as the primary authentication identifier alongside username.
    """

    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        validators=[phone_validator],
    )
    company_name = models.CharField(max_length=255, blank=True)
    abn = models.CharField(max_length=20, blank=True, verbose_name='ABN')
    address = models.TextField(blank=True)
    role = models.CharField(max_length=100, blank=True, verbose_name='Role / Position')

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    # Login attempt tracking
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    last_failed_login = models.DateTimeField(null=True, blank=True)

    objects = CustomerManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        db_table = 'auth_customer'
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.email} ({self.company_name or self.username})'

    def get_full_name(self):
        return self.full_name or self.username

    def get_short_name(self):
        return self.full_name.split()[0] if self.full_name else self.username

    def record_failed_login(self):
        self.failed_login_attempts += 1
        self.last_failed_login = timezone.now()
        self.save(update_fields=['failed_login_attempts', 'last_failed_login'])

    def reset_failed_login(self):
        if self.failed_login_attempts > 0:
            self.failed_login_attempts = 0
            self.last_failed_login = None
            self.save(update_fields=['failed_login_attempts', 'last_failed_login'])
