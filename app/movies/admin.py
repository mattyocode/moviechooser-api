from django.contrib import admin
from django.db.models import BooleanField, ExpressionWrapper, Q

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
    list_filter = ("source", "model_name", "premise_model_name")
    list_select_related = ("movie",)
    search_fields = ("movie__imdbid", "movie__title")
    exclude = ("embedding", "premise_embedding")

    def get_queryset(self, request):
        # The list shows neither vectors nor text, so don't fetch them per row.
        # The detail page loads the deferred text on access.
        return (
            super()
            .get_queryset(request)
            .defer("text", "embedding", "premise_embedding")
            .annotate(
                has_premise=ExpressionWrapper(
                    Q(premise_embedding__isnull=False), output_field=BooleanField()
                )
            )
        )

    @admin.display(boolean=True, description="premise", ordering="has_premise")
    def has_premise_embedding(self, obj):
        return obj.has_premise

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
