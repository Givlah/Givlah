from django.urls import path

from . import views

app_name = "pwa"

urlpatterns = [
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("sw.js", views.service_worker, name="sw"),
    path("offline/", views.offline, name="offline"),
]
