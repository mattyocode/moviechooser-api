from rest_framework import serializers

from .models import Movie

class MovieSerializer(serializers.ModelSerializer):

    class Meta:
        model = Movie
        fields = '__all__'
        # released = serializers.DateField()
        read_only_fields = ('id',)