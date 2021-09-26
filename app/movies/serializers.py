from django.db.models import fields
from rest_framework import serializers

from .models import Genre, Movie

class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ('name',)

        read_only_fields = (
            'id',
        )

class MovieSerializer(serializers.ModelSerializer):
    genre = GenreSerializer(many=True, read_only=True)

    class Meta:
        model = Movie
        fields = (
            'id',
            'title', 
            'released',
            'runtime',
            'writer',
            'plot',
            'country',
            'poster_url',
            'genre')
        # released = serializers.DateField()
        read_only_fields = (
            'id',
        )