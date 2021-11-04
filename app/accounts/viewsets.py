from rest_framework import serializers, status, viewsets
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

    def get_queryset(self):
        if self.request.user.is_superuser:
            return CustomUser.objects.all().order_by('-last_login')
        raise PermissionDenied(code=401)

    def get_object(self):
        lookup_field_value = self.kwargs[self.lookup_field]

        obj = CustomUser.objects.get(lookup_field_value)
        self.check_object_permissions(self.request, obj)

        return obj

# class UserViewSet(viewsets.ModelViewSet):
#     http_method_names = ['get']
#     serializer_class = UserSerializer
#     permission_classes = (IsAuthenticated,)
#     # filter_backends = [filters.OrderingFilter]

#     def get_queryset(self):
#         if self.request.user.is_superuser:
#             print("IS-SUPERUSER")
#             return CustomUser.objects.all().order_by('-last_login')
#         else:
#             return Response(status=status.HTTP_401_UNAUTHORIZED)

#     def get_object(self):
#         lookup_field_value = self.kwargs[self.lookup_field]

#         obj = CustomUser.objects.get(lookup_field_value)
#         self.check_object_permissions(self.request, obj)

#         return obj