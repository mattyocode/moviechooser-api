from django.urls import path
from rest_framework_simplejwt import views as jwt_views

# from .views import

# will need login, register, and refresh endpoints
urlpatterns = [
    path('token/obtain/', jwt_views.TokenObtainPairView.as_view(), name="token_create"),
    path('token/refresh/', jwt_views.TokenRefreshView.as_view(), name="token_refresh"),
]
