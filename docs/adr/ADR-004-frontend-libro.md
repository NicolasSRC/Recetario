# ADR-004 · El frontend como libro abierto

- **Estado:** aceptado
- **Fecha:** 2026-11-10
- **Fase:** F3

## Contexto

El requisito de producto es que el recetario se sienta «como un libro en el cual
se muestre una receta por página», con ingredientes y pasos editables y con
recetas creadas a mano, sin video. Una tabla o una lista de tarjetas cumpliría
la función, pero no la intención.

## Decisión

1. **Next.js 16 (App Router) + TypeScript estricto + Tailwind 4**, sin librería
   de componentes. El diseño es específico y no encaja en un sistema genérico.
2. **Una receta = un pliego**: dos páginas en escritorio (ingredientes a la
   izquierda, preparación y fuente a la derecha) y una sola columna en móvil.
   La numeración avanza de dos en dos.
3. **Navegación de libro**: botones anterior/siguiente, contador y flechas
   ← → del teclado, ignoradas cuando el foco está en un campo.
4. **Edición en la misma página**: `RecipeForm` se usa tanto para editar como
   para crear, y guarda con `PATCH /recipes/{id}`. No hay editor aparte.
5. **Alta manual sin video** con `POST /recipes`. El usuario es la fuente, así
   que la receta se guarda `aprobada`, con confianza 1.0 y sin flags. Las
   recetas extraídas por el modelo conservan `por_revisar` cuando faltan datos.
6. **Cliente HTTP propio** (`lib/api.ts`) con errores tipados; el backend se
   configura con `NEXT_PUBLIC_API_URL` (por defecto `http://127.0.0.1:8000`).
7. **CORS local amplio**: `cors_origins` más `cors_origin_regex` para aceptar
   cualquier puerto de `localhost`/`127.0.0.1` durante el desarrollo.

## Consecuencias

- El libro funciona sin estado global: cada página pide su receta y la lista de
  vecinas para la navegación. Con muchas recetas habrá que paginar la lista.
- La edición envía el contenido completo, no un diff; el `PATCH` del backend ya
  es idempotente y valida el esquema.
- Imprimir usa `window.print()` y una hoja de estilos `@media print`; el PDF
  real queda para más adelante.
- El test e2e automatizado sigue pendiente: por ahora la verificación se hace
  con Playwright sobre Edge y capturas manuales.
