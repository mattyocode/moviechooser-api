from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver

from config.util import unique_slug


class Actor(models.Model):
    name = models.CharField(unique=True, max_length=100)

    def __str__(self):
        return self.name


class Director(models.Model):
    name = models.CharField(unique=True, max_length=200)

    def __str__(self):
        return self.name


class Genre(models.Model):
    name = models.CharField(unique=True, max_length=24)

    def __str__(self):
        return self.name


class Movie(models.Model):
    imdbid = models.CharField(primary_key=True, unique=True, max_length=20)
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=32, null=True, blank=True, unique=True)
    rated = models.CharField(max_length=20, blank=True, null=True)
    released = models.DateField()
    runtime = models.IntegerField(null=True)
    genre = models.ManyToManyField(Genre, related_name='movie', blank=True)
    director = models.ManyToManyField(Director, related_name='movie', blank=True)
    writer = models.CharField(max_length=500)
    actors = models.ManyToManyField(Actor, related_name='movie', blank=True)
    plot = models.CharField(max_length=500, null=True)
    language = models.CharField(max_length=40, null=True)
    country = models.CharField(max_length=40, null=True)
    poster_url = models.CharField(max_length=200)
    type_field = models.CharField(db_column='type_', max_length=12, null=True)

    def __str__(self):
        return f"{self.title}"


@receiver(pre_save, sender=Movie)
def pre_save_receiver(sender, instance, *args, **kwargs):
    if not instance.slug:
        instance.slug = unique_slug(instance)


class OnDemand(models.Model):
    movie = models.ForeignKey(
        Movie, on_delete=models.CASCADE,
        related_name='ondemand'
    )
    service = models.CharField(max_length=50)
    url = models.CharField(max_length=300)
    added = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.movie.imdbid + "--" + self.service


class Review(models.Model):
    movie = models.ForeignKey(
        Movie, on_delete=models.CASCADE,
        related_name='review'
    )
    source = models.CharField(max_length=50)
    score = models.IntegerField(null=False)

    def __str__(self):
        return self.source + "--" + str(self.score)