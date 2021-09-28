from django.http import Http404
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework import status

from .models import Movie
from .serializers import MovieSerializer


class MovieList(ListAPIView):
    def get_queryset(self, request, format=None):
        genres = request.query_params.get('genre')
        print("GENRES >>", genres)
        movies = Movie.objects.filter(genre=genres)
        serializer = MovieSerializer(movies, many=True)
        return Response(serializer.data)

    def get(self, request, format=None):
        movies = Movie.objects.all()
        serializer = MovieSerializer(movies, many=True)
        return Response(serializer.data)


class MovieDetail(APIView):
    def get_object(self, slug):
        try:
            return Movie.objects.get(slug=slug)
        except Movie.DoesNotExist:
            raise Http404

    def get(self, request, slug, format=None):
        movie = self.get_object(slug)
        serializer = MovieSerializer(movie)
        return Response(serializer.data)
