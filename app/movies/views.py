import random

from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404
from pgvector.django import CosineDistance
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from movies import embeddings
from movies.utils import annotated_movies, recommendable_movies

from .filters import MovieFilter
from .models import Genre, Movie, MoviePlot
from .serializers import (
    GenreSerializer,
    MovieSerializer,
    SimilarMovieSerializer,
)


class MovieList(ListAPIView):
    serializer_class = MovieSerializer
    filterset_class = MovieFilter

    def get_queryset(self):
        movies_qs = recommendable_movies(self.request.user)
        filterset = self.filterset_class(self.request.GET, queryset=movies_qs)

        return filterset.qs.order_by("-avg_rating").distinct()


class MovieDetail(APIView):
    def get(self, request, slug, format=None):
        movie = get_object_or_404(annotated_movies(request.user), slug=slug)
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


def source_plot(slug):
    """The movie's MoviePlot when both vectors are from the current model.

    Vectors from another model can't be compared, so they count as missing.
    Vectors from text changed since embedding are still used: roughly right
    beats an empty list until build_plot_embeddings runs. Returns None when
    there is nothing to compare; raises Http404 for an unknown slug.
    """
    plot = (
        MoviePlot.objects.filter(
            movie__slug=slug,
            model_name=embeddings.MODEL_NAME,
            premise_model_name=embeddings.MODEL_NAME,
            embedding__isnull=False,
            premise_embedding__isnull=False,
        )
        .only("embedding", "premise_embedding")
        .first()
    )
    if plot is None and not Movie.objects.filter(slug=slug).exists():
        raise Http404
    return plot


class SimilarMovies(APIView):
    def get(self, request, slug, format=None):
        source = source_plot(slug)
        if source is None:
            return Response([])

        # Scores every movie: about 20ms for 3,000 movies (2026-11-04), exact,
        # and simpler than a candidate pass through the HNSW indexes.
        similarity = SIMILARITY_PLOT_WEIGHT * (
            1 - CosineDistance("plot_data__embedding", source.embedding)
        ) + (1 - SIMILARITY_PLOT_WEIGHT) * (
            1 - CosineDistance("plot_data__premise_embedding", source.premise_embedding)
        )
        movies_qs = (
            recommendable_movies(request.user)
            .exclude(pk=source.pk)
            .filter(
                plot_data__model_name=embeddings.MODEL_NAME,
                plot_data__premise_model_name=embeddings.MODEL_NAME,
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
    def get(self, request):
        movie_slugs = Movie.objects.values_list("slug", flat=True)
        movie_slug = random.choice(movie_slugs)
        movie = get_object_or_404(annotated_movies(request.user), slug=movie_slug)
        serializer = MovieSerializer(movie)
        return Response(serializer.data)


class GenreList(ListAPIView):
    serializer_class = GenreSerializer

    def get(self, request):
        genres = Genre.objects.annotate(movie_count=Count("movie"))
        genres = genres.order_by("-movie_count")
        serializer = GenreSerializer(genres, many=True)
        return Response(serializer.data)
