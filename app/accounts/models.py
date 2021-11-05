import uuid

from django.db import models
from django.contrib.auth.models import AbstractUser


class CustomUser(AbstractUser):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    email = models.EmailField(verbose_name="email", max_length=60, unique=True, default=None)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'password']