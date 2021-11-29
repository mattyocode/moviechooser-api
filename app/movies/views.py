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

from .models import Genre, Movie
from .serializers import GenreSerializer, MovieSerializer


class MovieList(ListAPIView):
    serializer_class = MovieSerializer

    def get_queryset(self):
        genres = self.request.GET.getlist("g")
        start_decade = self.request.GET.get("dmin")
        end_decade = self.request.GET.get("dmax")
        runtime_from = self.request.GET.get("rmin")
        runtime_to = self.request.GET.get("rmax")

        movies = Movie.objects.all()
        # movies = Movie.objects.annotate(avg_rating=Avg("reviews__score"))

        if len(genres) > 0:
            movies = movies.filter(genre__id__in=genres)
        else:
            movies = movies.all()

        if start_decade and end_decade:
            if start_decade == "pre":
                start_decade = "1920"
            if end_decade == "pre":
                end_decade = "1959"
            movies = movies.filter(
                released__range=[f"{start_decade}-01-01", f"{end_decade[:3]}9-12-31"]
            )

        if runtime_from and runtime_to:
            if runtime_from == "<75":
                runtime_from = 0
            if runtime_to == "<75":
                runtime_to = 74
            if runtime_from == ">150":
                runtime_from = 151
            if runtime_to == ">150":
                runtime_to = 400
            if runtime_from == runtime_to:
                runtime_from = int(runtime_from) - 3
                runtime_to = int(runtime_to) + 3
            movies = movies.filter(runtime__range=[runtime_from, runtime_to])

        movies = movies.annotate(on_list=Value(False))

        if self.request.user.is_authenticated:
            try:
                _list = List.objects.get(owner=self.request.user)
                items = Item.objects.filter(movie=OuterRef("pk"), _list=_list)
                movies = movies.annotate(on_list=Exists(items))
            except ObjectDoesNotExist:
                pass

        movies = movies.annotate(avg_rating=Avg("reviews__score"))

        return (
            movies.order_by("-avg_rating")
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
