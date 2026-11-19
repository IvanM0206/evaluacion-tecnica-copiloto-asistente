from django.contrib import admin
from django.urls import path

from api.api import api

urlpatterns = [
    path("admin/", admin.site.urls),  # inspeccionar/editar los incidentes guardados
    path("api/", api.urls),  # capa 3: endpoints JSON (docs en /api/docs)
]
