from django.urls import path
from . import views

app_name = "ocr"

urlpatterns = [
    path("", views.index, name="index"),
    path("upload/", views.upload, name="upload"),
    path("process/<int:pk>/", views.process, name="process"),
    path("detail/<int:pk>/", views.detail, name="detail"),
    path("delete/<int:pk>/", views.delete, name="delete"),
]
