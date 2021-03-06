# from django.db.models import fields
from django.db.models import Avg
from rest_framework import serializers

from .models import Actor, Director, Genre, Movie, OnDemand, Review


class ActorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Actor
        fields = (
            "id",
            "name",
        )

        read_only_fields = ("id",)


class DirectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Director
        fields = (
            "id",
            "name",
        )

        read_only_fields = ("id",)


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ["id", "name"]


class OnDemandSerializer(serializers.ModelSerializer):
    class Meta:
        model = OnDemand
        fields = ["id", "service", "url"]


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ["id", "source", "score"]


class MovieSerializer(serializers.ModelSerializer):
    actors = ActorSerializer(many=True, read_only=True)
    director = DirectorSerializer(many=True, read_only=True)
    genre = GenreSerializer(many=True, read_only=True)
    ondemand = OnDemandSerializer(many=True, read_only=True)
    reviews = ReviewSerializer(many=True, read_only=True)
    # avg_rating = serializers.FloatField(read_only=True)
    on_list = serializers.BooleanField(read_only=True)

    avg_rating = serializers.SerializerMethodField(read_only=True)

    def get_avg_rating(self, movie):
        if hasattr(movie, "reviews"):
            return movie.reviews.aggregate(avg_score=Avg("score"))["avg_score"]

    class Meta:
        model = Movie
        fields = (
            "slug",
            "title",
            "released",
            "runtime",
            "writer",
            "plot",
            "country",
            "poster_url",
            "actors",
            "director",
            "genre",
            "ondemand",
            "reviews",
            "avg_rating",
            "on_list",
        )
        read_only_fields = ("__all__",)
