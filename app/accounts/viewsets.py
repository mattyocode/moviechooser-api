from rest_framework import serializers, status, viewsets
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework import filters
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied

from .serializers import UserSerializer
from .models import CustomUser


class UserViewSet(viewsets.ModelViewSet):
    http_method_names = ['get']
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)
    lookup_field = "id"

    def get_queryset(self):
        if self.request.user.is_superuser:
            return CustomUser.objects.all().order_by('-last_login')
        raise PermissionDenied(code=403)

    def get_object(self):
        if self.request.user.is_superuser:
            filter_kwargs = {self.lookup_field: self.kwargs[self.lookup_field]}
            obj = get_object_or_404(CustomUser, **filter_kwargs)
            self.check_object_permissions(self.request, obj)

            return obj
        raise PermissionDenied(code=403)
