from django.contrib import admin
from django.urls import include, path

from api.api import api

urlpatterns = [
    path("admin/", admin.site.urls),  # inspeccionar/editar los incidentes guardados
    path("api/", api.urls),  # capa 3: endpoints JSON (docs en /api/docs)
    path("", include("frontend.urls")),  # capa 4: panel del operador
]
