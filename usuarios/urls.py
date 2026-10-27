from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import IngresoView

urlpatterns = [
    path("login/", IngresoView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
]
