import random

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Avg, Count
from django.db.models.expressions import Exists, OuterRef, Value
from django.http import Http404
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from lists.models import Item, List
from movies.utils import annotate_object_if_auth

from .filters import MovieFilter
from .models import Genre, Movie
from .serializers import GenreSerializer, MovieSerializer


class MovieList(ListAPIView):
    serializer_class = MovieSerializer
    filterset_class = MovieFilter

    def get_queryset(self):
        movies_qs = Movie.objects.annotate(avg_rating=Avg("reviews__score"))
        if self.request.user.is_authenticated:
            try:
                items = Item.objects.filter(movie=OuterRef("pk"), _list__owner=self.request.user)
                movies_qs = movies_qs.annotate(on_list=Exists(items))
            except ObjectDoesNotExist:
                pass
        else:
            movies_qs = movies_qs.annotate(on_list=Value(False))

        filterset = self.filterset_class(self.request.GET, queryset=movies_qs)

        return (
            filterset.qs.order_by("-avg_rating")
            .distinct()
            .filter(avg_rating__gte=40)
            .exclude(poster_url="N/A")
        )


class MovieDetail(APIView):
    def get_object(self, slug):
        try:
            return Movie.objects.get(slug=slug)
        except Movie.DoesNotExist:
            raise Http404

    def get(self, request, slug, format=None):
        movie = self.get_object(slug)
        movie = annotate_object_if_auth(request, movie)
        serializer = MovieSerializer(movie)
        return Response(serializer.data)


class RandomMovie(APIView):
    def get(self, request):
        movies = list(Movie.objects.all())
        movie = random.choice(movies)
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
