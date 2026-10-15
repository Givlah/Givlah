from django.urls import path

from . import views

app_name = "coordination"

urlpatterns = [
    path("items/<int:pk>/offer/<str:kind>/", views.make_offer, name="offer"),
    path("offers/<str:kind>/<int:offer_id>/withdraw/", views.withdraw_offer, name="withdraw"),
    path("items/<int:pk>/crew/", views.crew, name="crew"),
    path("plans/<int:plan_id>/", views.plan_detail, name="plan"),
    path("plans/<int:plan_id>/<str:action>/", views.plan_action, name="plan_action"),
    path("impact/", views.impact, name="impact"),
]
