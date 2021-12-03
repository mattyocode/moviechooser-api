from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from rest_framework import permissions, status
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

    def get_list_or_create(self, name, owner):
        try:
            return List.objects.get(name=name, owner=owner)
        except ObjectDoesNotExist:
            return List.objects.create(name=name, owner=owner)

    def get_queryset(self, format=None):
        # list_name = self.request.data.get("list", DEFAULT_LIST)
        user = self.request.user
        _list = self.get_list_or_create(name=DEFAULT_LIST, owner=user)
        return Item.objects.filter(_list=_list).order_by("-added")

    def post(self, request, *args, **kwargs):
        serializer = CreateItemSerializer(data=request.data)
        if serializer.is_valid():
            try:
                movie = Movie.objects.get(slug=request.data.get("movie_slug"))
                user = self.request.user
                _list = self.get_list_or_create(name=DEFAULT_LIST, owner=user)
                item = Item.objects.create(movie=movie, _list=_list)
                serializer = self.serializer_class(item)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except ObjectDoesNotExist:
                return Response(
                    {"detail": "movie does not exist."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MovieItemDetail(APIView):
    serializer_class = ItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    # def get_object(self, uid):
    #     try:
    #         return Item.objects.get(uid=uid)
    #     except Item.DoesNotExist:
    #         raise Http404

    def get_object(self, slug):
        try:
            # _list = List.objects.get(owner=self.request.user)
            return Item.objects.get(movie__slug=slug, _list__owner=self.request.user)
        except Item.DoesNotExist:
            raise Http404

    def get(self, request, slug, format=None):
        item = self.get_object(slug)
        serializer = self.serializer_class(item)
        return Response(serializer.data)

    def delete(self, request, slug, format=None):
        item = self.get_object(slug)
        item.delete()
        return Response({"deleted": str(item.uid)}, status=status.HTTP_200_OK)

    def patch(self, request, slug, format=None):
        item = self.get_object(slug)
        serializer = self.serializer_class(item, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
