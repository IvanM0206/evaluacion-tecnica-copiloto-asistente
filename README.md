# evaluacion-tecnica-copiloto-asistente

## Arquitectura

Todo es Python: Django 5.1 + Django Ninja (API tipada con Pydantic v2) + SQLite. El front se renderiza en el servidor **sin JavaScript**.

```
 [4] frontend/  ──HTTP (httpx)──▶  [3] api/  ──▶  [2] services/  ──▶  [1] backend/  ──▶ SQLite
     templates + view models          routers         copiloto, NLP,       ORM +
     (panel del operador)             Ninja           providers LLM        repositorios
```