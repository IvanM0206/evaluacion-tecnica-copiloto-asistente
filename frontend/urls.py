from django.urls import path

from frontend import views

app_name = "frontend"

urlpatterns = [
    path("", views.index, name="index"),
    path("analizar/", views.analyze, name="analyze"),
    path("cargando/", views.loading, name="loading"),
    path("analisis/", views.workspace, name="workspace"),
]
