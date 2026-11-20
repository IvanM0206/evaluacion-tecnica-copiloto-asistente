# Copiloto de Operador · Soflex Technical Challenge

Prototipo de **copiloto para operadores de sala** de las centrales de emergencia de CABA (911, 103, 107, 147).
Recibe la **transcripción de texto** de una llamada y asiste al operador en vivo:

1. **Extrae y normaliza la ubicación**: calle, altura, intersección y barrio. Cada dato va con la frase literal del relato que lo respalda.
2. **Tipifica el hecho** (categoría y subcategoría) y **sugiere prioridad P1–P4** con su justificación.
3. Arma el **checklist dinámico de protocolo**: qué preguntas clave ya respondió el llamante y cuáles faltan, con las pendientes primero.
4. Propone las **instrucciones pre-arribo** para leerle al ciudadano.
5. El operador **valida o corrige** todo, marca el checklist y **deriva la Carta de Llamada** al despacho.

El operador no despacha recursos: eso lo decide el despachador en el CAD. Por eso los recursos aparecen solo como sugerencia.

> Las decisiones de diseño, los supuestos, los trade-offs y las mejoras futuras están en [DECISIONS.md](DECISIONS.md).

---

## Cómo correrlo

### Con Docker (recomendado)

```bash
docker compose up --build
```

Abrir **http://localhost:8000**. El contenedor migra la base, carga el dataset (es idempotente) y levanta gunicorn. La base queda en el volumen `copiloto-db`.
Por defecto corre en **modo mock**: determinista, offline y gratis. No necesita ninguna credencial.

Para usar el LLM real, crear un `.env` a partir de [.env.example](.env.example):

```bash
cp .env.example .env
# editar .env: LLM_PROVIDER=anthropic y ANTHROPIC_API_KEY=...
docker compose up --build
```

Si falta la API key, el sistema cae siempre a `mock`. Si el LLM falla en una llamada (timeout, rate limit, JSON inválido, rechazo), esa llamada se resuelve con el mock y se muestra una advertencia.

### Local (sin Docker)

Requiere Python 3.12 o superior.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt        # Windows: .venv\Scripts\pip
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_dataset          # carga data/dataset_challenge_soflex.csv
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

### URLs

| URL | Qué es |
|---|---|
| `/` | Panel del operador |
| `/api/docs` | Documentación interactiva de la API (OpenAPI) |
| `/admin/` | Admin de Django para ver incidentes y cartas (requiere `manage.py createsuperuser`) |

### Variables de entorno

| Variable | Default | Uso |
|---|---|---|
| `LLM_PROVIDER` | vacío local / `mock` en Docker | `mock` o `anthropic`. Vacío = Claude si hay key, si no mock |
| `ANTHROPIC_API_KEY` | — | Sin key se usa `mock` |
| `ANTHROPIC_MODEL` | `claude-opus-5-5` | Modelo del provider real |
| `DJANGO_DEBUG` | `true` local / `false` Docker | |
| `DJANGO_SECRET_KEY` | clave de desarrollo | Definirla fuera de desarrollo |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,0.0.0.0` | |
| `API_BASE_URL` | `http://127.0.0.1:8000/api` | A dónde llama el front (permite separar front y API) |
| `CATALOG_API_TOKEN` | — | Habilita `POST /api/catalog/incidents` (header `X-Catalog-Token`). Sin definir, la escritura del catálogo está deshabilitada |
| `API_TIMEOUT_SECONDS`, `DB_PATH`, `DATA_DIR`, `DATASET_PATH` | | Ver [config/settings.py](config/settings.py) |

---

## Cómo se usa (flujo del operador)

1. **Pantalla inicial**: elegir una llamada del dataset, escribir o pegar la transcripción, subir un `.txt` o tocar **Usar plantilla de ejemplo**.
   Sin LLM configurado aparece además **Analizar simulando LLM**: agrega respuestas de ejemplo fijas (por ejemplo, las preguntas extra) para ver cómo se vería el panel con un modelo real. Todo lo simulado queda rotulado como tal.
2. **Analizar** (Alt+A): aparece un loader a pantalla completa y después el panel de trabajo.
3. **Columna izquierda**: la transcripción en modo lectura, separada en turnos *Operador* / *Llamante*.
   - **Editar** (Alt+E) permite corregirla y reanalizarla.
   - **+ Nueva transcripción** (Alt+N) carga otra llamada sin salir del panel.
4. **Columna derecha**: la sugerencia en secciones plegables (acordeón), con scroll propio:
   - **Advertencias**: datos sin evidencia literal, baja similitud, prioridad distinta a la del caso de referencia, etc.
   - **Tipificación y prioridad**: editables.
   - **Ubicación**: cada campo muestra su evidencia (`✓ "Av. Belgrano 3100"`), si falta (`No mencionado: preguntar`) o si la editó el operador.
   - **Instrucciones pre-arribo**: para leerle al llamante.
   - **Checklist**: las preguntas pendientes primero; las respondidas muestran la respuesta del relato. Con el LLM, puede sumar hasta 3 preguntas extra marcadas **Sugerida por IA** (no son del protocolo: el operador decide si hacerlas).
   - **Riesgos**, **Recursos sugeridos** (los decide el despachador) y **Notas del operador**.
5. **Derivar Carta de Llamada** (Alt+D): se guarda la carta y se vuelve a la pantalla inicial.
   Si falta un dato obligatorio, el panel se vuelve a mostrar **con las ediciones del operador intactas**.
6. **Cartas derivadas** (en el header): lista de las cartas enviadas al despacho; cada una se despliega con el detalle completo (ubicación, checklist, instrucciones, riesgos, notas y transcripción).

El botón **⌨** (abajo a la izquierda) muestra los atajos de teclado. La combinación es Alt en Chrome/Edge, Alt+Shift en Firefox y Ctrl+Option en Mac.

---

## Arquitectura

Todo es Python: Django 5.1 + Django Ninja (API tipada con Pydantic v2) + SQLite. El front se renderiza en el servidor **sin JavaScript**.

```
 [4] frontend/  ──HTTP (httpx)──▶  [3] api/  ──▶  [2] services/  ──▶  [1] backend/  ──▶ SQLite
     templates + view models          routers         copiloto, NLP,       ORM +
     (panel del operador)             Ninja           providers LLM        repositorios
```

- **`backend/`**: modelos ORM (`Incident`, `CallCard`), repositorios y el comando `seed_dataset`.
- **`services/`**: la lógica. Retrieval TF-IDF sobre el catálogo → extracción por *provider* (mock o Claude) → **grounding y validación** → sugerencia tipada. Incluye el catálogo de referencia.
- **`api/`**: endpoints finos que solo validan y delegan en `services.container`.
- **`frontend/`**: vistas y templates. Habla con la API **solo por HTTP**, aunque hoy corran en el mismo proceso. Cambiando `API_BASE_URL` se separan en dos servicios.

Cada capa solo importa la de abajo (lo verifica `tests/test_architecture.py`). La justificación está en [DECISIONS.md](DECISIONS.md).

### API

| Método y ruta | Descripción |
|---|---|
| `GET /api/health` | Estado, provider activo y tamaño del catálogo |
| `GET /api/catalog/samples[/{id}]` | Transcripciones del dataset para la demo |
| `GET /api/catalog/incidents` | Catálogo de referencia completo |
| `POST /api/catalog/incidents` | Agrega un incidente sintético en caliente (201; 409 si el id existe; 401 sin `X-Catalog-Token` válido) |
| `POST /api/copilot/analyze` | `{"transcript": "...", "simulate_llm": false}` → sugerencia completa |
| `POST /api/cards` · `GET /api/cards` | Deriva o lista Cartas de Llamada |

---

## Datos

[data/dataset_challenge_soflex.csv](data/dataset_challenge_soflex.csv) tiene 30 llamadas sintéticas de CABA, con la tipificación, la ubicación normalizada, el protocolo y las instrucciones como referencia.
Se usa como **catálogo de referencia**: casos similares, preguntas de protocolo, instrucciones y few-shot para el LLM.
Cuando se analiza una llamada del dataset (selector o plantilla de ejemplo), ese mismo caso se excluye de la búsqueda (*leave-one-out*): el copiloto la trata como una llamada nueva en lugar de copiar la respuesta guardada.

Para sumar datos hipotéticos hay dos caminos, ambos con el mismo formato:

```bash
.venv/bin/python manage.py seed_dataset ruta/a/otro.csv --source SYNTHETIC
```

```bash
# requiere CATALOG_API_TOKEN definido en el servidor
curl -X POST localhost:8000/api/catalog/incidents -H 'Content-Type: application/json' -H "X-Catalog-Token: $CATALOG_API_TOKEN" -d '{"id":"SYN-001","category":"SERVICIOS_PUBLICOS","subcategory":"Fuga de gas en edificio","priority":"P1","transcript":"Llamante: hay olor a gas en el palier..."}'
```

---

## Tests

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

Son offline y deterministas: fuerzan el modo mock y no usan red.
