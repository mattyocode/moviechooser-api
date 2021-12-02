from rest_framework import serializers

from lists.models import Item, List
from movies.serializers import MovieSerializer


class ListSerializer(serializers.ModelSerializer):
    class Meta:
        model = List
        fields = ["name"]


class ItemSerializer(serializers.ModelSerializer):
    movie = MovieSerializer(read_only=True)
    _list = ListSerializer(read_only=True)

    class Meta:
        model = Item
        fields = ["_list", "movie", "watched", "added", "updated", "uid"]
        read_only_fields = ["added", "updated"]


class CreateItemSerializer(serializers.ModelSerializer):
    movie_slug = serializers.CharField(max_length=50)

    class Meta:
        model = Item
        fields = ["movie_slug"]
