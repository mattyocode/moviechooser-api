import logging
import random

from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from pgvector.django import CosineDistance
from rest_framework import status
from rest_framework.exceptions import APIException
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

logger = logging.getLogger(__name__)

# Text search returns one page: the slice must fit PAGE_SIZE (pinned by a test).
TEXT_SEARCH_LIMIT = 30
TEXT_SEARCH_MAX_CHARS = 120


class SearchUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Search is unavailable right now."
    default_code = "search_unavailable"


class MovieList(ListAPIView):
    filterset_class = MovieFilter

    def text_query(self):
        """The trimmed ?q=, cut to TEXT_SEARCH_MAX_CHARS; "" when blank."""
        return self.request.query_params.get("q", "").strip()[:TEXT_SEARCH_MAX_CHARS]

    def get_serializer_class(self):
        if self.text_query():
            return SimilarMovieSerializer
        return MovieSerializer

    def get_queryset(self):
        movies_qs = recommendable_movies(self.request.user)
        filterset = self.filterset_class(self.request.GET, queryset=movies_qs)

        query = self.text_query()
        if not query:
            return filterset.qs.order_by("-avg_rating").distinct()

        try:
            query_vector = embeddings.embed_query(query)
        except Exception:
            logger.exception("Could not embed text search query")
            raise SearchUnavailable()

        return (
            filterset.qs.filter(current_vectors("plot_data__"))
            .annotate(similarity=combined_similarity(query_vector, query_vector))
            .order_by("-similarity", "slug")
            .distinct()[:TEXT_SEARCH_LIMIT]
        )


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


def current_vectors(prefix=""):
    """Both vectors present and from the current model, so comparable.

    prefix is the path to MoviePlot, e.g. "plot_data__" from Movie.
    """
    return Q(
        **{
            f"{prefix}model_name": embeddings.MODEL_NAME,
            f"{prefix}premise_model_name": embeddings.MODEL_NAME,
            f"{prefix}embedding__isnull": False,
            f"{prefix}premise_embedding__isnull": False,
        }
    )


def combined_similarity(plot_vector, premise_vector):
    """Weighted cosine similarity to a movie's plot and premise vectors.

    Annotates a Movie queryset. /similar/ passes a movie's two vectors; text
    search passes the query vector for both.
    """
    return SIMILARITY_PLOT_WEIGHT * (
        1 - CosineDistance("plot_data__embedding", plot_vector)
    ) + (1 - SIMILARITY_PLOT_WEIGHT) * (
        1 - CosineDistance("plot_data__premise_embedding", premise_vector)
    )


def source_plot(slug):
    """The movie's MoviePlot when both vectors are from the current model.

    Vectors from another model can't be compared, so they count as missing.
    Vectors from text changed since embedding are still used: roughly right
    beats an empty list until build_plot_embeddings runs. Returns None when
    there is nothing to compare; raises Http404 for an unknown slug.
    """
    plot = (
        MoviePlot.objects.filter(current_vectors(), movie__slug=slug)
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

        # Scores every movie: exact, and simpler than a candidate pass through
        # the HNSW indexes. On dev with 3,000 movies (2026-11-04) this query
        # takes about 7ms, and the whole view in-process about 13ms; HTTP adds
        # more.
        movies_qs = (
            recommendable_movies(request.user)
            .exclude(pk=source.pk)
            .filter(current_vectors("plot_data__"))
            .annotate(
                similarity=combined_similarity(
                    source.embedding, source.premise_embedding
                )
            )
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
