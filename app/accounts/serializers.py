from django.contrib.auth import get_user, get_user_model
from rest_framework import serializers

class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = get_user_model()
        fields = ['id', 'username', 'email', 'is_active', 'date_joined', 'last_login']
        # fields = ['id', 'username', 'email', 'is_active', 'created', 'updated']
        # read_only_field = ['is_active', 'created', 'updated']