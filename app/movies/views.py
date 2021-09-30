from django.http import Http404
from django.db.models import Avg
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework import status

from .models import Movie
from .serializers import MovieSerializer


class MovieList(ListAPIView):
    serializer_class = MovieSerializer

    def get_queryset(self):
        genres = self.request.GET.getlist('g')
        start_decade = self.request.GET.get('dmin')
        end_decade = self.request.GET.get('dmax')
        runtime_from = self.request.GET.get('rmin')
        runtime_to = self.request.GET.get('rmax')

        movies = Movie.objects.annotate(
            avg_rating=Avg('reviews__score')
        )


        if len(genres) > 0:
            movies = movies.filter(genre__id__in=genres)
        else:
            movies = movies.all()

        if start_decade and end_decade:
            movies = movies.filter(released__range=[f"{start_decade}-01-01", f"{end_decade}-12-31"])

        if runtime_from and runtime_to:
            movies = movies.filter(runtime__range=[f"{runtime_from}", f"{runtime_to}"])

        return movies.order_by('-avg_rating')

    # def get(self, request):
    #     movies = Movie.objects.all()
    #     genres = request.GET.get("genre")
    #     if genres:
    #         movies = Movie.objects.filter(genre=genres)
    #     serializer = MovieSerializer(movies, many=True)
    #     return Response(serializer.data)


class MovieDetail(APIView):
    def get_object(self, slug):
        try:
            return Movie.objects.get(slug=slug)
        except Movie.DoesNotExist:
            raise Http404

    def get(self, request, slug, format=None):
        movie = self.get_object(slug)
        movie.avg_rating = movie.reviews.aggregate(avg_score=Avg('score'))['avg_score']
        serializer = MovieSerializer(movie)
        return Response(serializer.data)
