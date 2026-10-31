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
    list_display = (
        "movie",
        "source",
        "model_name",
        "has_premise_embedding",
        "updated_at",
    )
    list_filter = ("source", "model_name")
    list_select_related = ("movie",)
    search_fields = ("movie__imdbid", "movie__title")
    exclude = ("embedding", "premise_embedding")

    @admin.display(boolean=True, description="premise")
    def has_premise_embedding(self, obj):
        return obj.premise_embedding is not None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
