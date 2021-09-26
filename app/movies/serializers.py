from django.db.models import fields
from rest_framework import serializers

from .models import Actor, Director, Genre, Movie


class ActorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Actor
        fields = ('name',)

        read_only_fields = (
            'id',
        )


class DirectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Director
        fields = ('name',)

        read_only_fields = (
            'id',
        )


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ('name',)

        read_only_fields = (
            'id',
        )



class MovieSerializer(serializers.ModelSerializer):
    actors = ActorSerializer(many=True, read_only=True)
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
            'actors',
            'genre')
        # released = serializers.DateField()
        read_only_fields = (
            'id',
        )