from django.db import models

from accounts.models import CustomUser

# Create your models here.


class List(models.Model):
    owner = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="owner"
    )
    name = models.CharField(max_length=32)
    added = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
