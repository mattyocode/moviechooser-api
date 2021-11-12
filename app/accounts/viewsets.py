from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated

from .models import CustomUser
from .serializers import UserSerializer


class UserViewSet(viewsets.ModelViewSet):
    http_method_names = ["get"]
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)
    lookup_field = "id"

    def get_queryset(self):
        if self.request.user.is_superuser:
            return CustomUser.objects.all().order_by("-last_login")
        raise PermissionDenied(code=403)

    def get_object(self):
        filter_kwargs = {self.lookup_field: self.kwargs[self.lookup_field]}
        obj = get_object_or_404(CustomUser, **filter_kwargs)
        if not self.request.user.is_superuser:
            if str(self.request.user) != obj.email:
                raise PermissionDenied(code=403)
        return obj
