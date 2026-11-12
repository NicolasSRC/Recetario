# Recetario con IA

Convierte un enlace de TikTok de cocina en una receta estructurada, validada y
guardada en un recetario propio que se puede buscar, editar y exportar.

> **Estado:** F2 y F3 completadas; F4 implementada y verificada de punta a punta
> con 15 videos reales (metadatos, audio, frames y OCR). Falta la extracción con
> LLM real por cuota del modelo gratuito y la medición OCR vs visión, porque el
> lote disponible es de recetas habladas y casi no trae texto en pantalla.
> Ver [`docs/FASES.md`](docs/FASES.md).

## Qué resuelve

- Ingesta de una URL de TikTok o de texto manual (caption, transcripción).
- Unión de caption, audio y texto en pantalla con la fuente de cada dato.
- Muestreo de frames con `ffmpeg` y lectura del texto en pantalla con OCR local
  (Tesseract) o un modelo de visión.
- Un agente que decide qué fuentes usar: si el caption basta, se salta audio y
  frames; si faltan cantidades o pasos, los pide.
- Extracción a un esquema único, compatible con schema.org/Recipe.
- Validación con reintentos y marca `por_revisar` cuando falta evidencia.
- Trabajos de ingesta en segundo plano con etapas, reintentos, cancelación,
  costo y traza de cada herramienta.
- Recetario en forma de libro: una receta por pliego, editable y exportable.
- Alta manual de recetas sin video, aprobadas al guardar.

## Stack

| Capa | Elección |
| --- | --- |
| Lenguaje | Python 3.11 |
| Esquema y validación | Pydantic 2 |
| LLM | OpenCode local (`deepseek-v4.1-flash-free`) u API compatible con OpenAI |
| Descarga | yt-dlp + ffmpeg |
| Transcripción | faster-whisper (local) |
| Texto en pantalla | ffmpeg + Tesseract OCR (local) o modelo de visión |
| Agente | Reglas deterministas RA-01 a RA-05 con herramientas inyectables |
| API y base de datos | FastAPI + SQLAlchemy 2 + SQLite (Postgres en F5) |
| Frontend | Next.js 16 + React 19 + TypeScript + Tailwind 4 |

## Arranque local (desarrollo)

### 1. Requisitos

| Herramienta | Para qué |
| --- | --- |
| Python 3.11 | Backend |
| Node.js 22 | Libro (frontend) |
| ffmpeg | Muestreo de frames (F4) |
| Tesseract + `spa` | OCR local (opcional) |
| OpenCode | LLM local sin llave (o una API compatible con OpenAI) |

### 2. Instalación (una sola vez)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -e "backend[api,audio,ocr,queue,dev]"
Copy-Item .env.example .env
```

Si PowerShell bloquea la activación, usa
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` o llama
directamente a `.\.venv\Scripts\python.exe`.

Extras incluidos:

- `api`: FastAPI, SQLAlchemy, PDF y driver de Postgres.
- `audio`: faster-whisper para transcribir.
- `ocr`: pytesseract y Pillow.
- `queue`: Celery y Redis (F5).
- `dev`: pytest, ruff, mypy y pip-audit.

### 3. Arrancar el backend

En una terminal, desde la raíz del repositorio:

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.asgi:app --reload --port 8000
```

Comprobar:

- Salud: <http://127.0.0.1:8000/health>
- Documentación interactiva: <http://127.0.0.1:8000/docs>

La base de datos SQLite (`backend/data/recetario.db`) se crea sola al arrancar.
Los trabajos se ejecutan en hilos (`RECETARIO_JOB_RUNNER=thread`), sin Redis.

### 4. Arrancar el frontend

En otra terminal:

```powershell
cd frontend
npm install
cmd /c "npm run dev"
```

Abrir <http://localhost:3000>. La URL de la API se configura con
`NEXT_PUBLIC_API_URL` (por defecto `http://127.0.0.1:8000`); hay una plantilla
en `frontend/.env.local.example`.

### 5. Probar el flujo

1. `/nueva`: crear una receta sin video.
2. `/importar`: pegar una URL de TikTok o texto y seguir el estado del trabajo.
3. `/recetas/[id]`: revisar, aprobar, editar, imprimir y exportar.

### OCR opcional (Windows)

Además del extra `[ocr]`, hace falta el binario de Tesseract y el idioma
español:

```powershell
winget install --id UB-Mannheim.TesseractOCR -e
# Descarga spa.traineddata de tessdata_fast a una carpeta propia y define
# TESSDATA_PREFIX para no necesitar permisos de administrador:
#   [Environment]::SetEnvironmentVariable(
#     "TESSDATA_PREFIX", "$env:LOCALAPPDATA\Tesseract-OCR\tessdata", "User")
```

En Linux: `sudo apt install tesseract-ocr tesseract-ocr-spa`.

El lector descarta por defecto palabras con confianza menor a 60 y frames sin
una palabra fuerte; se ajusta con `RECETARIO_TESSERACT_MIN_CONFIDENCE`.

### Uso

```powershell
# Normalizar un ingrediente
python -m app.cli parse "1 1/2 tazas de harina integral"

# Ver el contexto que se enviaría al modelo (sin llamarlo)
python -m app.cli ingest --caption-file fixtures\caption_01.txt --dry-run

# Extraer una receta a JSON
python -m app.cli ingest --caption-file fixtures\caption_01.txt --out receta.json

# Desde una URL (requiere yt-dlp, ffmpeg y el extra [audio])
python -m app.cli ingest --url https://vm.tiktok.com/XXXX/

# Ingesta por URL sin leer frames (útil para aislar el resto del pipeline)
python -m app.cli ingest --url https://vm.tiktok.com/XXXX/ --no-frames --interval 2

# Muestrear un video local y leer su texto en pantalla (RF-12)
python -m app.cli frames --video C:\ruta\video.mp4 --interval 2 --out frames.txt

# Comparar OCR y visión sobre los mismos frames
python -m app.evals.screen_text --video C:\ruta\video.mp4 --expected fixtures\screen_text_01.txt --readers tesseract,vision
```

El agente imprime su traza en `stderr`: pasos, herramienta, resultado, duración
y costo. En la API, la misma traza viaja en `JobOut.events`.

### Endpoints principales

- Documentación interactiva: <http://127.0.0.1:8000/docs>
- Recetas: `GET/POST /api/v1/recipes` · `GET/PATCH/DELETE /api/v1/recipes/{id}`
- Exportación: `GET /api/v1/recipes/{id}/export?format=jsonld|md|pdf`
- Trabajos: `POST /api/v1/jobs` · `GET /api/v1/jobs/{id}` · `POST /api/v1/jobs/{id}/retry` · `POST /api/v1/jobs/{id}/cancel`
- Traza del agente: `GET /api/v1/jobs/{id}` devuelve `events` con paso,
  herramienta, entrada, salida, duración, costo y error.

La base de datos es SQLite (`backend/data/recetario.db`) y se crea sola al
arrancar. En Docker se usa Postgres.

### Páginas del libro

| Ruta | Qué hace |
| --- | --- |
| `/` | Estantería: búsqueda, filtros y tarjetas de recetas |
| `/recetas/[id]` | Libro abierto: ingredientes a la izquierda, pasos a la derecha; editar, aprobar, imprimir y exportar |
| `/nueva` | Alta manual de una receta sin video |
| `/importar` | Pegar una URL de TikTok o texto y seguir el estado del trabajo |

La verificación se hace con:

```powershell
cd frontend
cmd /c "npm run lint"
cmd /c "npm run typecheck"
cmd /c "npm run build"
cmd /c "npm run e2e"
```

`npm run e2e` levanta la API real con un LLM simulado y el frontend, y ejecuta
los dos flujos de Playwright: alta manual/edición/PDF/búsqueda e ingesta
simulada con revisión y aprobación. En CI corre con Chromium.

## Arranque con Docker (F5)

La forma reproducible de levantar todo (Postgres + pgvector, Redis, API, worker
de Celery y frontend) es Docker Compose.

### 1. Requisitos

- Docker Desktop con el motor Linux en marcha.
- Un proveedor LLM con llave. La imagen **no** incluye OpenCode, así que dentro
  de Docker se usa el adaptador compatible con OpenAI.

### 2. Configuración (una sola vez)

```powershell
Copy-Item .env.example .env
# Edita .env y define, como mínimo:
#   RECETARIO_LLM_PROVIDER=openai
#   RECETARIO_LLM_API_KEY=sk-...
#   RECETARIO_LLM_MODEL=gpt-4o-mini
```

Compose lee `.env` si existe (`required: false`), así que sin llave la API y el
libro arrancan igual: solo la extracción desde URL quedará sin LLM.

### 3. Levantar

```powershell
docker compose up --build -d
docker compose ps
```

| Servicio | URL / comprobación |
| --- | --- |
| Libro | <http://localhost:3000> |
| API | <http://localhost:8000> |
| Salud | <http://localhost:8000/health> |
| OpenAPI | <http://localhost:8000/docs> |
| Postgres | `localhost:5432` (usuario `recetario`) |
| Redis | `localhost:6379` |

El primer arranque tarda: construye las imágenes (ffmpeg, Tesseract, `spa`,
faster-whisper) y descarga el modelo de transcripción la primera vez que se
procesa un video.

### 4. Comprobar el worker y los datos

```powershell
docker compose logs -f worker
docker compose exec db psql -U recetario -d recetario -c "\dt"
```

Los trabajos se encolan en Redis (`RECETARIO_JOB_RUNNER=celery`) y el worker
ejecuta el mismo `process_job` que en local. Los reintentos automáticos solo
aplican a errores transitorios (`descarga_bloqueada`, `error_interno`), con
espera exponencial 5 s → 10 s → 20 s y tope de 3 intentos.

### 5. Detener

```powershell
docker compose down          # conserva los volúmenes
docker compose down -v       # borra Postgres, Redis y la caché de Whisper
```

### Diferencias con el arranque local

| Aspecto | Local | Docker |
| --- | --- | --- |
| Base de datos | SQLite (`backend/data/recetario.db`) | Postgres 16 + pgvector |
| Cola | Hilos (`thread`) | Celery + Redis |
| LLM | OpenCode local o API | API compatible con OpenAI |
| OCR | Tesseract del sistema | Tesseract dentro de la imagen |

## Arquitectura

```
backend/app/
├── domain/        esquema, unidades, confianza, reglas, contenido y agente
├── ports/         interfaces (extractor, transcriber, LLM, frames, lector)
├── adapters/      yt-dlp, faster-whisper, OpenCode, OpenAI, manual, OCR, visión
├── pipeline/      orquestación, validación con reintentos y agente
├── db/            modelos SQLAlchemy y repositorio
├── jobs/          trabajos, etapas, traza, runner en hilos y Celery
├── api/           routers y esquemas HTTP
├── evals/         comparación de lectores de texto en pantalla
└── cli.py         interfaz de línea de comandos

frontend/
├── app/           rutas (estantería, receta, nueva, importar)
├── components/    libro, formulario, tarjetas, iconos
├── e2e/           pruebas de Playwright
└── lib/           cliente de API, tipos y formato
```

La regla es simple: el dominio no conoce adaptadores. Cambiar de proveedor es
configuración, no código.

## Límites conocidos

- Los modelos gratuitos de OpenCode solo funcionan desde OpenCode y tienen cuota;
  el adaptador informa `provider.free-limit` con el tiempo de espera. Al cierre
  de esta validación la cuota seguía agotada, así que no se pudo contar 10/15
  recetas válidas.
- `yt-dlp` puede romperse cuando TikTok cambia su sitio; por eso existe la
  entrada manual y las fixtures para pruebas.
- El OCR necesita el binario de Tesseract y el extra `[ocr]`. En este equipo
  están instalados (Tesseract 5.4 + `spa`) y la ruta está verificada con un
  video sintético (F1 = 1.0) y con frames reales. Si falta el binario, el agente
  registra la llamada como fallida y sigue con las demás fuentes.
- **Texto en pantalla real:** de los 15 videos de prueba, ninguno muestra
  ingredientes con cantidad en pantalla; el OCR solo recupera títulos
  (`ARROZ`, `Papas rellenas`, `Sopa de papa CREMOSA`) y algún logotipo. Por eso
  la mejora de F4 frente a F1 aún no es medible con ese lote.
- **Audio real:** 12/15 videos tienen voz transcribible. Los videos 02, 03 y 10
  no tienen voz reconocible (audio musical); el agente no aborta: registra el
  fallo y continúa con el caption. Si el caption tampoco alcanza, la receta
  queda `por_revisar` o se rechaza.
- La comparación OCR vs visión sigue pendiente: falta configurar una llave de
  visión y un lote con texto de receta visible y anotado.
- La transcripción con `small` funcionó bien con voz real en español (video 01:
  1742 caracteres, 48,7 s); los videos en inglés pueden requerir `language=en`
  o un modelo mayor.
- El recetario es de uso personal y un solo usuario.
- No se guardan ni se republican los videos.

## Aviso legal

Proyecto de uso personal. Se respetan los términos de TikTok y los derechos de
los autores: se cita siempre al autor y la fuente, y el video se elimina al
terminar el procesamiento.

## Documentación

- [`docs/FASES.md`](docs/FASES.md): fases, estado y criterios de aceptación.
- [`docs/adr/`](docs/adr/): decisiones de arquitectura.
