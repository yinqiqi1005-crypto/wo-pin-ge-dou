from django.urls import path

from .views import add_category, delete_category, profile, register, set_language, update_category

app_name = "accounts"

urlpatterns = [
    path("register/", register, name="register"),
    path("profile/", profile, name="profile"),
    path("language/", set_language, name="set_language"),
    path("categories/add/", add_category, name="add_category"),
    path("categories/<int:category_id>/", update_category, name="update_category"),
    path("categories/<int:category_id>/delete/", delete_category, name="delete_category"),
]
