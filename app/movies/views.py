import random

from django.db.models import Avg, Count, FloatField
from django.db.models.expressions import (
    Exists,
    ExpressionWrapper,
    OuterRef,
    Value,
)
from django.http import Http404
from django.shortcuts import get_object_or_404
from pgvector.django import CosineDistance
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from lists.models import Item
from movies.utils import annotate_object_if_auth

from .filters import MovieFilter
from .models import Genre, Movie, MoviePlot
from .serializers import (
    GenreSerializer,
    MovieSerializer,
    SimilarMovieSerializer,
)


def annotate_on_list(movies_qs, user):
    """Add on_list: whether the movie is on one of the user's lists."""
    if user.is_authenticated:
        item = Item.objects.filter(movie=OuterRef("pk"), _list__owner=user)
        return movies_qs.annotate(on_list=Exists(item))
    return movies_qs.annotate(on_list=Value(False))


def meets_quality_bar(movies_qs):
    """Keep well-reviewed movies with a poster. Needs avg_rating annotated."""
    return movies_qs.filter(avg_rating__gte=40).exclude(poster_url="N/A")


class MovieList(ListAPIView):
    serializer_class = MovieSerializer
    filterset_class = MovieFilter

    def get_queryset(self):
        movies_qs = Movie.objects.annotate(avg_rating=Avg("reviews__score"))
        movies_qs = annotate_on_list(movies_qs, self.request.user)

        filterset = self.filterset_class(self.request.GET, queryset=movies_qs)

        return meets_quality_bar(filterset.qs.order_by("-avg_rating").distinct())


class MovieDetail(APIView):
    def get_object(self, slug):
        try:
            return Movie.objects.annotate(avg_rating=Avg("reviews__score")).get(
                slug=slug
            )
        except Movie.DoesNotExist:
            raise Http404

    def get(self, request, slug, format=None):
        movie = self.get_object(slug)
        movie = annotate_object_if_auth(request, movie)
        serializer = MovieSerializer(movie)
        return Response(serializer.data)


SIMILAR_DEFAULT_LIMIT = 6
SIMILAR_MAX_LIMIT = 12
# Equal weight on the plot and premise vectors. The 2026-10-30 experiment found
# plot-only neighbours blurred (Baby Driver -> Babel); 0.5 fixed it. Untuned.
SIMILARITY_PLOT_WEIGHT = 0.5


def clamp_limit(raw):
    """Parse ?limit=, falling back to the default for anything not an integer."""
    try:
        limit = int(raw)
    except (TypeError, ValueError):
        return SIMILAR_DEFAULT_LIMIT
    return max(1, min(SIMILAR_MAX_LIMIT, limit))


class SimilarMovies(APIView):
    def get(self, request, slug, format=None):
        movie = get_object_or_404(Movie, slug=slug)
        try:
            plot_data = movie.plot_data
        except MoviePlot.DoesNotExist:
            return Response([])
        if plot_data.embedding is None or plot_data.premise_embedding is None:
            return Response([])

        weight = SIMILARITY_PLOT_WEIGHT
        similarity = ExpressionWrapper(
            weight * (1 - CosineDistance("plot_data__embedding", plot_data.embedding))
            + (1 - weight)
            * (
                1
                - CosineDistance(
                    "plot_data__premise_embedding", plot_data.premise_embedding
                )
            ),
            output_field=FloatField(),
        )
        movies_qs = Movie.objects.annotate(avg_rating=Avg("reviews__score"))
        movies_qs = annotate_on_list(movies_qs, request.user)
        movies_qs = (
            meets_quality_bar(movies_qs)
            .exclude(pk=movie.pk)
            .filter(
                plot_data__embedding__isnull=False,
                plot_data__premise_embedding__isnull=False,
            )
            .annotate(similarity=similarity)
            .order_by("-similarity", "slug")
            .prefetch_related("actors", "director", "genre", "ondemand", "reviews")
        )
        limit = clamp_limit(request.query_params.get("limit"))

        serializer = SimilarMovieSerializer(movies_qs[:limit], many=True)
        return Response(serializer.data)


class RandomMovie(APIView):
    def get_object(self, slug):
        try:
            return Movie.objects.annotate(avg_rating=Avg("reviews__score")).get(
                slug=slug
            )
        except Movie.DoesNotExist:
            raise Http404

    def get(self, request):
        movie_slugs = Movie.objects.values_list("slug", flat=True)
        movie_slug = random.choice(movie_slugs)
        movie = self.get_object(movie_slug)
        movie = annotate_object_if_auth(request, movie)
        serializer = MovieSerializer(movie)
        return Response(serializer.data)


class GenreList(ListAPIView):
    serializer_class = GenreSerializer

    def get(self, request):
        genres = Genre.objects.annotate(movie_count=Count("movie"))
        genres = genres.order_by("-movie_count")
        serializer = GenreSerializer(genres, many=True)
        return Response(serializer.data)
