import random

from django.db.models import Avg, Count
from django.db.models.expressions import Exists, OuterRef, Value
from django.http import Http404
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from lists.models import Item
from movies.utils import annotate_object_if_auth

from .filters import MovieFilter
from .models import Genre, Movie
from .serializers import GenreSerializer, MovieSerializer


def filter_movies(params, queryset):
    """Apply the search filters and the catalogue's quality cut-offs."""
    filterset = MovieFilter(params, queryset=queryset)
    return (
        filterset.qs.order_by("-avg_rating")
        .distinct()
        .filter(avg_rating__gte=40)
        .exclude(poster_url="N/A")
    )


class MovieList(ListAPIView):
    serializer_class = MovieSerializer
    filterset_class = MovieFilter

    def get_queryset(self):
        movies_qs = Movie.objects.annotate(avg_rating=Avg("reviews__score"))
        if self.request.user.is_authenticated:
            item = Item.objects.filter(
                movie=OuterRef("pk"), _list__owner=self.request.user
            )
            movies_qs = movies_qs.annotate(on_list=Exists(item))
        else:
            movies_qs = movies_qs.annotate(on_list=Value(False))

        return filter_movies(self.request.GET, movies_qs)


class MovieCount(APIView):
    """Number of movies matching the search filters, for live counts as the
    user edits filters. Throttled on its own scope so it doesn't use up the
    anonymous allowance needed for real searches."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "movie_count"

    def get(self, request):
        movies_qs = Movie.objects.annotate(avg_rating=Avg("reviews__score"))
        return Response({"count": filter_movies(request.GET, movies_qs).count()})


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
