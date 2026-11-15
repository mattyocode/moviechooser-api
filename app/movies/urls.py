from django.urls import path

from .views import (
    GenreList,
    MovieDetail,
    MovieList,
    MovieWatch,
    RandomMovie,
    SimilarMovies,
    WatchRegions,
)

urlpatterns = [
    path("api/movies/", MovieList.as_view()),
    path("api/movies/random/", RandomMovie.as_view()),
    path("api/movies/<slug:slug>/similar/", SimilarMovies.as_view()),
    path("api/movies/<slug:slug>/watch/", MovieWatch.as_view()),
    path("api/movies/<slug:slug>/", MovieDetail.as_view()),
    path("api/genres/", GenreList.as_view()),
    path("api/watch/regions/", WatchRegions.as_view()),
]
