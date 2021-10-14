from django.urls import path

from .views import GenreList, MovieDetail, MovieList

urlpatterns = [
    path("api/movies/", MovieList.as_view()),
    path("api/movies/<slug:slug>/", MovieDetail.as_view()),
    path("api/genres/", GenreList.as_view()),
]
