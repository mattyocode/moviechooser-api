from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from rest_framework import permissions, serializers, status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from lists.models import Item, List
from lists.serializers import CreateItemSerializer, ItemSerializer
from movies.models import Movie


DEFAULT_LIST = "watch-list"


class MovieItemList(ListAPIView):
    serializer_class = ItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self, format=None):
        # list_name = self.request.data.get("list", DEFAULT_LIST)
        user = self.request.user
        try:
            _list = List.objects.get(name=DEFAULT_LIST, owner=user)
        except ObjectDoesNotExist:
            _list = List.objects.create(name=DEFAULT_LIST, owner=user)

        return Item.objects.filter(_list=_list).order_by("-added")

    def post(self, request, *args, **kwargs):
        serializer = CreateItemSerializer(data=request.data)
        if serializer.is_valid():
            try:
                movie = Movie.objects.get(slug=request.data.get("movie_slug"))
                user = self.request.user

                try:
                    _list = List.objects.get(name=DEFAULT_LIST, owner=user)
                except ObjectDoesNotExist:
                    _list = List.objects.create(name=DEFAULT_LIST, owner=user)

                item = Item.objects.create(movie=movie, _list=_list)
                serializer = self.serializer_class(item)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except ObjectDoesNotExist:
                return Response({"detail": "movie does not exist."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MovieItemDetail(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, uid):
        try:
            return Item.objects.get(uid=uid)
        except Item.DoesNotExist:
            raise Http404

    def get(self, request, uid, format=None):
        item = self.get_object(uid)
        serializer = ItemSerializer(item)
        return Response(serializer.data)

    def delete(self, request, uid, format=None):
        item = self.get_object(uid)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)