# Recetario con IA

Convierte un enlace de TikTok de cocina en una receta estructurada, validada y
guardada en un recetario propio que se puede buscar, editar y exportar.

> **Estado:** F1 en curso. El pipeline y la CLI funcionan; la validación con
> videos reales está pendiente por la cuota del modelo gratuito.
> Ver [`docs/FASES.md`](docs/FASES.md).

## Qué resuelve

- Ingesta de una URL de TikTok o de texto manual (caption, transcripción).
- Unión de caption, audio y texto en pantalla con la fuente de cada dato.
- Extracción a un esquema único, compatible con schema.org/Recipe.
- Validación con reintentos y marca `por_revisar` cuando falta evidencia.
- Recetario con búsqueda, edición y exportación (a partir de F2/F3).

## Stack

| Capa | Elección |
| --- | --- |
| Lenguaje | Python 3.11 |
| Esquema y validación | Pydantic 2 |
| LLM | OpenCode local (`deepseek-v4.1-flash-free`) u API compatible con OpenAI |
| Descarga | yt-dlp + ffmpeg |
| Transcripción | faster-whisper (local) |
| API y base de datos | FastAPI + SQLAlchemy (F2) |
| Frontend | Next.js + TypeScript + Tailwind (F3) |

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
```

### API

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.asgi:app --reload
```

- Documentación interactiva: <http://127.0.0.1:8000/docs>
- `GET /api/v1/recipes` · `POST /api/v1/recipes` · `PATCH /api/v1/recipes/{id}`
- `GET /api/v1/recipes/{id}/export?format=jsonld|md`

La base de datos es SQLite (`data/recetario.db`) y se crea sola al arrancar.

## Arquitectura

```
backend/app/
├── domain/        esquema, unidades, confianza, reglas, contenido
├── ports/         interfaces (extractor, transcriber, LLM)
├── adapters/      yt-dlp, faster-whisper, OpenCode, OpenAI, entrada manual
├── pipeline/      orquestación y validación con reintentos
└── cli.py         interfaz de línea de comandos
```

La regla es simple: el dominio no conoce adaptadores. Cambiar de proveedor es
configuración, no código.

## Límites conocidos

- Los modelos gratuitos de OpenCode solo funcionan desde OpenCode y tienen cuota;
  el adaptador informa `provider.free-limit` con el tiempo de espera.
- `yt-dlp` puede romperse cuando TikTok cambia su sitio; por eso existe la
  entrada manual y las fixtures para pruebas.
- El recetario es de uso personal y un solo usuario.
- No se guardan ni se republican los videos.

## Aviso legal

Proyecto de uso personal. Se respetan los términos de TikTok y los derechos de
los autores: se cita siempre al autor y la fuente, y el video se elimina al
terminar el procesamiento.

## Documentación

- [`docs/FASES.md`](docs/FASES.md): fases, estado y criterios de aceptación.
- [`docs/adr/`](docs/adr/): decisiones de arquitectura.
