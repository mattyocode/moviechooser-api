from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import PasswordTokenCheckAPI, RequestPasswordResetEmail
from .viewsets import LoginViewSet, RefreshViewSet, RegisterViewSet

routes = SimpleRouter()

routes.register(r"login", LoginViewSet, basename="auth-login")
routes.register(r"register", RegisterViewSet, basename="auth-register")
routes.register(r"refresh", RefreshViewSet, basename="auth-refresh")

urlpatterns = [*routes.urls]

urlpatterns += [
    path(
        "request-reset-email/",
        RequestPasswordResetEmail.as_view(),
        name="request-reset-email",
    ),
    path(
        "password-reset/<uidb64>/<token>/",
        PasswordTokenCheckAPI.as_view(),
        name="password-reset-confirm",
    ),
]
