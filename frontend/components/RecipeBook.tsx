"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ArrowLeftIcon,
  CheckIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ClockIcon,
  DownloadIcon,
  PencilIcon,
  PrintIcon,
  SpinnerIcon,
  TrashIcon,
  UsersIcon,
} from "@/components/Icons";
import { RecipeForm } from "@/components/RecipeForm";
import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import {
  authorName,
  difficultyLabel,
  formatDate,
  formatIngredient,
  formatMinutes,
  formatTotalTime,
} from "@/lib/format";
import type { Recipe, RecipeContent, RecipePage } from "@/lib/types";

const flagLabels: Record<string, string> = {
  pasos_insuficientes: "Faltan pasos",
  porciones_sin_evidencia: "Porciones sin evidencia",
  ingredientes_sin_evidencia: "Ingredientes sin evidencia",
  titulo_sin_evidencia: "Título sin evidencia",
  tiempo_sin_evidencia: "Tiempos sin evidencia",
  baja_confianza: "Confianza baja",
};

function humanizeFlag(flag: string): string {
  if (flagLabels[flag]) return flagLabels[flag];
  const text = flag.replaceAll("_", " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function MetaStat({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="text-gold" aria-hidden>
        {icon}
      </span>
      <span>
        <span className="block text-[0.6rem] font-semibold uppercase tracking-[0.16em] text-ink-soft/70">
          {label}
        </span>
        <span className="block text-sm font-medium text-ink">{value}</span>
      </span>
    </div>
  );
}

function Ornament() {
  return (
    <div className="my-5 flex items-center gap-3 text-gold/70" aria-hidden>
      <span className="h-px flex-1 bg-gradient-to-r from-transparent via-gold/40 to-gold/40" />
      <span className="text-xs tracking-[0.4em]">❦</span>
      <span className="h-px flex-1 bg-gradient-to-l from-transparent via-gold/40 to-gold/40" />
    </div>
  );
}

export function RecipeBook({ recipeId }: { recipeId: string }) {
  const router = useRouter();
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [siblings, setSiblings] = useState<Recipe[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [working, setWorking] = useState<"aprobar" | "borrar" | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const fetchData = useCallback(
    () =>
      Promise.all([
        api.getRecipe(recipeId),
        api.listRecipes({ limit: 100 }),
      ]),
    [recipeId],
  );

  const applyData = useCallback((current: Recipe, page: RecipePage) => {
    setRecipe(current);
    setSiblings(page.items);
    setError(null);
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchData()
      .then(([current, page]) => {
        if (!cancelled) applyData(current, page);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "No se pudo abrir la receta.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [fetchData, applyData]);

  const retryLoad = useCallback(async () => {
    setLoading(true);
    try {
      const [current, page] = await fetchData();
      applyData(current, page);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "No se pudo abrir la receta.",
      );
    } finally {
      setLoading(false);
    }
  }, [fetchData, applyData]);

  const position = useMemo(
    () => siblings.findIndex((item) => item.id === recipeId),
    [siblings, recipeId],
  );
  const previous = position > 0 ? siblings[position - 1] : null;
  const next =
    position >= 0 && position < siblings.length - 1
      ? siblings[position + 1]
      : null;

  const goTo = useCallback(
    (id: string | null) => {
      if (id) router.push(`/recetas/${id}`);
    },
    [router],
  );

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (editing) return;
      const target = event.target as HTMLElement | null;
      if (
        target?.closest(
          "input, textarea, select, button, a, [contenteditable='true']",
        )
      ) {
        return;
      }
      if (event.key === "ArrowLeft" && previous?.id) {
        event.preventDefault();
        goTo(previous.id);
      }
      if (event.key === "ArrowRight" && next?.id) {
        event.preventDefault();
        goTo(next.id);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [editing, previous?.id, next?.id, goTo]);

  async function handleSave(content: RecipeContent) {
    const updated = await api.updateRecipe(recipeId, content);
    setRecipe(updated);
    setSiblings((current) =>
      current.map((item) => (item.id === recipeId ? updated : item)),
    );
    setEditing(false);
    setNotice("Cambios guardados en esta página.");
  }

  async function handleApprove() {
    setWorking("aprobar");
    setNotice(null);
    try {
      const updated = await api.updateRecipe(recipeId, { status: "aprobada" });
      setRecipe(updated);
      setSiblings((current) =>
        current.map((item) => (item.id === recipeId ? updated : item)),
      );
      setNotice("Receta aprobada. Ya no aparecerá como pendiente.");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "No se pudo aprobar la receta.",
      );
    } finally {
      setWorking(null);
    }
  }

  async function handleDelete() {
    if (
      !window.confirm(
        "¿Quitar esta receta del recetario? Esta acción no se puede deshacer.",
      )
    ) {
      return;
    }
    setWorking("borrar");
    try {
      await api.deleteRecipe(recipeId);
      router.push("/");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "No se pudo borrar la receta.",
      );
      setWorking(null);
    }
  }

  if (loading) {
    return (
      <div
        className="mx-auto grid max-w-5xl gap-0 overflow-hidden rounded-xl shadow-book lg:grid-cols-2"
        aria-busy
      >
        <div className="paper min-h-96 animate-pulse p-8" />
        <div className="paper min-h-96 animate-pulse p-8" />
      </div>
    );
  }

  if (error && !recipe) {
    return (
      <div className="paper mx-auto max-w-xl rounded-xl p-8 text-center shadow-book">
        <h1 className="font-serif text-2xl text-ink">
          No se pudo abrir esta página
        </h1>
        <p className="mt-2 text-sm text-ink-soft">{error}</p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <button
            type="button"
            onClick={() => void retryLoad()}
            className="rounded-full bg-wine px-5 py-2 text-sm font-semibold text-paper transition hover:bg-wine-soft"
          >
            Reintentar
          </button>
          <Link
            href="/"
            className="rounded-full border border-ink-soft/30 px-5 py-2 text-sm font-medium text-ink transition hover:border-ink-soft/60"
          >
            Volver a la estantería
          </Link>
        </div>
      </div>
    );
  }

  if (!recipe) return null;

  const totalTime = formatTotalTime(
    recipe.prep_time_min,
    recipe.cook_time_min,
  );
  const groups = new Map<string, typeof recipe.ingredients>();
  for (const ingredient of recipe.ingredients) {
    const key = ingredient.group?.trim() ?? "";
    const bucket = groups.get(key) ?? [];
    bucket.push(ingredient);
    groups.set(key, bucket);
  }

  return (
    <div className="space-y-6">
      <div className="no-print flex flex-wrap items-center justify-between gap-3">
        <Link
          href="/"
          className="inline-flex items-center gap-2 rounded-full border border-white/15 px-4 py-2 text-sm text-paper/80 transition hover:border-white/35 hover:text-paper"
        >
          <ArrowLeftIcon width={16} height={16} />
          Estantería
        </Link>

        <div className="flex flex-wrap items-center gap-2">
          {!editing ? (
            <button
              type="button"
              onClick={() => {
                setEditing(true);
                setNotice(null);
              }}
              className="inline-flex items-center gap-2 rounded-full border border-white/15 px-4 py-2 text-sm text-paper/80 transition hover:border-white/35 hover:text-paper"
            >
              <PencilIcon width={16} height={16} />
              Editar
            </button>
          ) : null}

          {recipe.status === "por_revisar" ? (
            <button
              type="button"
              onClick={() => void handleApprove()}
              disabled={working !== null}
              className="inline-flex items-center gap-2 rounded-full bg-sage px-4 py-2 text-sm font-semibold text-paper transition hover:brightness-110 disabled:opacity-60"
            >
              {working === "aprobar" ? (
                <SpinnerIcon width={16} height={16} />
              ) : (
                <CheckIcon width={16} height={16} />
              )}
              Aprobar
            </button>
          ) : null}

          <button
            type="button"
            onClick={() => window.print()}
            className="inline-flex items-center gap-2 rounded-full border border-white/15 px-4 py-2 text-sm text-paper/80 transition hover:border-white/35 hover:text-paper"
          >
            <PrintIcon width={16} height={16} />
            <span className="hidden sm:inline">Imprimir</span>
          </button>

          <a
            href={api.exportUrl(recipeId, "jsonld")}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-full border border-white/15 px-4 py-2 text-sm text-paper/80 transition hover:border-white/35 hover:text-paper"
          >
            <DownloadIcon width={16} height={16} />
            <span className="hidden sm:inline">JSON-LD</span>
          </a>

          <a
            href={api.exportUrl(recipeId, "md")}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-full border border-white/15 px-4 py-2 text-sm text-paper/80 transition hover:border-white/35 hover:text-paper"
          >
            <DownloadIcon width={16} height={16} />
            <span className="hidden sm:inline">Markdown</span>
          </a>

          <button
            type="button"
            onClick={() => void handleDelete()}
            disabled={working !== null}
            aria-label="Borrar receta"
            className="inline-flex items-center gap-2 rounded-full border border-wine/40 px-3 py-2 text-sm text-wine-soft transition hover:bg-wine/20 disabled:opacity-60"
          >
            {working === "borrar" ? (
              <SpinnerIcon width={16} height={16} />
            ) : (
              <TrashIcon width={16} height={16} />
            )}
          </button>
        </div>
      </div>

      {notice ? (
        <p
          role="status"
          className="no-print rounded-lg border border-sage/30 bg-sage/15 px-4 py-2 text-sm text-paper/80"
        >
          {notice}
        </p>
      ) : null}

      {error ? (
        <p
          role="alert"
          className="no-print rounded-lg border border-wine/40 bg-wine/15 px-4 py-2 text-sm text-paper/80"
        >
          {error}
        </p>
      ) : null}

      {recipe.status === "por_revisar" ? (
        <div className="no-print flex flex-wrap items-center gap-3 rounded-xl border border-gold/25 bg-gold/10 px-4 py-3 text-sm text-paper/80">
          <span className="ribbon rounded-sm px-2 py-0.5 text-[0.62rem] font-bold uppercase tracking-[0.18em] text-paper">
            Por revisar
          </span>
          <span>
            Confía en lo que ves: si falta algo, edita la página o apruébala
            tal cual.
          </span>
          {recipe.extraction.flags.length > 0 ? (
            <span className="flex flex-wrap gap-1.5">
              {recipe.extraction.flags.map((flag) => (
                <span
                  key={flag}
                  className="rounded-full border border-gold/30 px-2 py-0.5 text-[0.68rem] text-gold-soft"
                >
                  {humanizeFlag(flag)}
                </span>
              ))}
            </span>
          ) : null}
        </div>
      ) : null}

      {editing ? (
        <div className="paper page-in rounded-xl p-6 shadow-book sm:p-8">
          <div className="mb-6 flex flex-wrap items-baseline justify-between gap-2 border-b border-ink-soft/15 pb-4">
            <h1 className="font-serif text-2xl text-ink">
              Editando «{recipe.title}»
            </h1>
            <p className="text-xs text-ink-soft">
              Los cambios se guardan en esta misma receta.
            </p>
          </div>
          <RecipeForm
            initial={recipe}
            submitLabel="Guardar cambios"
            onSubmit={handleSave}
            onCancel={() => setEditing(false)}
          />
        </div>
      ) : (
        <>
          <div className="page-in relative overflow-hidden rounded-xl shadow-book">
            <div className="grid lg:grid-cols-2">
              {/* Página izquierda: la receta y sus ingredientes */}
              <article className="paper paper-edge relative px-6 py-8 sm:px-9 sm:py-10">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-[0.62rem] font-semibold uppercase tracking-[0.3em] text-ink-soft/70">
                    Receta
                  </p>
                  <StatusBadge status={recipe.status} />
                </div>

                <h1 className="mt-3 font-serif text-3xl leading-tight text-ink sm:text-4xl">
                  {recipe.title}
                </h1>
                {recipe.description ? (
                  <p className="mt-3 font-serif text-base italic leading-relaxed text-ink-soft">
                    {recipe.description}
                  </p>
                ) : null}

                <div className="mt-6 flex flex-wrap gap-x-6 gap-y-3 border-y border-ink-soft/15 py-4">
                  <MetaStat
                    icon={<ClockIcon width={18} height={18} />}
                    label="Tiempo total"
                    value={totalTime}
                  />
                  <MetaStat
                    icon={<UsersIcon width={18} height={18} />}
                    label="Porciones"
                    value={
                      recipe.servings === null
                        ? "—"
                        : String(recipe.servings)
                    }
                  />
                  <MetaStat
                    icon={<span className="font-serif text-lg">✦</span>}
                    label="Dificultad"
                    value={difficultyLabel(recipe.difficulty)}
                  />
                </div>

                <Ornament />

                <section aria-labelledby="ingredientes">
                  <div className="flex items-baseline justify-between gap-3">
                    <h2
                      id="ingredientes"
                      className="font-serif text-xl text-wine"
                    >
                      Ingredientes
                    </h2>
                    <span className="text-[0.68rem] uppercase tracking-[0.16em] text-ink-soft/70">
                      {recipe.ingredients.length}
                    </span>
                  </div>

                  <div className="mt-3 space-y-5">
                    {Array.from(groups.entries()).map(([group, items]) => (
                      <div key={group || "principales"}>
                        {group ? (
                          <h3 className="mb-2 text-[0.66rem] font-semibold uppercase tracking-[0.2em] text-ink-soft">
                            {group}
                          </h3>
                        ) : null}
                        <ul className="space-y-2.5">
                          {items.map((ingredient, index) => (
                            <li
                              key={`${ingredient.name}-${index}`}
                              className="flex items-baseline gap-2 text-[0.95rem] leading-relaxed"
                            >
                              <span
                                aria-hidden
                                className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-gold"
                              />
                              <span>
                                <span className="font-medium text-ink">
                                  {formatIngredient(ingredient)}
                                </span>
                                {ingredient.note &&
                                !ingredient.raw_text.includes(
                                  ingredient.note,
                                ) ? (
                                  <span className="text-ink-soft">
                                    {" "}
                                    · {ingredient.note}
                                  </span>
                                ) : null}
                                {ingredient.optional ? (
                                  <span className="ml-1.5 rounded border border-ink-soft/25 px-1 py-0.5 align-middle text-[0.58rem] uppercase tracking-wide text-ink-soft">
                                    opcional
                                  </span>
                                ) : null}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                </section>

                {recipe.equipment.length > 0 ? (
                  <section className="mt-6" aria-labelledby="utensilios">
                    <h2
                      id="utensilios"
                      className="font-serif text-lg text-wine"
                    >
                      Utensilios
                    </h2>
                    <ul className="mt-2 flex flex-wrap gap-2">
                      {recipe.equipment.map((item) => (
                        <li
                          key={item}
                          className="rounded-full border border-ink-soft/20 px-3 py-1 text-xs text-ink-soft"
                        >
                          {item}
                        </li>
                      ))}
                    </ul>
                  </section>
                ) : null}

                <p className="mt-8 text-center font-serif text-xs text-ink-soft/60">
                  — {position >= 0 ? position * 2 + 1 : 1} —
                </p>
              </article>

              {/* Página derecha: pasos, notas y fuente */}
              <article className="paper paper-edge relative border-t border-ink-soft/15 px-6 py-8 sm:px-9 sm:py-10 lg:border-l-0 lg:border-t-0">
                <div
                  aria-hidden
                  className="gutter pointer-events-none absolute inset-y-0 -left-3 hidden w-6 lg:block"
                />

                <section aria-labelledby="preparacion">
                  <div className="flex items-baseline justify-between gap-3">
                    <h2
                      id="preparacion"
                      className="font-serif text-xl text-wine"
                    >
                      Preparación
                    </h2>
                    <span className="text-[0.68rem] uppercase tracking-[0.16em] text-ink-soft/70">
                      {recipe.steps.length}{" "}
                      {recipe.steps.length === 1 ? "paso" : "pasos"}
                    </span>
                  </div>

                  <ol className="mt-4 space-y-4">
                    {recipe.steps.map((step) => (
                      <li key={step.order} className="flex gap-3">
                        <span
                          aria-hidden
                          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-wine/25 bg-wine/5 font-serif text-sm font-semibold text-wine"
                        >
                          {step.order}
                        </span>
                        <div className="min-w-0">
                          <p className="text-[0.95rem] leading-relaxed text-ink">
                            {step.text}
                          </p>
                          {step.duration_min !== null ? (
                            <p className="mt-1 inline-flex items-center gap-1 text-[0.7rem] text-ink-soft">
                              <ClockIcon width={13} height={13} />
                              {formatMinutes(step.duration_min)}
                            </p>
                          ) : null}
                        </div>
                      </li>
                    ))}
                  </ol>
                </section>

                {recipe.notes ? (
                  <>
                    <Ornament />
                    <section aria-labelledby="notas">
                      <h2 id="notas" className="font-serif text-xl text-wine">
                        Notas
                      </h2>
                      <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-ink-soft">
                        {recipe.notes}
                      </p>
                    </section>
                  </>
                ) : null}

                <Ornament />

                <section
                  aria-labelledby="fuente"
                  className="text-xs leading-relaxed text-ink-soft"
                >
                  <h2
                    id="fuente"
                    className="text-[0.62rem] font-semibold uppercase tracking-[0.22em] text-ink-soft/70"
                  >
                    Fuente
                  </h2>
                  <p className="mt-2 font-serif text-sm text-ink">
                    {authorName(recipe.source.author)}
                  </p>
                  <p className="mt-0.5">
                    {recipe.source.platform} ·{" "}
                    {formatDate(recipe.source.captured_at)}
                  </p>
                  {recipe.source.url.startsWith("http") ? (
                    <a
                      href={recipe.source.url}
                      target="_blank"
                      rel="noreferrer"
                      className="link-ink mt-1 inline-block break-all"
                    >
                      {recipe.source.url}
                    </a>
                  ) : null}

                  {recipe.tags.length > 0 ? (
                    <ul className="mt-3 flex flex-wrap gap-1.5">
                      {recipe.tags.map((tag) => (
                        <li
                          key={tag}
                          className="rounded-full bg-ink/5 px-2 py-0.5 text-[0.68rem] text-ink-soft"
                        >
                          #{tag}
                        </li>
                      ))}
                    </ul>
                  ) : null}

                  <p className="mt-4 border-t border-ink-soft/15 pt-3 text-[0.66rem] text-ink-soft/70">
                    Confianza {Math.round(recipe.extraction.confidence * 100)}%
                    {recipe.extraction.sources_used.length > 0
                      ? ` · fuentes: ${recipe.extraction.sources_used.join(", ")}`
                      : ""}
                    {recipe.extraction.model
                      ? ` · ${recipe.extraction.model}`
                      : ""}
                  </p>
                </section>

                <p className="mt-8 text-center font-serif text-xs text-ink-soft/60">
                  — {position >= 0 ? position * 2 + 2 : 2} —
                </p>
              </article>
            </div>
          </div>

          <nav
            aria-label="Pasar página"
            className="no-print grid grid-cols-[1fr_auto_1fr] items-center gap-2"
          >
            <button
              type="button"
              onClick={() => goTo(previous?.id ?? null)}
              disabled={!previous}
              className="group flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-left transition enabled:hover:border-gold/40 enabled:hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-30"
            >
              <ChevronLeftIcon width={18} height={18} className="shrink-0" />
              <span className="min-w-0">
                <span className="block text-[0.6rem] uppercase tracking-[0.18em] text-paper/40">
                  Anterior
                </span>
                <span className="block truncate text-sm text-paper/75">
                  {previous?.title ?? "Primera página"}
                </span>
              </span>
            </button>

            <p className="px-2 text-center text-[0.68rem] uppercase tracking-[0.16em] text-paper/40">
              {position >= 0
                ? `${position + 1} de ${siblings.length}`
                : "Receta"}
              <span className="mt-1 hidden text-[0.6rem] normal-case tracking-normal text-paper/30 sm:block">
                ← → para pasar página
              </span>
            </p>

            <button
              type="button"
              onClick={() => goTo(next?.id ?? null)}
              disabled={!next}
              className="group flex items-center justify-end gap-2 rounded-lg border border-white/10 px-3 py-2 text-right transition enabled:hover:border-gold/40 enabled:hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-30"
            >
              <span className="min-w-0">
                <span className="block text-[0.6rem] uppercase tracking-[0.18em] text-paper/40">
                  Siguiente
                </span>
                <span className="block truncate text-sm text-paper/75">
                  {next?.title ?? "Última página"}
                </span>
              </span>
              <ChevronRightIcon width={18} height={18} className="shrink-0" />
            </button>
          </nav>
        </>
      )}
    </div>
  );
}
