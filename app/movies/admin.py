from django.contrib import admin

from .models import Movie, MoviePlot


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    fields = (
        "imdbid",
        "title",
        "rated",
        "released",
        "runtime",
        "writer",
        "plot",
        "language",
        "country",
        "poster_url",
        "type_field",
    )
    list_display = (
        "imdbid",
        "title",
        "rated",
        "released",
        "runtime",
        "writer",
        "plot",
        "language",
        "country",
        "poster_url",
        "type_field",
    )


@admin.register(MoviePlot)
class MoviePlotAdmin(admin.ModelAdmin):
    list_display = ("movie", "source", "model_name", "updated_at")
    list_filter = ("source", "model_name")
    search_fields = ("movie__imdbid", "movie__title")
    exclude = ("embedding",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
