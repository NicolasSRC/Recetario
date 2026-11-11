# ADR-005 · Frames, lector de pantalla y agente determinista

- **Estado:** aceptado
- **Fecha:** 2026-11-11
- **Fase:** F4

## Contexto

RF-12 pide muestrear frames y extraer el texto en pantalla (ingredientes,
cantidades, tiempos). El requisito también describe un agente que decide qué
fuentes usar (RA-01 a RA-06) con herramientas, límite de pasos y costo, y traza
de cada llamada.

Hay dos tentaciones opuestas:

1. **Seguir siempre el mismo pipeline** y transcribir/leer frames en todos los
   videos. Es simple, pero gasta tiempo y dinero en videos cuyo caption ya trae
   la receta completa, y no demuestra ninguna decisión de agente.
2. **Dejar que un LLM elija herramientas en cada paso.** Es flexible, pero
   cuesta cuota, es difícil de reproducir, introduce no determinismo y hace que
   las pruebas dependan de un servicio externo.

Además, el entorno actual no tiene Tesseract instalado ni una llave de visión,
y la cuota del modelo gratuito está agotada. La fase debe poder implementarse y
probarse sin esos servicios.

## Decisión

1. **Pipeline fijo para lo predecible**: descargar metadatos, transcribir si
   hace falta, extraer, validar y guardar. El agente solo decide qué fuentes
   consultar.
2. **Política determinista** en `pipeline/agent.py`:
   - RA-01: si el caption tiene al menos dos ingredientes con cantidad y dos
     pasos marcados, se omiten audio y frames.
   - RA-02: si faltan cantidades (salvo «al gusto») o pasos, se piden frames y
     se conserva la extracción de mayor calidad (cantidades, pasos, confianza).
   - RA-03: máximo de pasos y tope de costo configurables; al alcanzarlos se
     guarda lo obtenido como `por_revisar` con el flag `agente_presupuesto`.
   - RA-04: cada llamada se registra con entrada, salida, duración y costo.
   - RA-05: ninguna fuente que no confirme un dato lo completa; la validación
     marca la receta para revisión.
3. **Herramientas inyectables** (`AgentTools`): `get_metadata`,
   `transcribe_audio`, `extract_frames`, `validate_recipe`, `save_recipe` y
   `ask_user`. Los trabajos y la CLI pasan las implementaciones reales; las
   pruebas pasan dobles. El agente no importa yt-dlp, whisper ni ffmpeg.
4. **Frames con ffmpeg** (`FFmpegFrameSampler`): un proceso por video, intervalo
   configurable, tope de frames y error explícito si falta el binario. Nunca se
   envía el video completo a un modelo.
5. **Dos lectores intercambiables** detrás del puerto `ScreenTextReader`:
   Tesseract (local, por defecto) y un modelo de visión por API compatible con
   OpenAI. La selección es configuración
   (`RECETARIO_SCREEN_TEXT_READER=tesseract|vision|none`).
6. **La traza reutiliza `job_events`**: no hay migración. El paso va dentro de
   `input` y el texto, el resultado y el error dentro de `output`. La API los
   aplana en `JobOut.events` y el frontend los muestra en «Qué hizo el agente».
7. **La comparación OCR vs visión es una eval reproducible**
   (`app.evals.screen_text`) con F1 por multiconjunto de palabras sobre los
   mismos frames. Se ejecuta con un video local y un texto esperado; no descarga
   nada.

## Consecuencias

- La política es auditable y se prueba sin cuota de modelo. Cambiar una regla es
  cambiar una función pura con pruebas.
- El agente no «razona» sobre casos raros: si la heurística del caption falla,
  el coste es una transcripción local o una lectura de frames, no datos
  inventados.
- La calidad del OCR depende de Tesseract y de la resolución del video. La eval
  dirá si conviene cambiar el lector por defecto a visión.
- Sin Tesseract ni llave de visión, `extract_frames` se registra como llamada
  fallida y el agente continúa con las fuentes disponibles.
- El costo del LLM se estima con `RECETARIO_LLM_COST_USD_PER_EXTRACTION` y el de
  visión con `RECETARIO_VISION_COST_USD_PER_FRAME`; con modelos gratuitos ambos
  quedan en 0.
