"""Capa 3 · Endpoints. Adaptadores HTTP finos sobre la capa services.

Reglas: acá no hay lógica de negocio ni acceso al ORM. Los esquemas de request/response
son los modelos Pydantic de `services.models`. Docs interactivas: /api/docs
"""

from ninja import NinjaAPI

from api.routers import cards, catalog, copilot, health

api = NinjaAPI(title="Soflex · Copiloto de Operador", version="0.1.0", urls_namespace="api")

api.add_router("/", health.router, tags=["health"])
api.add_router("/catalog", catalog.router, tags=["catalog"])
api.add_router("/copilot", copilot.router, tags=["copilot"])
api.add_router("/cards", cards.router, tags=["cards"])
