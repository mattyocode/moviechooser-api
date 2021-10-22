import random

from django.db.models import Avg, Count
from django.http import Http404
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

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

        movies = Movie.objects.annotate(avg_rating=Avg("reviews__score"))

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
            movies = movies.filter(runtime__range=[f"{runtime_from}", f"{runtime_to}"])

        return movies.order_by("-avg_rating")


class MovieDetail(APIView):
    def get_object(self, slug):
        try:
            return Movie.objects.get(slug=slug)
        except Movie.DoesNotExist:
            raise Http404

    def get(self, request, slug, format=None):
        movie = self.get_object(slug)
        movie.avg_rating = movie.reviews.aggregate(avg_score=Avg("score"))["avg_score"]
        serializer = MovieSerializer(movie)
        return Response(serializer.data)


class RandomMovie(APIView):
    def get(self, request):
        movies = list(Movie.objects.all())
        random_movie = random.choice(movies)
        random_movie.avg_rating = random_movie.reviews.aggregate(avg_score=Avg("score"))["avg_score"]
        serializer = MovieSerializer(random_movie)
        return Response(serializer.data)


class GenreList(ListAPIView):
    serializer_class = GenreSerializer

    def get(self, request):
        genres = Genre.objects.annotate(movie_count=Count('movie'))
        genres = genres.order_by('-movie_count')
        serializer = GenreSerializer(genres, many=True)
        return Response(serializer.data)
