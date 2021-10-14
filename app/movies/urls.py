from django.urls import path

from .views import MovieDetail, MovieList

urlpatterns = [
    path("api/movies/", MovieList.as_view()),
    path("api/movies/<slug:slug>/", MovieDetail.as_view()),
    path("api/genres/", )
]
