# from django.db.models import fields
from django.db.models import Avg
from rest_framework import serializers

from .models import Actor, Director, Genre, Movie, Review


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


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ["id", "source", "score"]


class MovieSerializer(serializers.ModelSerializer):
    actors = ActorSerializer(many=True, read_only=True)
    director = DirectorSerializer(many=True, read_only=True)
    genre = GenreSerializer(many=True, read_only=True)
    reviews = ReviewSerializer(many=True, read_only=True)
    # avg_rating = serializers.FloatField(read_only=True)
    on_list = serializers.BooleanField(read_only=True)

    avg_rating = serializers.SerializerMethodField(read_only=True)
    plot_source_url = serializers.SerializerMethodField(read_only=True)
    # Whether the watch endpoint has anything to look up. The column is on the
    # row, so this adds no query; clients show the Watch button only when true.
    has_tmdb = serializers.SerializerMethodField(read_only=True)

    def get_has_tmdb(self, movie):
        return getattr(movie, "tmdb_id", None) is not None

    def get_avg_rating(self, movie):
        # The movie views annotate it; lists nest plain movies, so fall back.
        if hasattr(movie, "avg_rating"):
            return movie.avg_rating
        if hasattr(movie, "reviews"):
            return movie.reviews.aggregate(avg_score=Avg("score"))["avg_score"]

    def get_plot_source_url(self, movie):
        """Permalink to the Wikipedia revision whose plot was embedded.

        For CC BY-SA attribution. None for OMDb plots and for movies the views
        didn't annotate (lists nest plain movies).
        """
        url = getattr(movie, "plot_source_url", None)
        if not url:
            return None
        revid = getattr(movie, "plot_source_revid", None)
        return f"{url}?oldid={revid}" if revid else url

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
            "reviews",
            "avg_rating",
            "on_list",
            "plot_source_url",
            "has_tmdb",
        )
        read_only_fields = ("__all__",)


class SimilarMovieSerializer(MovieSerializer):
    similarity = serializers.FloatField(read_only=True)

    class Meta(MovieSerializer.Meta):
        fields = MovieSerializer.Meta.fields + ("similarity",)
