from django.urls import path

from . import views

app_name = "memberships"

urlpatterns = [
    path("", views.plans, name="plans"),
    path("center/", views.center, name="center"),
    path("upgrade/<str:level>/", views.upgrade, name="upgrade"),
]
