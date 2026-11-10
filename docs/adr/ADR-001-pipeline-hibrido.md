# ADR-001 · Pipeline híbrido con agente solo para decisiones

- **Estado:** aceptado
- **Fecha:** 2026-11-10
- **Fase:** F1 (decisión), F4 (implementación del agente)

## Contexto

El flujo tiene pasos predecibles (descargar, transcribir, validar, guardar) y
decisiones que dependen del contenido de cada video (¿basta el caption?, ¿hacen
falta los frames?, ¿qué fuente tiene las cantidades?).

Un agente totalmente libre es difícil de testear, caro e impredecible. Un
pipeline totalmente fijo no puede adaptarse a videos con distinta información.

## Decisión

Usar un pipeline fijo para lo predecible y un agente con herramientas solo para
las decisiones de contenido (RA-01 y RA-02), con límite de pasos y de costo.

## Consecuencias

- Las etapas son testeables por separado y se pueden cambiar de proveedor.
- El agente queda acotado: no controla la descarga ni la persistencia.
- Los costos y la latencia son predecibles; el agente se activa solo cuando aporta.
