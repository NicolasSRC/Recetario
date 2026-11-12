# Fases del proyecto — estado de avance

> Documento vivo. Última actualización: **11 de noviembre de 2026**.
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
| **F1** | MVP sin interfaz: URL/texto → receta JSON validada por CLI | 🟡 **En curso** | 10 de 15 videos producen JSON válido | Metadatos 15/15, audio y frames reales verificados; falta el LLM real (cuota agotada) |
| **F2** | Persistencia y API REST | ✅ **Completada** | OpenAPI publicado, integración en verde, reprocesar no duplica | CRUD, exportación, trabajos en segundo plano y 141 tests en verde |
| **F3** | Frontend: libro, edición, aprobación, exportación | ✅ **Completada** | Flujo e2e completo en CI | E2E de Playwright (2 casos), PDF, CI de backend/frontend/e2e |
| **F4** | Frames y agente con herramientas | 🟡 **En curso** | Mejora medible frente a F1 en videos con texto en pantalla | Frames, OCR/visión, agente, traza y eval implementados y probados con 15 videos reales; el lote real casi no trae texto en pantalla, así que la mejora no es medible todavía |
| **F5** | Cola, reintentos y despliegue | ⬜ Pendiente | `docker compose up` levanta todo y CI en verde | — |
| **F6** | Evals, búsqueda semántica y MCP | ⬜ Pendiente | Reporte de evals en README, búsqueda por significado, MCP con 3 herramientas | — |

**Avance global estimado:** F1 completo en código, F2 y F3 cerradas, F4
implementada y pendiente de validación con videos reales (≈ 65 %).

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
| Pruebas | **141 tests** en total (dominio, adaptadores, API, trabajos y agente), cobertura >90 % en dominio | ✅ |
| Calidad | `ruff check`, `ruff format --check` y `mypy` limpios | ✅ |

### 2.2 Pendiente para cerrar F1

| Tarea | Por qué falta | Prioridad |
| --- | --- | --- |
| Ejecutar el pipeline con LLM real sobre las fixtures | La cuota gratuita de OpenCode sigue agotada (`provider.free-limit`) | Alta |
| Contar 10/15 JSON válidos con los 15 videos reales | Los metadatos (15/15), el audio y los frames ya están verificados; solo falta la extracción con LLM | Alta |

> **Verificado con datos reales (11 nov 2026):** las 15 URLs de TikTok
> responden con yt-dlp 2026.10.26 (duraciones 14–164 s, captions de 59–1850
> caracteres), `faster-whisper small` transcribe español real (video 01: 1742
> caracteres en 48,7 s) y la ruta de frames + OCR funciona de punta a punta.
> El único bloqueo para cerrar el criterio 10/15 es la cuota del modelo.

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

## 3. F2 · Persistencia y API ✅

**Objetivo:** que la receta deje de ser un archivo JSON y pase a vivir en una API
con base de datos, estados de trabajo e idempotencia.

### 3.1 Completado

| Área | Entregable | Estado |
| --- | --- | --- |
| Base de datos | SQLite con SQLAlchemy 2.0: `sources`, `recipes`, `ingredients`, `steps`, `tags`, `recipe_tags`, `jobs`, `job_events` | ✅ |
| Repositorio | Conversión dominio ↔ filas, guardado idempotente por URL (RP-02) | ✅ |
| API de recetas | `POST`, `GET` (lista y detalle), `PATCH`, `DELETE` | ✅ |
| Alta manual | `POST /api/v1/recipes` sin video; se aprueba al guardar (`confianza 1.0`, sin flags) | ✅ |
| Edición | `PATCH` de título, ingredientes, pasos, etiquetas y estado | ✅ |
| Búsqueda | `GET /api/v1/recipes?q=` por título e ingrediente | ✅ |
| Exportación | JSON-LD (schema.org/Recipe) y Markdown | ✅ |
| Trabajos | `POST /api/v1/jobs`, `GET /jobs/{id}`, `retry`, `cancel` con estados `en_cola/procesando/lista/fallida/cancelada` | ✅ |
| Etapas | `descargando → transcribiendo → extrayendo → guardando`, visibles para el polling de la UI | ✅ |
| Errores | Códigos estables: `url_invalida`, `descarga_bloqueada`, `transcripcion_vacia`, `esquema_invalido`, `cuota_agotada`, `no_es_receta`, `error_interno` | ✅ |
| Procesamiento | `ThreadJobRunner` en hilos daemon; sustituible por una cola real en F5 | ✅ |
| CORS | Orígenes locales configurables (`cors_origins` + `cors_origin_regex`) | ✅ |
| OpenAPI | Generado automáticamente en `/docs` y `/openapi.json` | ✅ |
| Pruebas | 141 tests: CRUD, búsqueda, exportación, duplicados, validación, trabajos, agente y clasificación de errores | ✅ |

### 3.2 Pendiente (no bloquea el criterio de aceptación)

| Tarea | Prioridad |
| --- | --- |
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

## 4. F3 · Frontend ✅

**Objetivo:** que el flujo completo se pueda usar sin consola, con una
experiencia de **libro de recetas**: una receta por página.

### Diseño de producto: el recetario como libro

| Elemento | Comportamiento |
| --- | --- |
| Vista principal | Libro abierto a dos páginas: receta a la izquierda (ingredientes) y pasos a la derecha, o una receta por página en móvil |
| Navegación | Pasar página con botones, teclado (← →) y contador de posición; la estantería hace de índice |
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

### 4.1 Completado

| Área | Entregable | Estado |
| --- | --- | --- |
| Proyecto | Next.js 16 (App Router), React 19, TypeScript estricto y Tailwind 4 | ✅ |
| Estantería | Portada con búsqueda (título/ingrediente), filtros por estado y tarjetas con lomo de color | ✅ |
| Libro | Vista a doble página: ingredientes a la izquierda, pasos y fuente a la derecha; una columna en móvil | ✅ |
| Navegación | Botones anterior/siguiente, contador de página y flechas ← → del teclado | ✅ |
| Edición | `RecipeForm` reutilizable: título, tiempos, raciones, ingredientes, pasos, etiquetas y utensilios; guarda con `PATCH` | ✅ |
| Alta manual | `/nueva`: receta sin video; entra aprobada y sin banner de revisión | ✅ |
| Ingesta | `/importar`: URL de TikTok o texto pegado; polling cada 2 s y línea de etapas | ✅ |
| Estados | Insignias `aprobada/por_revisar/descartada` y cinta de aviso con los flags del modelo | ✅ |
| Acciones | Aprobar, borrar, imprimir (`window.print`), exportar JSON-LD, Markdown y PDF | ✅ |
| Responsive | Diseño de escritorio, tableta y móvil | ✅ |
| Calidad | `npm run lint`, `npm run typecheck` y `npm run build` limpios | ✅ |
| E2E | Playwright sobre la app real: alta manual/edición/PDF/búsqueda e ingesta simulada con revisión y aprobación | ✅ |
| CI | GitHub Actions: backend (ruff, mypy, pytest), frontend (lint, typecheck, build) y e2e (Chromium) | ✅ |

### 4.2 Pendiente (no bloquea el criterio de aceptación)

| Tarea | Prioridad |
| --- | --- |
| Paginación real en la estantería cuando haya muchas recetas | Baja |
| Revisión visual con datos reales (los e2e usan datos simulados) | Baja |

### 4.3 Cómo probarla

```powershell
# 1) API
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.asgi:app --reload

# 2) Libro (en otra terminal)
cd frontend
npm install
cmd /c "npm run dev"
```

Abrir <http://localhost:3000>. La URL de la API se configura con
`NEXT_PUBLIC_API_URL` (por defecto `http://127.0.0.1:8000`).

### Criterio de aceptación

El flujo e2e completo (pegar URL → ver estado → revisar → aprobar → editar →
exportar) pasa en CI, y se puede crear una receta manual sin video.

### Dependencias

- F2 con los endpoints estables, incluido `POST /recipes` para el alta manual.

---

## 5. F4 · Frames y agente 🟡

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

### 5.1 Completado

| Área | Entregable | Estado |
| --- | --- | --- |
| Dominio | `domain/agent.py`: límites, traza, heurísticas de caption, cantidades faltantes y calidad de receta | ✅ |
| Contenido | `Frame` y `ScreenTextResult` en `domain/content.py` | ✅ |
| Puertos | `FrameSampler`, `ScreenTextReader` y `ScreenTextExtractor` | ✅ |
| Frames | `FFmpegFrameSampler` con intervalo, tope de frames y error claro si falta ffmpeg | ✅ |
| OCR | `TesseractScreenTextReader` con umbral de confianza, filtro de tokens y descarte de frames sin palabra fuerte | ✅ |
| Visión | `VisionScreenTextReader` sobre API compatible con OpenAI, con prompt anti-inyección | ✅ |
| Selección | `vision_factory.py`: `RECETARIO_SCREEN_TEXT_READER=tesseract\|vision\|none` | ✅ |
| Agente | `RecipeAgent` determinista: RA-01, RA-02, RA-03, RA-04 y RA-05; herramientas inyectables | ✅ |
| Traza | Cada llamada se guarda en `job_events` (paso, entrada, salida, duración, costo, error) y se expone en `JobOut.events` | ✅ |
| Trabajos | Etapa `leyendo_pantalla`, costo por trabajo y traza persistida también al fallar o cancelar | ✅ |
| CLI | `ingest --url` usa el agente; `--no-frames` y `--interval`; comando `frames` para un video local | ✅ |
| Eval | `python -m app.evals.screen_text`: F1 por palabras para comparar OCR y visión sobre los mismos frames | ✅ |
| Frontend | Etapa «Leer el texto en pantalla» y panel «Qué hizo el agente» con duración, errores y costo | ✅ |
| Verificación OCR | Tesseract 5.4 + `spa` instalados; video sintético de 3 frames leído completo y F1 = 1.0 en la eval | ✅ |
| Validación real | 15/15 metadatos, 12/15 con audio o caption utilizable, OCR limpio sobre frames reales (ver 5.4) | ✅ |
| Pruebas | Agente (RA-01/02/03/04/05), frames, OCR, visión, traza en la API y métrica de la eval | ✅ |

### 5.2 Pendiente para cerrar F4

| Tarea | Por qué falta | Prioridad |
| --- | --- | --- |
| Medir OCR vs visión con videos reales | Falta la llave de visión y videos anotados; el lote real casi no tiene texto de receta en pantalla | Alta |
| Conseguir videos con ingredientes/cantidades visibles | Es el caso de uso que justifica los frames; el lote actual es de voz en off | Alta |
| Decidir qué hacer con los videos 02, 03 y 10 | **Resuelto:** el agente registra el fallo del audio y continúa con el caption (prueba `test_sin_voz_continua_con_el_caption`) | — |

### 5.3 Cómo probarla

```powershell
# Frames de un video local (requiere ffmpeg y, para OCR, Tesseract + extra [ocr])
cd backend
..\.venv\Scripts\python.exe -m app.cli frames --video C:\ruta\video.mp4 --interval 2 --out frames.txt

# Ingesta por URL con agente (sin frames, para aislar el resto)
..\.venv\Scripts\python.exe -m app.cli ingest --url https://vm.tiktok.com/XXXX/ --no-frames

# Comparar lectores sobre los mismos frames
..\.venv\Scripts\python.exe -m app.evals.screen_text --video C:\ruta\video.mp4 --expected fixtures\screen_text_01.txt --readers tesseract,vision
```

Variables nuevas en `.env.example`: `RECETARIO_FRAMES_ENABLED`,
`RECETARIO_FRAME_INTERVAL_S`, `RECETARIO_MAX_FRAMES_PER_VIDEO`,
`RECETARIO_SCREEN_TEXT_READER`, `RECETARIO_TESSERACT_*`,
`RECETARIO_VISION_*`, `RECETARIO_MAX_AGENT_STEPS` y
`RECETARIO_LLM_COST_USD_PER_EXTRACTION`.

### 5.4 Validación con los 15 videos reales (11 nov 2026)

Lote completo ejecutado con los adaptadores reales (yt-dlp, faster-whisper
`small`, ffmpeg y Tesseract `spa+eng`, intervalo 2 s):

| # | Caption RA-01 | Audio (caracteres) | Texto en pantalla detectado |
| --- | --- | --- | --- |
| 01 | incompleto | 1742 | `MES` |
| 02 | incompleto | **vacío** | no ejecutado (falló antes) |
| 03 | incompleto | **vacío** | no ejecutado (falló antes) |
| 04 | incompleto | 1489 | ruido (`2 2`, `eee 4`) |
| 05 | **completo** | omitido por RA-01 | `CapCut` |
| 06 | incompleto | 1240 | títulos de platos |
| 07 | **completo** | omitido por RA-01 | frases en inglés |
| 08 | incompleto | 54 | — |
| 09 | incompleto | 230 | — |
| 10 | incompleto | **vacío** | no ejecutado (falló antes) |
| 11 | **completo** | omitido por RA-01 | ruido (`7 4`) |
| 12 | incompleto | 1411 | `Cúrcuma.` |
| 13 | incompleto | 244 | `Papas rellenas` |
| 14 | incompleto | 3 | — |
| 15 | incompleto | 1915 | — |

**Resultados:**

- **Metadatos: 15/15.** yt-dlp resuelve todos los enlaces cortos (14–164 s,
  captions de 59–1850 caracteres).
- **RA-01: 3/15 captions completos** (05, 07, 11). La heurística se ajustó con
  estos datos para aceptar captions en prosa con viñetas inline y rechazar los
  que solo traen ingredientes o solo pasos.
- **Audio: 12/15 con transcripción.** 01, 04, 06, 12 y 15 superan los 1200
  caracteres; 08 (54) y 14 (3) son marginales. Los videos 02, 03 y 10 no
  tienen voz reconocible (audio musical). En la app esto **no aborta**: el
  agente registra la llamada fallida y sigue solo con el caption (cubierto por
  `test_sin_voz_continua_con_el_caption`). El lote de validación los marca como
  fallo porque el script de sonda llamaba al transcriptor directamente.
- **OCR: limpio pero poco útil.** Tras subir el umbral a 60, exigir una palabra
  fuerte y filtrar tokens de una o dos letras, solo quedan títulos
  (`ARROZ`, `Papas rellenas`, `Sopa de papa CREMOSA`) y algo de ruido de
  logotipos. Ningún video del lote muestra ingredientes con cantidad en
  pantalla, que es el caso que F4 debía cubrir.
- **Eval sintética: F1 = 1.0** sobre un video de 3 frames con
  `INGREDIENTES / 200 g de harina / 2 huevos y sal`, lo que demuestra que la
  cadena frames → OCR → texto funciona cuando hay texto legible.

**Conclusión:** la implementación de F4 está verificada de punta a punta, pero
el criterio «mejora medible frente a F1» **no se puede demostrar con este
lote**: son recetas habladas, no recetas escritas en pantalla. Para cerrarlo
hace falta un lote con texto de ingredientes visible o anotar manualmente los
frames y comparar OCR contra visión.

### Criterio de aceptación

Mejora medible frente a F1 en los videos que solo traen texto en pantalla.

### Dependencias

- F1 (pipeline) y F3 (panel de traza) terminadas.
- Decisión visión vs OCR: **resuelto por configuración** (OCR local por
  defecto, visión seleccionable); falta la medición comparativa.

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

1. **Cerrar F1** cuando la cuota del modelo se restablezca: correr
   `ingest --url` sobre los 15 videos y contar 10/15 JSON válidos. Metadatos,
   audio y frames ya están verificados.
2. **Cerrar F4**: conseguir videos con ingredientes/cantidades visibles o
   configurar visión, y medir OCR vs visión con `app.evals.screen_text`.
3. **Videos 02, 03 y 10:** el agente ya continúa con el caption cuando no hay
   voz; si el LLM no alcanza, se marcan como `por_revisar` o no-receta.
4. **Preparar F5**: sustituir `ThreadJobRunner` por Celery/Redis, añadir
   `docker compose` y migrar a Postgres.

---

## 10. Decisiones abiertas que afectan las próximas fases

| Decisión | Afecta | Estado |
| --- | --- | --- |
| Modelo de lenguaje y tope de costo | F1, F4, F6 | **Resuelto:** OpenCode local con `deepseek-v4.1-flash-free`; adaptador OpenAI como alternativa |
| Postgres desde F2 o SQLite hasta F5 | F2, F5 | **Resuelto:** SQLite hasta F5 (`data/recetario.db`), sin Alembic todavía |
| Visión vs OCR para texto en pantalla | F4 | **Resuelto por configuración:** OCR local por defecto, visión seleccionable con `RECETARIO_SCREEN_TEXT_READER`; falta la medición comparativa |
| Política del agente | F4 | **Resuelto:** determinista y auditable (ADR-005), no un selector de herramientas por LLM |
| Dónde se despliega la demo | F5 | Pendiente |
| Repositorio público desde el inicio | F6 (dataset) | Pendiente |
| Transcripción local vs API | F1 | **Resuelto:** local por defecto |
| Estilo del frontend | F3 | **Resuelto:** libro, una receta por página (ADR-004) |
| Ejecución de trabajos en F2 | F2, F5 | **Resuelto:** hilos daemon con interfaz `JobRunner`; cola real en F5 |
