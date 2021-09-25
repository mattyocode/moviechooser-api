from django.contrib import admin

from .models import Movie

@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    fields = (
        "imdbid", "title", "rated", "released",
        "runtime", "writer", "plot", "language",
        "country", "poster_url", "type_field",
    )
    list_display = (
        "imdbid", "title", "rated", "released",
        "runtime", "writer", "plot", "language",
        "country", "poster_url", "type_field",
    )
    
