from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.GivlahLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("signup/", views.signup, name="signup"),
    path("demo-switch/", views.demo_switch, name="demo_switch"),
]
