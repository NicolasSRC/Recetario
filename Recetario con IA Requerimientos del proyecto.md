# Recetario con IA: Requerimientos del proyecto

Nov 10, 2026 · @nicolas

## 1. Resumen y objetivos

El proyecto convierte un enlace de TikTok de cocina en una receta estructurada, validada y guardada en un recetario propio que se puede buscar, editar y exportar. Es de uso personal, con un solo usuario, y está pensado para que el repositorio muestre habilidades que hoy faltan en el CV: pipelines multimodales, salidas estructuradas, agentes con herramientas, procesamiento asíncrono y evaluación de calidad.

**Objetivos**

- **O1.** Pasar de una URL de TikTok a una receta completa con una sola acción del usuario.
- **O2.** Producir siempre el mismo formato de salida, compatible con schema.org/Recipe.
- **O3.** Mostrar en el repo un agente que decide qué fuentes usar (caption, audio, frames) en lugar de seguir siempre los mismos pasos.
- **O4.** Medir la calidad con un conjunto de evaluación propio, para poder poner una cifra real en el CV.
- **O5.** Dejar el proyecto desplegable con Docker Compose y CI/CD, con README, diagrama y demo.

**Dentro del alcance**

- Ingesta de enlaces públicos de TikTok, con alternativa manual (pegar caption o transcripción).
- Extracción de texto desde caption, audio y texto en pantalla.
- Estructuración, validación y normalización de la receta.
- Recetario con listado, detalle, edición, etiquetas, búsqueda y exportación.
- Evaluación automática, pruebas, observabilidad básica y despliegue.

**Fuera del alcance (primera versión)**

- Cuentas multiusuario, roles y pagos.
- Redistribuir o almacenar el video original de forma pública.
- Apps móviles nativas.
- Otras plataformas además de TikTok (la interfaz de ingesta debe permitir añadirlas después).

## 2. Requerimientos funcionales

Prioridad: **M** = imprescindible (MVP), **S** = importante, **C** = deseable.

### Ingesta

| ID | Requerimiento | Prioridad |
| --- | --- | --- |
| RF-01 | El usuario envía una URL de TikTok (corta `vm.tiktok.com` o larga) y el sistema la valida y la normaliza. | M |
| RF-02 | El sistema obtiene metadatos: caption, autor, duración, hashtags, fecha y URL canónica. | M |
| RF-03 | Si la URL ya fue procesada, el sistema devuelve la receta existente y no la procesa de nuevo. | S |
| RF-04 | El usuario puede pegar manualmente caption y/o transcripción cuando la descarga falla. | M |
| RF-05 | El extractor de video está detrás de una interfaz, para cambiar `yt-dlp` por otro sin tocar el resto. | S |
| RF-06 | El usuario puede enviar varias URL a la vez (lote). | C |

### Extracción multimodal

| ID | Requerimiento | Prioridad |
| --- | --- | --- |
| RF-10 | El sistema extrae el audio y lo transcribe con marcas de tiempo. | M |
| RF-11 | El sistema detecta el idioma del audio y soporta al menos español e inglés. | M |
| RF-12 | El sistema muestrea frames del video y extrae el texto en pantalla (ingredientes, cantidades, tiempos). | S |
| RF-13 | El sistema une caption, transcripción y texto en pantalla en un único contexto, indicando de qué fuente viene cada dato. | M |
| RF-14 | El sistema borra el video y el audio temporales al terminar el procesamiento. | M |

### Estructuración y validación

| ID | Requerimiento | Prioridad |
| --- | --- | --- |
| RF-20 | Un LLM convierte el contexto unido en una receta con el esquema de la sección 3, usando salida estructurada. | M |
| RF-21 | Cada ingrediente se separa en cantidad, unidad, nombre y nota (ej. "picada"). | M |
| RF-22 | El sistema normaliza unidades a un conjunto fijo (g, kg, ml, l, taza, cucharada, cucharadita, unidad) y conserva el texto original. | M |
| RF-23 | El sistema valida el resultado contra el esquema y reintenta con el error de validación si falla (máximo 2 reintentos). | M |
| RF-24 | El sistema marca como "por revisar" los campos sin evidencia clara en las fuentes, en lugar de inventarlos. | M |
| RF-25 | El sistema calcula un puntaje de confianza por receta y por campo. | S |
| RF-26 | El sistema detecta que el video no es una receta y lo informa sin crear una entrada. | S |

### Recetario

| ID | Requerimiento | Prioridad |
| --- | --- | --- |
| RF-30 | El usuario ve el estado del procesamiento de cada video (en cola, procesando, listo, falló, por revisar). | M |
| RF-31 | El usuario puede listar, ver el detalle, editar y borrar recetas. | M |
| RF-32 | El usuario puede corregir una receta "por revisar" y marcarla como aprobada. | M |
| RF-33 | El usuario puede añadir etiquetas (tipo de plato, dieta, ingrediente principal) y el sistema sugiere algunas automáticamente. | S |
| RF-34 | El usuario puede escalar porciones y ver las cantidades recalculadas. | S |
| RF-35 | El usuario puede buscar por texto (nombre, ingrediente) y por significado ("algo con pollo y sin horno"). | S |
| RF-36 | El usuario puede filtrar por etiqueta, tiempo total y dificultad. | S |
| RF-37 | El usuario puede marcar favoritas y armar una lista de compras a partir de varias recetas. | C |

### Exportación e integración

| ID | Requerimiento | Prioridad |
| --- | --- | --- |
| RF-40 | El usuario exporta una receta en JSON-LD (schema.org/Recipe), Markdown y PDF. | M |
| RF-41 | El usuario exporta todo el recetario en un archivo. | S |
| RF-42 | El sistema expone las recetas como herramientas de un servidor MCP (`buscar_receta`, `agregar_receta`, `obtener_receta`). | C |
| RF-43 | El sistema ofrece una API REST documentada con OpenAPI. | M |

## 3. Esquema de datos de la receta

El esquema interno se define una sola vez con Pydantic, se usa como esquema de salida del LLM y se exporta a JSON-LD de schema.org/Recipe. Los campos propios (fuente, confianza, estado) viven fuera del JSON-LD.

| Campo | Tipo | Obligatorio | Notas |
| --- | --- | --- | --- |
| `title` | texto | Sí | Nombre de la receta |
| `description` | texto | No | Resumen de una o dos frases |
| `language` | código ISO | Sí | `es`, `en`, etc. |
| `servings` | número | No | Porciones; si no hay evidencia, queda vacío |
| `prep_time_min` / `cook_time_min` | número | No | Minutos; el total se calcula |
| `difficulty` | enum | No | `facil`, `media`, `dificil` |
| `ingredients[]` | lista | Sí | Ver siguiente tabla |
| `steps[]` | lista | Sí | `order`, `text`, `duration_min` (opcional), `timestamp_s` (opcional) |
| `equipment[]` | lista de texto | No | Horno, licuadora, etc. |
| `tags[]` | lista de texto | No | Plato, dieta, ingrediente principal |
| `nutrition` | objeto | No | Solo si aparece en las fuentes; nunca se estima |
| `notes` | texto | No | Consejos o variaciones que dice el autor |
| `source` | objeto | Sí | `url`, `author`, `platform`, `captured_at` |
| `extraction` | objeto | Sí | `sources_used[]`, `confidence`, `model`, `needs_review`, `flags[]` |
| `status` | enum | Sí | `en_cola`, `procesando`, `por_revisar`, `aprobada`, `fallida` |

**Ingrediente**

| Campo | Tipo | Notas |
| --- | --- | --- |
| `name` | texto | Nombre normalizado en minúscula ("cebolla") |
| `quantity` | número | Decimal; vacío si dice "al gusto" |
| `unit` | enum | Conjunto fijo de RF-22 |
| `note` | texto | Preparación ("picada fina") |
| `raw_text` | texto | Frase original, para auditoría |
| `optional` | booleano | `true` si el autor lo marca opcional |
| `group` | texto | Subreceta ("salsa", "masa") si existe |
| `evidence` | enum | `caption`, `audio`, `pantalla`: de dónde se sacó |

**Reglas del esquema**

- RE-01: todo dato debe poder rastrearse a una fuente; sin evidencia, el campo queda vacío y la receta pasa a `por_revisar`.
- RE-02: el esquema lleva un número de versión, y los cambios se aplican con migraciones.
- RE-03: la exportación a JSON-LD debe pasar un validador de schema.org en las pruebas.

## 4. Requerimientos del agente y del pipeline

El diseño es un híbrido: un pipeline fijo para lo predecible (descargar, transcribir, validar, guardar) y un agente con herramientas solo para las decisiones que dependen del contenido de cada video.

**Herramientas del agente**

| Herramienta | Qué hace | Entrada → salida |
| --- | --- | --- |
| `get_metadata` | Obtiene caption, autor y duración | URL → metadatos |
| `transcribe_audio` | Extrae y transcribe el audio | URL → texto con tiempos |
| `extract_frames` | Muestrea frames y lee el texto en pantalla | URL, intervalo → texto por frame |
| `validate_recipe` | Valida contra el esquema y las reglas de negocio | receta → errores o ok |
| `save_recipe` | Guarda la receta con su estado | receta → id |
| `ask_user` | Pide un dato que falta cuando la confianza es baja | pregunta → respuesta |

**Requerimientos del agente**

- RA-01: si el caption ya trae ingredientes y pasos completos, el agente se salta audio y frames.
- RA-02: si faltan cantidades o pasos tras caption y audio, el agente pide los frames.
- RA-03: el agente tiene un límite de pasos (por ejemplo 8 llamadas a herramientas) y un tope de costo por video; al alcanzarlo guarda lo obtenido como `por_revisar`.
- RA-04: cada llamada a una herramienta queda registrada con entrada, salida, duración y costo.
- RA-05: el agente no inventa datos. Si una fuente no confirma un campo, lo deja vacío y lo marca.
- RA-06: el texto del video, del caption y de los comentarios se trata como dato, nunca como instrucción (defensa contra inyección de prompts).
- RA-07: el modelo se configura por variable de entorno, para cambiarlo sin tocar el código.

**Requerimientos del pipeline asíncrono**

- RP-01: cada video se procesa como un trabajo en cola con estados y reintentos con espera creciente.
- RP-02: los trabajos son idempotentes: reprocesar la misma URL no duplica recetas.
- RP-03: los fallos tienen causa clasificada (URL inválida, video privado, descarga bloqueada, transcripción vacía, esquema inválido, límite de costo).
- RP-04: un trabajo fallido se puede reintentar manualmente desde la interfaz.
- RP-05: el usuario puede cancelar un trabajo en curso.
- RP-06: el tiempo objetivo por video de 60 segundos es una meta, no una garantía (ver RNF-01).

## 5. Requerimientos no funcionales

| ID | Categoría | Requerimiento |
| --- | --- | --- |
| RNF-01 | Rendimiento | Un video de hasta 90 segundos se procesa en menos de 60 segundos en el caso típico (meta, medida en las evals). |
| RNF-02 | Costo | El costo por video se registra y se mantiene por debajo de un tope configurable. La transcripción es local por defecto y los frames se muestrean, no se envía el video completo a un modelo. |
| RNF-03 | Confiabilidad | La caída de un servicio externo (modelo, descarga) no tumba la API: el trabajo falla con causa clara y se puede reintentar. |
| RNF-04 | Seguridad | Las llaves de API viven en variables de entorno o un gestor de secretos, nunca en el repo. Se valida y limita la entrada: solo URLs de dominios permitidos y límites de tamaño y duración. |
| RNF-05 | Seguridad | Protección contra SSRF en la descarga (no se aceptan IPs internas ni redirecciones a ellas) y contra inyección de prompts desde caption, audio o texto en pantalla. |
| RNF-06 | Privacidad | Solo se guardan receta, metadatos públicos y un enlace a la fuente. El video y el audio se eliminan al terminar. Lo que se envía a una API de terceros queda documentado en el README. |
| RNF-07 | Legal | Uso personal; se respetan los términos de TikTok y los derechos del autor, se cita siempre al autor y la fuente, y no se republica el video. El README lo advierte. |
| RNF-08 | Observabilidad | Logs estructurados con un identificador por trabajo; métricas de latencia, costo, tokens y tasa de fallos por etapa. |
| RNF-09 | Mantenibilidad | Cada etapa (ingesta, transcripción, visión, extracción, validación) está detrás de una interfaz y se puede cambiar de proveedor por configuración. |
| RNF-10 | Calidad de código | Tipado estático (mypy o pyright, TypeScript estricto), linter y formateador en CI, cobertura mínima del 70 % en la lógica de dominio. |
| RNF-11 | Portabilidad | Todo el sistema arranca con `docker compose up` y un archivo `.env.example`. |
| RNF-12 | Accesibilidad | La interfaz cumple lo básico de WCAG 2.1 AA: contraste, teclado y etiquetas. |
| RNF-13 | Documentación | README con arquitectura, decisiones técnicas, límites conocidos, cómo correr las evals y un demo en GIF. |

## 6. Arquitectura y stack

Una API recibe la URL, la encola y un worker ejecuta el agente; el resultado queda en Postgres y la interfaz consulta el estado hasta que la receta está lista.

&#91;embedded content: arquitectura · 5 componentes y 6 herramientas del agente\]

La API responde de inmediato con el identificador del trabajo. El worker corre el agente, que llama a sus herramientas, y el resultado se guarda con estado `por_revisar` o `aprobada` según la confianza.

### Stack propuesto

| Capa | Elección | Alternativa |
| --- | --- | --- |
| API | FastAPI + Pydantic | NestJS |
| Cola y workers | Celery + Redis | BullMQ (Node) |
| Descarga y audio | yt-dlp + ffmpeg, detrás de una interfaz | Carga manual del video |
| Transcripción | faster-whisper (local) | API de transcripción |
| Texto en pantalla | Modelo con visión sobre frames | PaddleOCR o Tesseract |
| Extracción | LLM por API con salida estructurada | Modelo local |
| Base de datos | PostgreSQL + pgvector | SQLite en el MVP |
| ORM y migraciones | SQLAlchemy + Alembic | Prisma |
| Frontend | Next.js + TypeScript + Tailwind | Vite + React |
| Pruebas | pytest, Vitest, Playwright | — |
| Infraestructura | Docker Compose, GitHub Actions | — |
| Observabilidad | Logs estructurados con `job_id` | OpenTelemetry, Langfuse |

### API REST (v1)

| Ruta | Qué hace |
| --- | --- |
| `POST /api/v1/jobs` | Crea un trabajo desde una URL o un texto manual y responde 202 con `job_id` |
| `GET /api/v1/jobs/{id}` | Devuelve estado, etapa actual y errores |
| `POST /api/v1/jobs/{id}/retry` | Reintenta un trabajo fallido |
| `POST /api/v1/jobs/{id}/cancel` | Cancela un trabajo en curso |
| `GET /api/v1/recipes` | Lista con filtros y paginación |
| `GET /api/v1/recipes/search?q=` | Búsqueda por texto y por significado |
| `GET /api/v1/recipes/{id}` | Detalle de una receta |
| `PATCH /api/v1/recipes/{id}` | Edita o aprueba una receta |
| `DELETE /api/v1/recipes/{id}` | Borra una receta |
| `GET /api/v1/recipes/{id}/export?format=jsonld\|md\|pdf` | Exporta una receta |

### Modelo de datos

| Tabla | Contenido clave |
| --- | --- |
| `recipes` | Título, descripción, idioma, porciones, tiempos, dificultad, estado, versión del esquema |
| `ingredients` | Receta, orden, nombre, cantidad, unidad, nota, texto original, evidencia |
| `steps` | Receta, orden, texto, duración, marca de tiempo |
| `tags` y `recipe_tags` | Etiquetas y su relación con recetas |
| `sources` | URL canónica única, autor, plataforma, fecha de captura |
| `jobs` | Fuente, estado, etapa, causa de fallo, costo y duración |
| `job_events` | Registro de cada llamada a una herramienta (entrada, salida, tiempo, costo) |
| `recipe_embeddings` | Vector (pgvector) por receta para la búsqueda semántica |

## 7. Evaluación, pruebas, CI/CD y fases

La evaluación es lo que convierte el proyecto en algo medible: sin dataset propio, la calidad de la extracción es una opinión.

### Evaluación (evals)

- EV-01: un dataset de 15 a 20 videos con la receta esperada anotada a mano, en español e inglés, que incluya recetas completas en el caption, recetas solo en audio, recetas solo en texto en pantalla y videos que no son recetas.
- EV-02: las evals corren en CI sobre captions y transcripciones guardadas como fixtures (sin llamar a TikTok) y, de forma manual, sobre el pipeline completo.
- EV-03: cada ejecución guarda su reporte en el repo, con modelo, versión del prompt y resultados, para comparar cambios.

| Métrica | Qué mide | Objetivo inicial (a ajustar) |
| --- | --- | --- |
| Recall de ingredientes | Ingredientes esperados que aparecen en la salida | ≥ 90 % |
| Precisión de ingredientes | Ingredientes de la salida que sí están en el video | ≥ 90 % |
| Exactitud de cantidad y unidad | Cantidades correctas entre los ingredientes acertados | ≥ 85 % |
| Cobertura y orden de pasos | Pasos esperados presentes y en orden | ≥ 85 % |
| Esquema válido al primer intento | Salidas que pasan la validación sin reintento | ≥ 95 % |
| Detección de no-receta | Videos sin receta rechazados correctamente | ≥ 90 % |
| Latencia y costo | p50 y p95 por video; costo medio | Registrar; fijar meta tras la F4 |

### Pruebas

- **Unitarias:** normalización de unidades, parseo de cantidades ("1 1/2", "media taza"), validación del esquema, reglas de confianza.
- **Integración:** API, cola y base de datos reales en contenedores; idempotencia y reintentos.
- **Contrato:** la exportación JSON-LD pasa el validador de schema.org.
- **End-to-end (Playwright):** pegar una URL, ver el estado, revisar, aprobar y exportar, con el modelo y la descarga simulados.
- **Seguridad:** casos de SSRF y de inyección de prompts incluidos en caption y audio de prueba.

### CI/CD

- Pipeline en GitHub Actions: linter, tipos, pruebas, build de imágenes Docker, evals sobre fixtures y escaneo de dependencias.
- Cada cambio de prompt o de modelo muestra la diferencia de métricas en el pull request.
- Despliegue opcional de una demo en un servicio de contenedores, con secretos fuera del repo.

### Entregables del repositorio

- README con problema, arquitectura (diagrama), decisiones técnicas, límites conocidos, resultados de evals y demo en GIF.
- `docker-compose.yml`, `.env.example` y OpenAPI generado.
- Carpeta `docs/adr/` con las decisiones de arquitectura (por qué híbrido, por qué ese modelo, por qué pgvector).
- Carpeta `evals/` con dataset, anotaciones, scripts y reportes.
- Licencia y nota legal sobre uso personal y derechos de autor.

### Fases y criterios de aceptación

| Fase | Alcance | Criterio de aceptación |
| --- | --- | --- |
| F1 · MVP sin interfaz | URL → caption y transcripción → LLM → JSON validado, por línea de comandos | Al menos 10 de 15 videos de prueba producen un JSON válido |
| F2 · Persistencia y API | Postgres, endpoints de recetas y trabajos, idempotencia | OpenAPI publicado; pruebas de integración en verde; reprocesar una URL no duplica |
| F3 · Frontend | Lista, detalle, edición, aprobación, exportación y estados | El flujo e2e completo pasa en CI |
| F4 · Frames y agente | Texto en pantalla y decisiones del agente (RA-01 y RA-02) | Mejora medible frente a F1 en videos con texto en pantalla |
| F5 · Cola y despliegue | Celery, reintentos, Docker Compose y GitHub Actions | `docker compose up` levanta todo y el CI queda en verde |
| F6 · Evals, búsqueda y MCP | Dataset completo con reporte, búsqueda semántica y servidor MCP | Reporte de evals en el README; búsqueda por significado funcionando; MCP con tres herramientas |

## 8. Riesgos, supuestos y decisiones abiertas

El mayor riesgo es la descarga: TikTok no ofrece una API oficial para obtener videos, por eso la entrada manual (RF-04) es un requerimiento imprescindible y no un extra.

### Riesgos

| Riesgo | Impacto | Mitigación |
| --- | --- | --- |
| `yt-dlp` deja de funcionar por cambios de TikTok | Alto | Interfaz de extractor (RF-05), entrada manual (RF-04) y fixtures para que las pruebas no dependan de TikTok |
| El LLM inventa cantidades o pasos | Alto | Evidencia por campo, estado `por_revisar`, validación y evals (RA-05, RE-01) |
| Costo por video mayor al esperado | Medio | Transcripción local, frames muestreados, tope por video y registro de costo (RNF-02, RA-03) |
| Inyección de prompts desde el contenido del video | Medio | El contenido se trata como dato (RA-06) y hay pruebas dedicadas |
| Problemas de derechos de autor o términos de uso | Medio | Uso personal, citar al autor, no guardar ni republicar el video (RNF-06, RNF-07) |
| Alcance excesivo | Medio | Fases con criterio de aceptación; lo deseable (C) se deja para el final |

### Supuestos

- Un solo usuario y volumen bajo (decenas de videos, no miles).
- Los videos son públicos y de corta duración (hasta unos 90 segundos).
- Se dispone de una llave de API de un modelo de lenguaje con salida estructurada y, idealmente, con visión.
- Las recetas están principalmente en español e inglés.

### Decisiones abiertas

- [ ] ¿Transcripción local (faster-whisper) o por API? Depende del equipo donde corra el worker.
- [ ] ¿Texto en pantalla con un modelo de visión o con OCR clásico? Se decide comparando ambos en las evals de la F4.
- [ ] ¿Qué modelo de lenguaje se usa y con qué tope de costo por video?
- [ ] ¿Dónde se despliega la demo (VPS propio, contenedores administrados)?
- [ ] ¿El repositorio será público desde el inicio? Afecta lo que se puede incluir en el dataset de evals.
