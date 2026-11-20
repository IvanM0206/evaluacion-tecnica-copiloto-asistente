# Decisiones de diseño

Este documento explica **por qué** el prototipo está armado como está: supuestos, trade-offs y lo que haría con más tiempo.
Para correrlo y usarlo, ver [README.md](README.md).

---

## 1. Producto: pensado para un operador bajo estrés

**Supuesto central.** El operador está en línea con alguien en crisis. No tiene tiempo de leer párrafos ni de pelearse con la interfaz. El copiloto **sugiere** y el operador **decide**. Nada se deriva sin su validación.

| Decisión | Por qué |
|---|---|
| Pantalla inicial con una sola acción (cargar la transcripción) | Cero decisiones antes de empezar. La plantilla de ejemplo deja probar el flujo sin escribir. |
| Transcripción en modo lectura, separada por turnos | Se lee de un vistazo quién dijo qué. Editar es explícito (botón), así no se modifica el relato por accidente. |
| Sugerencia en secciones plegables, con scroll propio y el botón **Derivar** siempre visible | El operador pliega lo que ya chequeó y nunca tiene que buscar el botón final. |
| El resumen de cada sección se ve con la sección plegada (prioridad, calle, "3/8 respondidas") | Permite leer el estado general sin abrir nada. |
| Checklist con **pendientes primero** | Lo que importa es la próxima pregunta que hay que hacer, no lo que ya se sabe. |
| Cada dato muestra su **evidencia literal** o "No mencionado: preguntar" | El operador ve en qué se basa el sistema y qué tiene que preguntar. Transforma la incertidumbre en una acción. |
| Advertencias arriba de todo | Lo dudoso (baja similitud, calle sin evidencia, prioridad discutible) se ve primero. |
| Atajos de teclado (`accesskey`) con ayuda flotante | El operador tiene las manos en el teclado. La ayuda se abre con hover o foco y no tapa los campos. |
| Si falla **Derivar**, se conservan las ediciones | Perder trabajo en medio de una llamada es inaceptable. |
| Los recursos se muestran como "sugeridos (decide el despachador)" | Es el rol real del operador en el CAD: no despacha. |

**Front sin JavaScript.** Es una decisión deliberada: menos superficie, nada que se rompa en el navegador de un puesto viejo y un stack 100 % Python.
Las interacciones se resuelven con HTML y CSS nativos:

- Acordeón: `<details>`.
- Modos ver/editar/nueva de la columna izquierda: radios + CSS.
- Ayuda de atajos: `:hover`/`:focus-within`.
- Loader: una página intermedia con `<meta refresh>`. El navegador la mantiene visible mientras el servidor analiza.

El costo es no tener streaming ni actualizaciones parciales. Ver "Mejoras futuras".

---

## 2. Arquitectura en 4 capas

```
frontend/ ──HTTP──▶ api/ ──▶ services/ ──▶ backend/ ──▶ SQLite
```

- **Cada capa importa solo la de abajo.** Los servicios no conocen HTTP y la API no conoce el ORM. El front ni siquiera importa Python de las otras capas: consume la API por HTTP con sus propios *view models*.
- **El front llama a la API por HTTP aunque estén en el mismo proceso.** Así el contrato real es la API, el front se puede reemplazar por otro cliente (por ejemplo el CAD) y se separan en dos servicios cambiando `API_BASE_URL`. El costo es un salto HTTP local y la necesidad de que gunicorn tenga `--threads > 1`, porque una vista se llama a sí misma.
- **Pydantic en cada límite.** Los modelos de servicio son los schemas de la API (Django Ninja) y el front valida las respuestas de nuevo con sus view models. Un cambio de contrato rompe ruidosamente, no en silencio.
- **Código en inglés, producto en español.** Los campos de los modelos (ORM, servicios, JSON de la API, view models) están en inglés y son los mismos en todas las capas (`street`, `street_number`, `priority`…). Los textos que ve el operador, los prompts y los warnings están en español rioplatense. Solo el CSV conserva sus columnas originales en español; `seed_dataset` las mapea.
- **Las reglas de capas se verifican.** `tests/test_architecture.py` revisa los imports por AST: si alguien hace que el front importe `services`, el test falla.
- **Django y no FastAPI.** Por ORM y migraciones, admin gratis para inspeccionar casos y cartas, templates y sesiones. Ninja aporta el tipado y el OpenAPI que daría FastAPI.
- **SQLite.** Alcanza para un prototipo de un solo puesto y se persiste en un volumen Docker. Pasar a Postgres es cambiar `DATABASES`.

---

## 3. IA: el LLM como fuente **no confiable**

El riesgo principal de un copiloto de emergencias es que **alucine una dirección o una prioridad**. Por eso la salida del provider, sea mock o LLM, nunca llega directo al operador. Pasa por este pipeline:

```
transcripción
  ├─▶ retrieval TF-IDF sobre el catálogo (k=5, leave-one-out)
  ├─▶ provider.extract(...) ─▶ RawExtraction (Pydantic, cada dato con "evidence")
  └─▶ grounding + validación ─▶ CopilotSuggestion
```

1. **Evidencia literal obligatoria.** Cada dato de ubicación y cada respuesta del checklist trae `evidence`. `is_grounded` verifica que esté en la transcripción, literal o con al menos 85 % de solapamiento, **y que el valor esté contenido en su propia evidencia**. Así se descarta, por ejemplo, `altura="1243"` citando "al 1234". Si falla, el dato se marca **sin evidencia**, se avisa y baja la certeza.
2. **Preguntas cerradas al catálogo, con sugerencias aparte y marcadas.** El checklist sale del protocolo del caso de referencia. Las preguntas que el LLM invente o reformule dentro del checklist **se descartan** y se avisa cuántas. Aparte, el LLM puede proponer **hasta 3 preguntas extra** que el relato no responde (por ejemplo, si hay chicos en el edificio). Llegan por un campo separado, se sanean (sin duplicar el protocolo, largo acotado, tope 3), entran siempre como **pendientes** y se muestran con la etiqueta **"Sugerida por IA"**: el operador ve qué es protocolo y qué es una propuesta del modelo, y decide si preguntarlo. No suman ni restan certeza.
3. **Un protocolo por llamada (*anchor*).** Preguntas, instrucciones pre-arribo y recursos salen del caso más similar **de la categoría final**. Así no se mezclan protocolos (por ejemplo, instrucciones de incendio en una emergencia médica). Si el LLM cambia la categoría, el checklist se recalcula para la nueva. Si entre los 5 casos más parecidos no hay ninguno de esa categoría, se busca en todo el catálogo, **pero solo si el caso supera la similitud mínima**: con la fuga de gas en vereda, el único candidato era una marquesina caída, y un checklist de marquesina para una fuga de gas confunde más de lo que ayuda. En ese caso se avisa "aplicar protocolo general".
4. **Normalización contra un gazetteer.** Las calles se cruzan con las del dataset (match exacto, sufijo o difuso: "Scalabrini Ortiz" → "Av. Raúl Scalabrini Ortiz").
5. **Advertencias explícitas** por calle no detectada o no literal, falta de altura o intersección, baja similitud (< 0.2) o prioridad distinta a la del caso de referencia.
6. **Certeza heurística**, no calibrada: combina ubicación con evidencia, similitud y proporción de respuestas con evidencia. Se muestra como orientación, no como probabilidad.

### Dual provider y resiliencia

- **`mock`** (por defecto): determinista, offline y gratis. Usa regex de direcciones, léxico por categoría, banderas rojas que fuerzan **P1** (no respira, atrapado, olor a gas, derrame de combustible…), prioridad del vecino más cercano y checklist por solapamiento de tokens.
- **`anthropic`**: Claude con **structured outputs** (`messages.parse` con `RawExtraction` como schema) y los casos similares como few-shot. El prompt pide extraer y no inventar, con evidencia literal.
- **Prompts como módulo propio** (`services/prompts/`): el system prompt se arma con secciones con nombre (rol, grounding, clasificación, checklist, preguntas sugeridas, resumen) y una versión. Las reglas del dominio se escriben una vez y un skill o agente nuevo compone las que necesita (`with_sections`), sin tocar el código del provider.
- **Fallback.** Errores de API, rate limit, falta de conexión, rechazo, `max_tokens` o JSON inválido o truncado se convierten en `ProviderError`. El SDK valida el JSON al parsear: esos errores también se capturan, cosa que detectaron los tests. El orquestador responde con el mock y una advertencia visible: **el operador nunca se queda sin sugerencia**. Para que eso se cumpla también ante un LLM lento, el peor caso del provider (2 intentos de 20 s) queda por debajo del timeout del front (45 s). En Claude Opus 5.5 el razonamiento interno no se puede apagar y cuenta contra `max_tokens`, así que la extracción corre con esfuerzo `low` y `max_tokens=16000`: es una tarea de extraer, no de razonar, y así no se corta ni tarda de más.
- Agregar otro provider (OpenAI, Gemini, Ollama) es implementar el Protocol `ExtractionProvider` y registrarlo en `services/container.py`.

### Prioridad: el error que importa es el sub-triage

Sugerir P1 para algo P2 cuesta recursos. Sugerir P3 para algo P1 puede costar una vida. Por eso las banderas rojas escalan a P1 **por encima** de lo que diga el vecino más cercano: ante la duda, el copiloto prefiere sobre-priorizar.

---

## 4. Datos

- **30 casos, casi todas las subcategorías aparecen una sola vez.** No alcanza para entrenar ni para hacer fine-tuning. Se usa como **catálogo de referencia**: retrieval, few-shot para el LLM y protocolos.
- **Las llamadas del dataset se analizan con leave-one-out.** Al analizar una llamada del dataset, su propio caso se excluye del retrieval. Como casi todas las subcategorías aparecen una vez, se analiza como un tipo de incidente nuevo y toma el protocolo de su vecino más cercano. La plantilla por defecto es una fractura expuesta, que toma el protocolo de traumatismo por caída: coherente y honesto. No desactivé el leave-one-out en el panel porque el demo mostraría el ground truth copiado.
- **Sobreajuste.** Las reglas del mock son genéricas (señales de alarma, léxico por categoría), no ajustadas caso por caso: con 30 ejemplos, perseguir que acierte todos sería memorizar el dataset.
- **Incidentes sintéticos.** Con `seed_dataset --source SYNTHETIC` o `POST /api/catalog/incidents` se amplía el catálogo sin reiniciar. Cada proceso detecta el cambio con un `COUNT` barato y reconstruye sus índices, así que funciona también con varios workers de gunicorn. Limitación conocida: modificar un caso existente (admin o re-seed del mismo id) no cambia el `COUNT` y requiere reiniciar. La solución sería una versión del catálogo o `max(updated_at)`.
- **El catálogo es superficie de ataque.** Lo que se carga ahí termina leído a un llamante (instrucciones pre-arribo) y dentro del prompt del LLM. Por eso la escritura por API exige `X-Catalog-Token` y está **deshabilitada por defecto**. Al ser un header y no una cookie, tampoco es vulnerable a CSRF.

---

## 5. Otros trade-offs

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| TF-IDF en Python puro | Embeddings / vector DB | 30 casos: no se justifica una dependencia pesada ni una llamada externa. Es determinista y offline. |
| La sugerencia se guarda en la sesión y solo se reemplaza cuando el análisis nuevo sale bien | Recalcular en cada request | Recargar la página no vuelve a llamar (ni a cobrar) al LLM. Si falla un análisis nuevo, el operador conserva el anterior y su texto. |
| La carta solo se persiste | Integración real con el CAD | Fuera del alcance del challenge. Es el punto de extensión natural (`CallCardService.derive`). |
| Botón **Analizar simulando LLM** en modo mock | Ocultar las funciones que solo tiene el LLM | Sin key ni red igual se puede ver y evaluar cómo queda el panel con el modelo. Las respuestas son fijas por categoría y todo va rotulado como "simulación" (badge, advertencia y etiqueta en cada pregunta): nunca se presentan como salida de un modelo. |
| `confidence` heurística | Calibración | Sin datos suficientes para calibrar. Se aclara en la UI y en el código. |
| Si falla la validación de "Derivar", se re-renderiza con status 422 | Validación en el navegador con `required` | Un campo `required` dentro de una sección plegada no se puede enfocar. |

---

## 6. Mejoras futuras

1. **Mapa y contexto de la zona.** Diseño acordado y postergado:
   - **Datos:** USIG (servicio oficial de la Ciudad) para normalizar la dirección, obtener coordenadas, barrio, comuna y esquinas reales. Datasets abiertos de la Ciudad, incluidos en el repo, como respaldo sin conexión, con un aviso claro cuando se usa el respaldo.
   - **Vista:** mapa de OpenStreetMap embebido, sin JavaScript propio. Si la geocodificación falla, la sección lo aclara y el mapa queda deshabilitado.
   - **Lugares cercanos (≤ 500 m, 5 por tipo):** hospitales, bomberos, comisarías, escuelas, subte, estaciones de servicio y plazas.
   - **Con LLM:** consideraciones de la zona y preguntas para ubicar mejor el hecho, limitadas a los lugares de la lista y marcadas como IA.
   - **En la carta:** se guardan las coordenadas y la dirección normalizada. Editar la dirección actualiza el mapa con un botón "Actualizar mapa".
   - **Por qué quedó afuera:** la red del entorno de desarrollo no llega a los servicios de la Ciudad, así que no se pudo verificar la API ni bajar los datos reales, y no se inventan ubicaciones de servicios de emergencia.
2. **Streaming de la llamada en vivo.** Hoy se analiza una transcripción completa. En producción llegaría por fragmentos desde el speech-to-text: análisis incremental, checklist que se completa en vivo y actualizaciones parciales (HTMX o SSE).
3. **Hand-off real al CAD.** Enviar la carta al sistema de despacho, con acuse y reintentos.
4. **Geocodificación real.** Ver el punto 1: hoy el gazetteer solo conoce las calles del dataset.
5. **Evaluación del copiloto.** Medir categoría, prioridad, recall de P1 y ubicación sobre un set de casos más grande (sintéticos generados y revisados por operadores), y comparar mock vs. LLM en CI.
6. **Feedback loop.** Guardar qué corrigió el operador respecto de la sugerencia. Es la mejor señal para mejorar prompts, banderas rojas y el catálogo.
7. **Más providers** (OpenAI, Gemini, Ollama local para operar sin internet) y selección por costo y latencia.
8. **Operación.** Autenticación de operadores, auditoría de quién derivó qué, Postgres y separar front y API en dos servicios (ya preparado con `API_BASE_URL`).
