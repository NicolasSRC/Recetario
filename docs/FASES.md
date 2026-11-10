# Fases del proyecto — estado de avance

> Documento vivo. Última actualización: **10 de noviembre de 2026**.
> Referencia: `Recetario con IA Requerimientos del proyecto.md` (sección 7).

## Leyenda

| Símbolo | Significado |
| --- | --- |
| ✅ | Completada y verificada |
| 🟡 | En curso: código hecho, validación pendiente |
| ⬜ | Pendiente |
| ⏸️ | Bloqueada por una decisión o dependencia externa |

---

## 1. Resumen general

| Fase | Alcance | Estado | Criterio de aceptación | Verificación |
| --- | --- | --- | --- | --- |
| **F1** | MVP sin interfaz: URL/texto → receta JSON validada por CLI | 🟡 **En curso** | 10 de 15 videos producen JSON válido | Código y pruebas listos; falta ejecutar con LLM real y 15 videos |
| **F2** | Persistencia y API REST | 🟡 **En curso** | OpenAPI publicado, integración en verde, reprocesar no duplica | CRUD de recetas y exportación listos; faltan jobs y Alembic |
| **F3** | Frontend: lista, detalle, edición, aprobación, exportación | ⬜ Pendiente | Flujo e2e completo en CI | — |
| **F4** | Frames y agente con herramientas | ⬜ Pendiente | Mejora medible frente a F1 en videos con texto en pantalla | — |
| **F5** | Cola, reintentos y despliegue | ⬜ Pendiente | `docker compose up` levanta todo y CI en verde | — |
| **F6** | Evals, búsqueda semántica y MCP | ⬜ Pendiente | Reporte de evals en README, búsqueda por significado, MCP con 3 herramientas | — |

**Avance global estimado:** F1 completo en código y F2 a la mitad (≈ 25 %).

---

## 2. F1 · MVP sin interfaz 🟡

**Objetivo:** demostrar que el núcleo funciona — de un texto o URL a una receta
estructurada, validada y trazable — antes de añadir base de datos o interfaz.

### 2.1 Completado

| Área | Entregable | Estado |
| --- | --- | --- |
| Entorno | `.venv` con Python 3.11.15, `pip` actualizado | ✅ |
| Dependencias | `backend/pyproject.toml` con extras `audio`, `api`, `dev` | ✅ |
| Configuración | `.env.example`, `Settings` con prefijo `RECETARIO_` | ✅ |
| Esquema | `domain/schemas.py`: `Recipe`, `RecipeDraft`, `Ingredient`, `Step`, `Source`, `Extraction`, `Status` | ✅ |
| Unidades | `domain/units.py`: normalización al conjunto fijo de RF-22 y parseo de cantidades | ✅ |
| Contexto | `domain/content.py`: unión de caption + audio + pantalla con etiquetas de fuente (RF-13) | ✅ |
| Evidencia | Inferencia de `evidence` por búsqueda en las fuentes (RE-01) | ✅ |
| Confianza | `domain/confidence.py`: puntaje global y por campo, flags de revisión (RF-24, RF-25) | ✅ |
| Reglas | `domain/validation.py`: validación de negocio y estado final | ✅ |
| URLs | `domain/urls.py`: validación y normalización de enlaces de TikTok (RF-01) | ✅ |
| Puertos | `VideoExtractor`, `Transcriber`, `RecipeLLM` (RF-05, RNF-09) | ✅ |
| Adaptadores | Manual (RF-04), yt-dlp con guardia SSRF, faster-whisper, OpenAI/instructor | ✅ |
| Proveedor LLM | Adaptador OpenCode local (`opencode run`) + adaptador API OpenAI, seleccionables por `RECETARIO_LLM_PROVIDER` | ✅ |
| Agente OpenCode | `.opencode/agents/recetario-extractor.md`: sin herramientas, solo JSON | ✅ |
| Pipeline | `pipeline/extract_recipe.py`: LLM → ensamblado → validación con reintentos (RF-23) | ✅ |
| CLI | `recetario parse` y `recetario ingest` (`--url`, archivos, `--dry-run`, `--out`) | ✅ |
| Fixtures | 4 casos: caption completo, transcripción en inglés, texto en pantalla, no-receta | ✅ |
| Pruebas | **81 tests**, cobertura **~80 %** total y >90 % en dominio | ✅ |
| Calidad | `ruff check` y `ruff format --check` limpios; `mypy` sin errores | ✅ |

### 2.2 Pendiente para cerrar F1

| Tarea | Por qué falta | Prioridad |
| --- | --- | --- |
| Ejecutar el pipeline con LLM real sobre las fixtures | La cuota gratuita de OpenCode se agotó (`provider.free-limit`, ~3,5 h de espera) | Alta |
| Reunir y anotar 15 videos de prueba | Es el criterio de aceptación (10/15); el usuario ya los tiene | Alta |
| Instalar extra `audio` y probar `yt-dlp` + `faster-whisper` reales | La ruta de descarga/transcripción no se ha ejecutado | Media |
| `git init` y primer commit etiquetado `v0.1.0` | El directorio aún no tiene commits | Media |
| ADR-001, ADR-002 y ADR-003 | Entregable de `docs/adr/` | Media |
| README mínimo de F1 | Entregable del repo | Media |

### 2.3 Cómo verificar el estado actual

```powershell
# Pruebas
.\.venv\Scripts\python.exe -m pytest backend/tests -q

# Cobertura
cd backend
..\.venv\Scripts\python.exe -m pytest tests --cov=app --cov-report=term

# Linter y tipos (desde backend/)
..\.venv\Scripts\python.exe -m ruff check .
..\.venv\Scripts\python.exe -m mypy app

# CLI
cd ..
.\.venv\Scripts\python.exe -m app.cli parse "1 1/2 tazas de harina integral"
.\.venv\Scripts\python.exe -m app.cli ingest --caption-file fixtures\caption_01.txt --dry-run
```

---

## 3. F2 · Persistencia y API 🟡

**Objetivo:** que la receta deje de ser un archivo JSON y pase a vivir en una API
con base de datos, estados de trabajo e idempotencia.

### 3.1 Completado

| Área | Entregable | Estado |
| --- | --- | --- |
| Base de datos | SQLite con SQLAlchemy 2.0: `sources`, `recipes`, `ingredients`, `steps`, `tags`, `recipe_tags`, `jobs`, `job_events` | ✅ |
| Repositorio | Conversión dominio ↔ filas, guardado idempotente por URL (RP-02) | ✅ |
| API de recetas | `POST`, `GET` (lista y detalle), `PATCH`, `DELETE` | ✅ |
| Alta manual | `POST /api/v1/recipes` sin video, para el libro de F3 | ✅ |
| Edición | `PATCH` de título, ingredientes, pasos, etiquetas y estado | ✅ |
| Búsqueda | `GET /api/v1/recipes?q=` por título e ingrediente | ✅ |
| Exportación | JSON-LD (schema.org/Recipe) y Markdown | ✅ |
| OpenAPI | Generado automáticamente en `/docs` y `/openapi.json` | ✅ |
| Pruebas | 15 tests de API (CRUD, búsqueda, exportación, duplicados, validación) | ✅ |

### 3.2 Pendiente

| Tarea | Prioridad |
| --- | --- |
| Endpoints de trabajos: `POST /jobs`, `GET /jobs/{id}`, `retry`, `cancel` | Alta |
| Procesamiento en segundo plano de la ingesta por URL | Alta |
| Migraciones con Alembic | Media |
| Exportación a PDF | Media |
| Pruebas de integración con Postgres | Media |

### 3.3 Cómo probarla

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.asgi:app --reload
```

Documentación interactiva en <http://127.0.0.1:8000/docs>.

### Criterio de aceptación

OpenAPI publicado; pruebas de integración en verde; reprocesar la misma URL no
duplica recetas.

### Dependencias

- **Resuelto:** SQLite hasta F5, migración a Postgres en el despliegue.
- F1 estable.

---

## 4. F3 · Frontend ⬜

**Objetivo:** que el flujo completo se pueda usar sin consola, con una
experiencia de **libro de recetas**: una receta por página.

### Diseño de producto: el recetario como libro

| Elemento | Comportamiento |
| --- | --- |
| Vista principal | Libro abierto a dos páginas: receta a la izquierda (ingredientes) y pasos a la derecha, o una receta por página en móvil |
| Navegación | Pasar página con botones, teclado (← →) y gestos; índice/índice lateral con todas las recetas |
| Portada | Estantería o portada del libro con el listado y la búsqueda |
| Edición | Editar ingredientes y pasos en la misma página, sin salir del libro |
| Alta manual | Crear una receta desde cero (sin video): formulario con ingredientes, pasos, tiempos y etiquetas |
| Estados | Marcar visualmente las recetas `por_revisar` (marca de agua o cinta) |
| Exportación | JSON-LD, Markdown y PDF desde la página de la receta |
| Accesibilidad | Navegación completa por teclado y contraste AA (RNF-12) |

### Tareas

1. Proyecto Next.js + TypeScript estricto + Tailwind en `frontend/`.
2. Componente `Book` con paginación, índice y atajos de teclado.
3. Página de receta con ingredientes, pasos, tiempos, etiquetas y fuente.
4. Edición en línea de ingredientes y pasos (PATCH a la API).
5. Formulario de alta manual de receta (sin video).
6. Pantalla de ingesta: pegar URL o caption/transcripción manual.
7. Pantalla de estado del trabajo con polling cada 2 s.
8. Listado con búsqueda, filtros y paginación.
9. Aprobación de recetas `por_revisar` (RF-32).
10. Botones de exportación JSON-LD / Markdown / PDF.
11. Accesibilidad básica WCAG 2.1 AA (RNF-12).
12. Test e2e con Playwright y LLM/descarga simulados.

### Criterio de aceptación

El flujo e2e completo (pegar URL → ver estado → revisar → aprobar → editar →
exportar) pasa en CI, y se puede crear una receta manual sin video.

### Dependencias

- F2 con los endpoints estables, incluido `POST /recipes` para el alta manual.

---

## 5. F4 · Frames y agente ⬜

**Objetivo:** cubrir recetas que solo están en el texto en pantalla y demostrar
un agente que decide qué fuentes usar.

### Tareas

1. Muestreo de frames con `ffmpeg` (intervalo configurable).
2. Adaptador de visión para leer texto en pantalla (modelo de visión u OCR).
3. Herramientas del agente: `get_metadata`, `transcribe_audio`,
   `extract_frames`, `validate_recipe`, `save_recipe`, `ask_user`.
4. Reglas de decisión RA-01 (saltar audio/frames si el caption basta) y
   RA-02 (pedir frames si faltan cantidades o pasos).
5. Límite de pasos (8) y tope de costo por video (RA-03).
6. Registro de cada llamada: entrada, salida, duración y costo (RA-04).
7. Comparar visión vs OCR con las evals de esta fase.

### Criterio de aceptación

Mejora medible frente a F1 en los videos que solo traen texto en pantalla.

### Dependencias

- F1 (pipeline) y decisión abierta sobre visión vs OCR.

---

## 6. F5 · Cola y despliegue ⬜

**Objetivo:** pasar de un proceso síncrono a un sistema operable y reproducible.

### Tareas

1. Celery + Redis; tareas idempotentes.
2. Reintentos con espera creciente y causa de fallo clasificada (RP-01, RP-03).
3. Reintento manual y cancelación desde la API (RP-04, RP-05).
4. `docker-compose.yml`: `api`, `worker`, `redis`, `db` (Postgres + pgvector),
   `frontend`.
5. `.env.example` definitivo y volúmenes de datos.
6. GitHub Actions: linter, tipos, tests, build de imágenes, escaneo de
   dependencias.
7. Migración de SQLite a Postgres si se empezó con SQLite.

### Criterio de aceptación

`docker compose up` levanta todo desde cero y el CI queda en verde.

### Dependencias

- F2 y F3 terminadas.

---

## 7. F6 · Evals, búsqueda y MCP ⬜

**Objetivo:** convertir la calidad en una cifra y cerrar los entregables del CV.

### Tareas

1. Dataset de 15–20 videos anotados a mano (ES/EN), con los cuatro tipos de
   caso: receta en caption, solo audio, solo texto en pantalla, no-receta.
2. Fixtures de captions y transcripciones para que las evals corran sin TikTok.
3. Script de métricas: recall/precisión de ingredientes, exactitud de cantidad
   y unidad, cobertura y orden de pasos, esquema válido al primer intento,
   detección de no-receta, latencia y costo.
4. Reportes versionados en `evals/reports/` con modelo y versión del prompt.
5. Búsqueda por texto y búsqueda semántica con `pgvector` (RF-35).
6. Escalado de porciones (RF-34), etiquetas sugeridas (RF-33), favoritas y
   lista de compras (RF-37).
7. Servidor MCP con `buscar_receta`, `agregar_receta`, `obtener_receta` (RF-42).
8. README final: arquitectura, decisiones, límites, resultados y GIF de demo.
9. Nota legal y licencia (RNF-07).

### Criterio de aceptación

Reporte de evals en el README; búsqueda por significado funcionando; MCP con
tres herramientas.

### Dependencias

- F1–F5 terminadas.

---

## 8. Mapa de requerimientos por fase

| Bloque | Requerimientos | Fase principal |
| --- | --- | --- |
| Ingesta | RF-01, RF-02, RF-04 | F1 |
| Ingesta (idempotencia, lote) | RF-03, RF-06 | F2 / F5 |
| Multimodal | RF-10, RF-11, RF-13, RF-14 | F1 |
| Texto en pantalla | RF-12 | F4 |
| Estructuración y validación | RF-20 – RF-26 | F1 |
| Recetario | RF-30 – RF-32 | F2 / F3 |
| Búsqueda, filtros, escalado | RF-33 – RF-36 | F6 |
| Favoritas y lista de compras | RF-37 | F6 |
| Exportación e integración | RF-40, RF-41, RF-43 | F2 |
| Servidor MCP | RF-42 | F6 |
| Agente | RA-01 – RA-06 | F4 |
| Configuración del modelo | RA-07 | F1 ✅ |
| Pipeline asíncrono | RP-01 – RP-06 | F5 |
| Rendimiento, costo, seguridad | RNF-01 – RNF-06 | F1 / F5 |
| Observabilidad | RNF-08 | F5 |
| Mantenibilidad y calidad | RNF-09, RNF-10 | F1 ✅ / continuo |
| Portabilidad | RNF-11 | F5 |
| Accesibilidad | RNF-12 | F3 |
| Documentación | RNF-13 | F6 |

---

## 9. Próximos pasos inmediatos

1. **Cerrar F2**: endpoints de trabajos (`POST /jobs`, `GET /jobs/{id}`, `retry`,
   `cancel`) y procesamiento en segundo plano.
2. **Abrir F3**: maqueta del libro con datos de la API (una receta por página,
   edición en línea y alta manual).
3. **Validar F1** cuando la cuota del modelo se restablezca: 10/15 JSON válidos.
4. **Reintentar la ingesta real** con `yt-dlp` + `faster-whisper` instalados.

---

## 10. Decisiones abiertas que afectan las próximas fases

| Decisión | Afecta | Estado |
| --- | --- | --- |
| Modelo de lenguaje y tope de costo | F1, F4, F6 | **Resuelto:** OpenCode local con `deepseek-v4.1-flash-free`; adaptador OpenAI como alternativa |
| Postgres desde F2 o SQLite hasta F5 | F2, F5 | Pendiente (recomendado: SQLite) |
| Visión vs OCR para texto en pantalla | F4 | Pendiente (se decide con evals) |
| Dónde se despliega la demo | F5 | Pendiente |
| Repositorio público desde el inicio | F6 (dataset) | Pendiente |
| Transcripción local vs API | F1 | **Resuelto:** local por defecto |
| Estilo del frontend | F3 | **Resuelto:** libro, una receta por página |
