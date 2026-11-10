# ADR-002 · Un solo esquema Pydantic para validar, guardar y exportar

- **Estado:** aceptado
- **Fecha:** 2026-11-10
- **Fase:** F1

## Contexto

La receta se usa en tres lugares: salida estructurada del LLM, persistencia y
exportación a JSON-LD de schema.org. Mantener tres definiciones invita a que se
desincronicen.

## Decisión

Definir el contenido en `RecipeDraft` (lo que produce el LLM) y extenderlo en
`Recipe` con los campos de infraestructura (`source`, `extraction`, `status`,
`schema_version`). El JSON-LD se genera a partir de `Recipe` en la capa de
exportación, no con un modelo paralelo.

## Consecuencias

- Una sola fuente de verdad para validación y tipos.
- El LLM nunca rellena campos de infraestructura (fuente, costo, estado).
- Cualquier cambio de esquema exige subir `SCHEMA_VERSION` y migrar (RE-02).
- La exportación JSON-LD debe seguir pasando el validador de schema.org (RE-03).
