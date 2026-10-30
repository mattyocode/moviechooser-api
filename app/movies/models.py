from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from pgvector.django import HnswIndex, VectorField

from config.util import unique_slug

from .constants import ReviewSources


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
    title = models.CharField(max_length=500)
    slug = models.SlugField(max_length=32, null=True, blank=True, unique=True)
    rated = models.CharField(max_length=20, blank=True, null=True)
    released = models.DateField()
    runtime = models.IntegerField(null=True)
    genre = models.ManyToManyField(Genre, related_name="movie", blank=True)
    director = models.ManyToManyField(Director, related_name="movie", blank=True)
    writer = models.CharField(max_length=1500)
    actors = models.ManyToManyField(Actor, related_name="movie", blank=True)
    plot = models.CharField(max_length=1000, null=True)
    language = models.CharField(max_length=500, null=True)
    country = models.CharField(max_length=500, null=True)
    poster_url = models.CharField(max_length=200)
    type_field = models.CharField(
        db_column="type_", max_length=12, null=True, default="movie"
    )

    def __str__(self):
        return f"{self.title}"


@receiver(pre_save, sender=Movie)
def pre_save_receiver(sender, instance, *args, **kwargs):
    if not instance.slug:
        instance.slug = unique_slug(instance)


class OnDemand(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="ondemand")
    service = models.CharField(max_length=50)
    url = models.CharField(max_length=300)
    added = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.movie.imdbid + "--" + self.service


class Review(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="reviews")
    source = models.CharField(max_length=50, choices=ReviewSources.choices())
    score = models.IntegerField(null=False)

    def __str__(self):
        return self.source + "--" + str(self.score)


class PlotSource(models.TextChoices):
    WIKIPEDIA = "wikipedia"
    OMDB = "omdb", "OMDb"


class MoviePlot(models.Model):
    """Long-form plot text and its embedding. Search only: never serialize."""

    movie = models.OneToOneField(
        Movie, primary_key=True, on_delete=models.CASCADE, related_name="plot_data"
    )
    source = models.CharField(max_length=12, choices=PlotSource.choices)
    text = models.TextField()
    source_url = models.URLField(max_length=500)
    # enwiki lastrevid, for attribution and change detection. Null for OMDb.
    source_revid = models.BigIntegerField(null=True, blank=True)
    embedding = VectorField(dimensions=384, null=True, blank=True)
    model_name = models.CharField(max_length=100, blank=True)
    embedded_text_hash = models.CharField(max_length=64, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            HnswIndex(
                name="movieplot_embedding_hnsw",
                fields=["embedding"],
                opclasses=["vector_cosine_ops"],
                m=16,
                ef_construction=64,
            )
        ]

    def __str__(self):
        return f"{self.movie_id}--{self.source}"
