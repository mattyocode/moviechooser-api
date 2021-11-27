from django.db import models

from accounts.models import CustomUser
from movies.models import Movie

# Create your models here.


class List(models.Model):
    owner = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="list"
    )
    name = models.CharField(max_length=32)
    added = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Item(models.Model):
    _list = models.ForeignKey(
        List, on_delete=models.CASCADE, related_name="list_item"
    )
    movie = models.ForeignKey(
        Movie, on_delete=models.CASCADE, related_name="movie_item"
    )
    watched = models.BooleanField(default=False)
    added = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.movie} on {self._list}"