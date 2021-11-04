# from django.urls import path
# from rest_framework_simplejwt import views as jwt_views
from rest_framework.routers import SimpleRouter
from .viewsets import UserViewSet

routes = SimpleRouter()

# User
routes.register(r'user', UserViewSet, basename='user')

urlpatterns = [
    *routes.urls
]

# will need login, register, and refresh endpoints
# urlpatterns = [
#     path('token/obtain/', jwt_views.TokenObtainPairView.as_view(), name="token_create"),
#     path('token/refresh/', jwt_views.TokenRefreshView.as_view(), name="token_refresh"),
# ]
