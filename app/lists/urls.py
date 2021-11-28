from django.urls import path

from .views import MovieItemList, MovieItemDetail

urlpatterns = [
    path("", MovieItemList.as_view()),
    path("<str:uid>/", MovieItemDetail.as_view()),
]
