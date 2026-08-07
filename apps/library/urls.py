from django.urls import path

from . import views

app_name = "library"

urlpatterns = [
    path("", views.pattern_list, name="list"),
    path("<int:pattern_id>/", views.pattern_detail, name="detail"),
]
