from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User

class Company(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    company_name = models.CharField(max_length=255)
    abn = models.CharField(max_length=50)
    address = models.TextField(blank=True)

    full_name = models.CharField(max_length=255)
    role = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.company_name