from rest_framework.routers import SimpleRouter
from .viewsets import LoginViewSet, RefreshViewSet, RegisterViewSet


routes = SimpleRouter()

routes.register(r'login', LoginViewSet, basename='auth-login')
routes.register(r'register', RegisterViewSet, basename='auth-register')
routes.register(r'refresh', RefreshViewSet, basename='auth-refresh')

urlpatterns = [
    *routes.urls
]
