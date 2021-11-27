from rest_framework import serializers

from lists.models import Item, List


class ListSerializer(serializers.ModelSerializer):
    class Meta:
        model = List
        fields = "__all__"
        read_only_fields = ["id", "added", "updated"]


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = "__all__"
        read_only_fields = ["id", "added", "updated"]