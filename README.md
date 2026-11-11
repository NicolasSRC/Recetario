# Recetario con IA

Convierte un enlace de TikTok de cocina en una receta estructurada, validada y
guardada en un recetario propio que se puede buscar, editar y exportar.

> **Estado:** F2 y F3 completadas; F4 implementada y pendiente de validación con
> videos reales. El pipeline, la API, el libro y el agente funcionan, pero la
> cuota del modelo gratuito y la falta de videos anotados impiden cerrar la
> medición.
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

## Arranque rápido

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e "backend[dev]"
Copy-Item .env.example .env
```

Opcional, para transcribir audio en local:

```powershell
pip install -e "backend[audio]"
```

Opcional, para leer texto en pantalla con OCR (además hace falta el binario de
Tesseract en el `PATH`):

```powershell
pip install -e "backend[ocr]"

# Windows: Tesseract + idioma español
winget install --id UB-Mannheim.TesseractOCR -e
# Descarga spa.traineddata de tessdata_fast a una carpeta propia y define
# TESSDATA_PREFIX para no necesitar permisos de administrador.
```

En Linux: `sudo apt install tesseract-ocr tesseract-ocr-spa`.

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

### API

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.asgi:app --reload
```

- Documentación interactiva: <http://127.0.0.1:8000/docs>
- Recetas: `GET/POST /api/v1/recipes` · `GET/PATCH/DELETE /api/v1/recipes/{id}`
- Exportación: `GET /api/v1/recipes/{id}/export?format=jsonld|md|pdf`
- Trabajos: `POST /api/v1/jobs` · `GET /api/v1/jobs/{id}` · `POST /api/v1/jobs/{id}/retry` · `POST /api/v1/jobs/{id}/cancel`
- Traza del agente: `GET /api/v1/jobs/{id}` devuelve `events` con paso,
  herramienta, entrada, salida, duración, costo y error.

La base de datos es SQLite (`backend/data/recetario.db`) y se crea sola al
arrancar.

### Libro (frontend)

```powershell
cd frontend
npm install
cmd /c "npm run dev"
```

Abrir <http://localhost:3000>. La URL de la API se configura con
`NEXT_PUBLIC_API_URL` (por defecto `http://127.0.0.1:8000`); hay una plantilla
en `frontend/.env.local.example`.

Páginas:

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

## Arquitectura

```
backend/app/
├── domain/        esquema, unidades, confianza, reglas, contenido y agente
├── ports/         interfaces (extractor, transcriber, LLM, frames, lector)
├── adapters/      yt-dlp, faster-whisper, OpenCode, OpenAI, manual, OCR, visión
├── pipeline/      orquestación, validación con reintentos y agente
├── db/            modelos SQLAlchemy y repositorio
├── jobs/          servicio de trabajos, etapas, traza y runner en hilos
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
  el adaptador informa `provider.free-limit` con el tiempo de espera.
- `yt-dlp` puede romperse cuando TikTok cambia su sitio; por eso existe la
  entrada manual y las fixtures para pruebas.
- El OCR necesita el binario de Tesseract y el extra `[ocr]`. En este equipo
  están instalados (Tesseract 5.4 + `spa`) y la ruta está verificada con un
  video sintético; si falta el binario, el agente registra la llamada como
  fallida y sigue con las demás fuentes.
- La comparación OCR vs visión aún no se ha medido con videos reales: falta
  configurar una llave de visión y contar con los videos anotados.
- La transcripción con `small` sobre audio sintético dio resultados pobres
  (detectó inglés); con voz real habrá que revisar el idioma y el modelo.
- El recetario es de uso personal y un solo usuario.
- No se guardan ni se republican los videos.

## Aviso legal

Proyecto de uso personal. Se respetan los términos de TikTok y los derechos de
los autores: se cita siempre al autor y la fuente, y el video se elimina al
terminar el procesamiento.

## Documentación

- [`docs/FASES.md`](docs/FASES.md): fases, estado y criterios de aceptación.
- [`docs/adr/`](docs/adr/): decisiones de arquitectura.
