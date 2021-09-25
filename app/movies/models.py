from django.db import models

class Genre(models.Model):
    name = models.CharField(unique=True, max_length=24)

    def __str__(self):
        return self.name

class Movie(models.Model):
    
    imdbid = models.CharField(max_length=20)
    title = models.CharField(max_length=200)
    rated = models.CharField(max_length=20, blank=True, null=True)
    released = models.DateField()
    runtime = models.IntegerField(null=True)
    # genre = models.ManyToManyField(Genre)
    # director = models.ManyToManyField(Director)
    writer = models.CharField(max_length=500)
    # actors = models.ManyToManyField(Actor)
    plot = models.CharField(max_length=500, null=True)
    language = models.CharField(max_length=40, null=True)
    country = models.CharField(max_length=40, null=True)
    poster_url = models.CharField(max_length=200)
    type_field = models.CharField(db_column='type_', max_length=12, null=True)

    def __str__(self):
        return f"{self.title}"

