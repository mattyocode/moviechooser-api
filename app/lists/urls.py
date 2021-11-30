from django.urls import path

from .views import MovieItemDetail, MovieItemList

urlpatterns = [
    path("", MovieItemList.as_view()),
    path("<str:slug>/", MovieItemDetail.as_view()),
]
