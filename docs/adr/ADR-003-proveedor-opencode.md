# ADR-003 · OpenCode local como proveedor de LLM

- **Estado:** aceptado
- **Fecha:** 2026-11-10
- **Fase:** F1

## Contexto

Se quiere usar el modelo `opencode/deepseek-v4.1-flash-free` sin costo. La API
de inferencia de OpenCode devuelve `403` a clientes externos para los modelos
gratuitos: solo funcionan desde dentro de OpenCode.

## Decisión

Implementar dos adaptadores detrás del puerto `RecipeLLM`:

1. `OpenCodeLLM`: ejecuta `opencode run --agent recetario-extractor --format json`
   y parsea el flujo JSONL. No requiere llave de API.
2. `OpenAIRecipeLLM`: API compatible con OpenAI, para proveedores de pago o
   cualquier endpoint alternativo.

El proveedor se elige con `RECETARIO_LLM_PROVIDER`.

El agente `recetario-extractor` vive en `.opencode/agents/` y tiene todas las
herramientas denegadas y un solo paso: solo devuelve JSON.

## Consecuencias

- El pipeline depende de que OpenCode esté instalado y autenticado en la máquina
  del worker; no es apto para un contenedor sin OpenCode.
- La cuota gratuita puede agotarse (`provider.free-limit`); el adaptador lo
  clasifica y el CLI informa el tiempo de espera.
- Cambiar a un proveedor de pago es solo configuración, sin tocar el pipeline.
