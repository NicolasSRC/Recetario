"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { BookIcon, ImportIcon, PlusIcon, SearchIcon } from "@/components/Icons";
import { RecipeCard } from "@/components/RecipeCard";
import { api } from "@/lib/api";
import type { RecipePage, RecipeStatus } from "@/lib/types";

const filters: { value: "" | RecipeStatus; label: string }[] = [
  { value: "", label: "Todas" },
  { value: "por_revisar", label: "Por revisar" },
  { value: "aprobada", label: "Aprobadas" },
];

export default function LibraryPage() {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"" | RecipeStatus>("");
  const [page, setPage] = useState<RecipePage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(
      async () => {
        setLoading(true);
        try {
          const result = await api.listRecipes({
            q: query,
            status: status || undefined,
          });
          if (!cancelled) {
            setPage(result);
            setError(null);
          }
        } catch (err) {
          if (!cancelled) {
            setError(
              err instanceof Error ? err.message : "No se pudo cargar el recetario.",
            );
          }
        } finally {
          if (!cancelled) setLoading(false);
        }
      },
      query ? 250 : 0,
    );

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query, status]);

  const recipes = page?.items ?? [];
  const total = page?.total ?? 0;
  const reviewing = recipes.filter((r) => r.status === "por_revisar").length;

  return (
    <div className="fade-in space-y-10">
      <section className="relative overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br from-desk-soft via-desk-soft/90 to-desk p-6 shadow-book sm:p-10">
        <div
          aria-hidden
          className="pointer-events-none absolute -right-10 top-1/2 hidden h-64 w-64 -translate-y-1/2 md:block"
        >
          <div className="absolute inset-0 rotate-6 rounded-lg border border-gold/25 bg-gradient-to-br from-wine/60 to-[#3a1a20] shadow-book" />
          <div className="absolute inset-0 translate-x-4 translate-y-4 rounded-lg border border-gold/20 bg-gradient-to-br from-sage/50 to-[#2a3326] shadow-book" />
          <div className="spine absolute inset-y-0 left-0 w-4 rounded-l-lg" />
          <div className="absolute inset-6 flex flex-col justify-between rounded border border-gold/30 p-4">
            <span className="font-serif text-2xl text-paper/90">
              Recetario
            </span>
            <span className="text-[0.6rem] uppercase tracking-[0.3em] text-gold-soft/80">
              cocina · memoria
            </span>
          </div>
        </div>

        <div className="relative max-w-2xl">
          <p className="text-[0.68rem] font-semibold uppercase tracking-[0.32em] text-gold-soft/80">
            Tu biblioteca de cocina
          </p>
          <h1 className="mt-3 font-serif text-4xl leading-tight text-paper sm:text-5xl">
            Cada video,
            <br />
            una página.
          </h1>
          <p className="mt-4 max-w-xl text-sm leading-relaxed text-paper/70 sm:text-base">
            Guarda las recetas que encuentras en TikTok y escríbelas a mano. Se
            leen como un libro: una receta por página, con sus ingredientes y
            sus pasos.
          </p>

          <div className="mt-7 flex flex-wrap gap-3">
            <Link
              href="/importar"
              className="inline-flex items-center gap-2 rounded-full bg-gold px-5 py-2.5 text-sm font-semibold text-desk shadow-card transition hover:bg-gold-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-paper"
            >
              <ImportIcon width={18} height={18} />
              Importar un video
            </Link>
            <Link
              href="/nueva"
              className="inline-flex items-center gap-2 rounded-full border border-paper/25 px-5 py-2.5 text-sm font-semibold text-paper/90 transition hover:border-paper/50 hover:bg-white/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold"
            >
              <PlusIcon width={18} height={18} />
              Escribir una receta
            </Link>
          </div>

          <p className="mt-5 text-xs text-paper/45">
            {total > 0
              ? `${total} ${total === 1 ? "receta guardada" : "recetas guardadas"}`
              : "Tu libro está en blanco: la primera página la escribes tú."}
            {reviewing > 0
              ? ` · ${reviewing} por revisar en esta vista`
              : ""}
          </p>
        </div>
      </section>

      <section aria-labelledby="estanteria" className="space-y-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2
              id="estanteria"
              className="font-serif text-2xl text-paper sm:text-3xl"
            >
              La estantería
            </h2>
            <p className="mt-1 text-sm text-paper/50">
              Abre un libro para leer la receta o editarla.
            </p>
          </div>

          <div className="flex w-full flex-col gap-3 sm:w-auto sm:items-end">
            <label className="relative block w-full sm:w-72">
              <span className="sr-only">Buscar por título o ingrediente</span>
              <SearchIcon
                width={17}
                height={17}
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-paper/40"
              />
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Buscar por receta o ingrediente…"
                className="w-full rounded-full border border-white/15 bg-white/5 py-2.5 pl-9 pr-4 text-sm text-paper placeholder:text-paper/35 focus:border-gold/60 focus:bg-white/10 focus:outline-none focus:ring-2 focus:ring-gold/25"
              />
            </label>

            <div
              className="flex flex-wrap gap-2"
              role="group"
              aria-label="Filtrar por estado"
            >
              {filters.map((filter) => (
                <button
                  key={filter.value || "todas"}
                  type="button"
                  onClick={() => setStatus(filter.value)}
                  aria-pressed={status === filter.value}
                  className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                    status === filter.value
                      ? "border-gold/60 bg-gold/15 text-gold-soft"
                      : "border-white/10 text-paper/60 hover:border-white/25 hover:text-paper"
                  }`}
                >
                  {filter.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {error ? (
          <div
            role="alert"
            className="rounded-xl border border-wine/40 bg-wine/15 p-5 text-sm text-paper/80"
          >
            <p className="font-semibold text-paper">
              No se pudo abrir el recetario
            </p>
            <p className="mt-1 text-paper/65">{error}</p>
            <p className="mt-3 text-xs text-paper/45">
              Arranca la API con{" "}
              <code className="rounded bg-black/30 px-1.5 py-0.5">
                uvicorn app.asgi:app --reload
              </code>{" "}
              desde <code className="rounded bg-black/30 px-1.5 py-0.5">backend/</code>.
            </p>
          </div>
        ) : null}

        {loading ? (
          <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3" aria-busy>
            {[0, 1, 2].map((item) => (
              <li
                key={item}
                className="h-56 animate-pulse rounded-xl bg-paper/10"
              />
            ))}
          </ul>
        ) : recipes.length > 0 ? (
          <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {recipes.map((recipe) => (
              <li key={recipe.id ?? recipe.title}>
                <RecipeCard recipe={recipe} />
              </li>
            ))}
          </ul>
        ) : (
          <div className="paper flex flex-col items-center rounded-xl px-6 py-14 text-center shadow-card">
            <span className="flex h-16 w-16 items-center justify-center rounded-full border border-gold/40 bg-gold/10 text-wine">
              <BookIcon width={30} height={30} />
            </span>
            <h3 className="mt-5 font-serif text-2xl text-ink">
              {query || status
                ? "No hay recetas con ese filtro"
                : "Aún no hay recetas"}
            </h3>
            <p className="mt-2 max-w-md text-sm leading-relaxed text-ink-soft">
              {query || status
                ? "Prueba con otro ingrediente o quita los filtros para ver todo el recetario."
                : "Importa un video de TikTok o escribe tu primera receta a mano. Aparecerá aquí como una página más del libro."}
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              <Link
                href="/importar"
                className="inline-flex items-center gap-2 rounded-full bg-wine px-4 py-2 text-sm font-semibold text-paper transition hover:bg-wine-soft"
              >
                <ImportIcon width={17} height={17} />
                Importar un video
              </Link>
              <Link
                href="/nueva"
                className="inline-flex items-center gap-2 rounded-full border border-ink-soft/30 px-4 py-2 text-sm font-semibold text-ink transition hover:border-ink-soft/60"
              >
                <PlusIcon width={17} height={17} />
                Escribir a mano
              </Link>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
