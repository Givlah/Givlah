from django.urls import path

from . import views

app_name = "listings"

urlpatterns = [
    path("", views.nearby, name="nearby"),
    path("items/new/", views.create, name="create"),
    path("items/<int:pk>/", views.detail, name="detail"),
    path("items/<int:pk>/edit/", views.edit, name="edit"),
    path("items/<int:pk>/close/", views.close, name="close"),
    path("activity/", views.activity, name="activity"),
    path("photos/<uuid:photo_uuid>.jpg", views.photo, name="photo"),
]
