"use client";

import { useId, useState } from "react";

import { PlusIcon, SpinnerIcon, TrashIcon } from "@/components/Icons";
import type {
  Difficulty,
  Evidence,
  Ingredient,
  Recipe,
  RecipeContent,
  Step,
  Unit,
} from "@/lib/types";

const units: { value: Unit | ""; label: string }[] = [
  { value: "", label: "Sin unidad" },
  { value: "g", label: "g" },
  { value: "kg", label: "kg" },
  { value: "ml", label: "ml" },
  { value: "l", label: "l" },
  { value: "taza", label: "taza" },
  { value: "cucharada", label: "cucharada" },
  { value: "cucharadita", label: "cucharadita" },
  { value: "unidad", label: "unidad" },
];

const difficulties: { value: Difficulty | ""; label: string }[] = [
  { value: "", label: "Sin definir" },
  { value: "facil", label: "Fácil" },
  { value: "media", label: "Media" },
  { value: "dificil", label: "Difícil" },
];

interface IngredientDraft {
  key: string;
  name: string;
  quantity: string;
  unit: Unit | "";
  note: string;
  rawText: string;
  optional: boolean;
  evidence: Evidence | null;
  snapshot: string;
}

interface StepDraft {
  key: string;
  text: string;
  duration: string;
  timestamp: number | null;
}

function snapshotOf(draft: IngredientDraft): string {
  return [draft.name, draft.quantity, draft.unit, draft.note].join("|");
}

function composeRaw(draft: IngredientDraft): string {
  const quantity = draft.quantity.trim();
  const unit = draft.unit === "unidad" ? "" : draft.unit;
  const name = draft.name.trim();
  const base = [quantity, unit, name].filter(Boolean).join(" ");
  return draft.note.trim() ? `${base} (${draft.note.trim()})` : base;
}

function toIngredientDraft(ingredient: Ingredient, key: string): IngredientDraft {
  const draft: IngredientDraft = {
    key,
    name: ingredient.name,
    quantity:
      ingredient.quantity === null ? "" : String(ingredient.quantity),
    unit: ingredient.unit ?? "",
    note: ingredient.note ?? "",
    rawText: ingredient.raw_text,
    optional: ingredient.optional,
    evidence: ingredient.evidence,
    snapshot: "",
  };
  draft.snapshot = snapshotOf(draft);
  return draft;
}

function emptyIngredient(key: string): IngredientDraft {
  return {
    key,
    name: "",
    quantity: "",
    unit: "",
    note: "",
    rawText: "",
    optional: false,
    evidence: null,
    snapshot: "",
  };
}

function toStepDraft(step: Step, key: string): StepDraft {
  return {
    key,
    text: step.text,
    duration: step.duration_min === null ? "" : String(step.duration_min),
    timestamp: step.timestamp_s,
  };
}

function emptyStep(key: string): StepDraft {
  return { key, text: "", duration: "", timestamp: null };
}

function parseNumber(value: string): number | null {
  const trimmed = value.trim().replace(",", ".");
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

let keySeed = 0;

function makeKey(prefix: string): string {
  keySeed += 1;
  return `${prefix}-${keySeed}`;
}

export interface RecipeFormProps {
  initial?: Recipe;
  submitLabel?: string;
  onSubmit: (content: RecipeContent) => Promise<void>;
  onCancel?: () => void;
}

export function RecipeForm({
  initial,
  submitLabel = "Guardar receta",
  onSubmit,
  onCancel,
}: RecipeFormProps) {
  const formId = useId();

  const [title, setTitle] = useState(initial?.title ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [servings, setServings] = useState(
    initial?.servings === null || initial?.servings === undefined
      ? ""
      : String(initial.servings),
  );
  const [prepTime, setPrepTime] = useState(
    initial?.prep_time_min === null || initial?.prep_time_min === undefined
      ? ""
      : String(initial.prep_time_min),
  );
  const [cookTime, setCookTime] = useState(
    initial?.cook_time_min === null || initial?.cook_time_min === undefined
      ? ""
      : String(initial.cook_time_min),
  );
  const [difficulty, setDifficulty] = useState<Difficulty | "">(
    initial?.difficulty ?? "",
  );
  const [tags, setTags] = useState((initial?.tags ?? []).join(", "));
  const [equipment, setEquipment] = useState(
    (initial?.equipment ?? []).join(", "),
  );
  const [notes, setNotes] = useState(initial?.notes ?? "");

  const [ingredients, setIngredients] = useState<IngredientDraft[]>(() =>
    initial?.ingredients.length
      ? initial.ingredients.map((item, index) =>
          toIngredientDraft(item, `${formId}-ing-${index}`),
        )
      : [emptyIngredient(`${formId}-ing-0`)],
  );
  const [steps, setSteps] = useState<StepDraft[]>(() =>
    initial?.steps.length
      ? initial.steps.map((item, index) =>
          toStepDraft(item, `${formId}-step-${index}`),
        )
      : [emptyStep(`${formId}-step-0`)],
  );

  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function updateIngredient(key: string, patch: Partial<IngredientDraft>) {
    setIngredients((current) =>
      current.map((item) =>
        item.key === key ? { ...item, ...patch } : item,
      ),
    );
  }

  function updateStep(key: string, patch: Partial<StepDraft>) {
    setSteps((current) =>
      current.map((item) => (item.key === key ? { ...item, ...patch } : item)),
    );
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!title.trim()) {
      setError("La receta necesita un título.");
      return;
    }

    const filledIngredients = ingredients.filter((item) => item.name.trim());
    if (filledIngredients.length === 0) {
      setError("Añade al menos un ingrediente con nombre.");
      return;
    }

    const filledSteps = steps.filter((item) => item.text.trim());
    if (filledSteps.length === 0) {
      setError("Añade al menos un paso.");
      return;
    }

    const parsedIngredients: Ingredient[] = filledIngredients.map((item) => {
      const dirty = item.snapshot === "" || snapshotOf(item) !== item.snapshot;
      const rawText =
        dirty || !item.rawText.trim() ? composeRaw(item) : item.rawText.trim();
      return {
        name: item.name.trim(),
        quantity: parseNumber(item.quantity),
        unit: item.unit || null,
        note: item.note.trim() || null,
        raw_text: rawText,
        optional: item.optional,
        group: null,
        evidence: item.evidence ?? "caption",
      };
    });

    const parsedSteps: Step[] = filledSteps.map((item, index) => ({
      order: index + 1,
      text: item.text.trim(),
      duration_min: parseNumber(item.duration),
      timestamp_s: item.timestamp,
    }));

    const content: RecipeContent = {
      title: title.trim(),
      description: description.trim() || null,
      language: initial?.language ?? "es",
      servings: parseNumber(servings),
      prep_time_min: parseNumber(prepTime),
      cook_time_min: parseNumber(cookTime),
      difficulty: difficulty || null,
      ingredients: parsedIngredients,
      steps: parsedSteps,
      equipment: equipment
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
      tags: Array.from(
        new Set(
          tags
            .split(",")
            .map((item) => item.trim().toLowerCase())
            .filter(Boolean),
        ),
      ),
      notes: notes.trim() || null,
    };

    setSaving(true);
    try {
      await onSubmit(content);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "No se pudo guardar la receta.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-8"
      aria-describedby={error ? `${formId}-error` : undefined}
    >
      <section className="space-y-4">
        <h2 className="font-serif text-2xl text-ink">Lo esencial</h2>

        <div>
          <label className="field-label" htmlFor={`${formId}-title`}>
            Título
          </label>
          <input
            id={`${formId}-title`}
            className="field font-serif text-xl"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Tortilla de patatas"
            required
            maxLength={300}
          />
        </div>

        <div>
          <label className="field-label" htmlFor={`${formId}-description`}>
            Descripción
          </label>
          <textarea
            id={`${formId}-description`}
            className="field min-h-20 resize-y"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="La clásica tortilla española, jugosa por dentro."
          />
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div>
            <label className="field-label" htmlFor={`${formId}-servings`}>
              Porciones
            </label>
            <input
              id={`${formId}-servings`}
              className="field"
              inputMode="numeric"
              value={servings}
              onChange={(event) => setServings(event.target.value)}
              placeholder="4"
            />
          </div>
          <div>
            <label className="field-label" htmlFor={`${formId}-prep`}>
              Preparación (min)
            </label>
            <input
              id={`${formId}-prep`}
              className="field"
              inputMode="numeric"
              value={prepTime}
              onChange={(event) => setPrepTime(event.target.value)}
              placeholder="10"
            />
          </div>
          <div>
            <label className="field-label" htmlFor={`${formId}-cook`}>
              Cocción (min)
            </label>
            <input
              id={`${formId}-cook`}
              className="field"
              inputMode="numeric"
              value={cookTime}
              onChange={(event) => setCookTime(event.target.value)}
              placeholder="30"
            />
          </div>
          <div>
            <label className="field-label" htmlFor={`${formId}-difficulty`}>
              Dificultad
            </label>
            <select
              id={`${formId}-difficulty`}
              className="field"
              value={difficulty}
              onChange={(event) =>
                setDifficulty(event.target.value as Difficulty | "")
              }
            >
              {difficulties.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>

      <section className="space-y-3" aria-labelledby={`${formId}-ingredients`}>
        <div className="flex items-baseline justify-between gap-3">
          <h2
            id={`${formId}-ingredients`}
            className="font-serif text-2xl text-ink"
          >
            Ingredientes
          </h2>
          <span className="text-xs text-ink-soft">
            {ingredients.length} en la lista
          </span>
        </div>

        <ul className="space-y-3">
          {ingredients.map((item, index) => (
            <li
              key={item.key}
              className="rounded-lg border border-ink-soft/15 bg-paper-2/60 p-3"
            >
              <div className="grid grid-cols-[4.5rem_7.5rem_minmax(0,1fr)_2rem] items-end gap-2 sm:grid-cols-[5rem_8rem_minmax(0,1fr)_2rem]">
                <div>
                  <label
                    className="field-label"
                    htmlFor={`${item.key}-quantity`}
                  >
                    Cantidad
                  </label>
                  <input
                    id={`${item.key}-quantity`}
                    className="field"
                    inputMode="decimal"
                    value={item.quantity}
                    onChange={(event) =>
                      updateIngredient(item.key, {
                        quantity: event.target.value,
                      })
                    }
                    placeholder="2"
                  />
                </div>
                <div>
                  <label className="field-label" htmlFor={`${item.key}-unit`}>
                    Unidad
                  </label>
                  <select
                    id={`${item.key}-unit`}
                    className="field text-sm"
                    value={item.unit}
                    onChange={(event) =>
                      updateIngredient(item.key, {
                        unit: event.target.value as Unit | "",
                      })
                    }
                  >
                    {units.map((unit) => (
                      <option key={unit.value} value={unit.value}>
                        {unit.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="field-label" htmlFor={`${item.key}-name`}>
                    Ingrediente {index + 1}
                  </label>
                  <input
                    id={`${item.key}-name`}
                    className="field"
                    value={item.name}
                    onChange={(event) =>
                      updateIngredient(item.key, { name: event.target.value })
                    }
                    placeholder="harina integral"
                  />
                </div>
                <button
                  type="button"
                  onClick={() =>
                    setIngredients((current) =>
                      current.length > 1
                        ? current.filter((row) => row.key !== item.key)
                        : current,
                    )
                  }
                  disabled={ingredients.length === 1}
                  aria-label={`Quitar ingrediente ${index + 1}`}
                  className="mb-0.5 flex h-9 w-9 items-center justify-center rounded-md text-ink-soft transition hover:bg-wine/10 hover:text-wine disabled:cursor-not-allowed disabled:opacity-30"
                >
                  <TrashIcon width={17} height={17} />
                </button>
              </div>

              <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center">
                <label
                  className="sr-only"
                  htmlFor={`${item.key}-note`}
                >
                  Nota del ingrediente {index + 1}
                </label>
                <input
                  id={`${item.key}-note`}
                  className="field flex-1 text-sm"
                  value={item.note}
                  onChange={(event) =>
                    updateIngredient(item.key, { note: event.target.value })
                  }
                  placeholder="Nota: picada fina, en cubos…"
                />
                <label className="flex items-center gap-2 text-xs text-ink-soft">
                  <input
                    type="checkbox"
                    checked={item.optional}
                    onChange={(event) =>
                      updateIngredient(item.key, {
                        optional: event.target.checked,
                      })
                    }
                    className="h-4 w-4 accent-[#7b2d3b]"
                  />
                  Opcional
                </label>
              </div>
            </li>
          ))}
        </ul>

        <button
          type="button"
          onClick={() =>
            setIngredients((current) => [
              ...current,
              emptyIngredient(makeKey("ing")),
            ])
          }
          className="inline-flex items-center gap-2 rounded-full border border-ink-soft/25 px-4 py-2 text-sm font-medium text-ink transition hover:border-wine/40 hover:bg-wine/5 hover:text-wine"
        >
          <PlusIcon width={16} height={16} />
          Añadir ingrediente
        </button>
      </section>

      <section className="space-y-3" aria-labelledby={`${formId}-steps`}>
        <div className="flex items-baseline justify-between gap-3">
          <h2 id={`${formId}-steps`} className="font-serif text-2xl text-ink">
            Pasos
          </h2>
          <span className="text-xs text-ink-soft">
            {steps.length} {steps.length === 1 ? "paso" : "pasos"}
          </span>
        </div>

        <ol className="space-y-3">
          {steps.map((item, index) => (
            <li
              key={item.key}
              className="flex gap-3 rounded-lg border border-ink-soft/15 bg-paper-2/60 p-3"
            >
              <span
                aria-hidden
                className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-wine/10 font-serif text-sm font-semibold text-wine"
              >
                {index + 1}
              </span>
              <div className="min-w-0 flex-1">
                <label className="sr-only" htmlFor={`${item.key}-step`}>
                  Paso {index + 1}
                </label>
                <textarea
                  id={`${item.key}-step`}
                  className="field min-h-16 resize-y text-sm"
                  value={item.text}
                  onChange={(event) =>
                    updateStep(item.key, { text: event.target.value })
                  }
                  placeholder="Describe el paso con tus palabras…"
                />
                <div className="mt-2 flex items-center gap-2">
                  <label
                    className="text-xs text-ink-soft"
                    htmlFor={`${item.key}-duration`}
                  >
                    Duración (min)
                  </label>
                  <input
                    id={`${item.key}-duration`}
                    className="field w-24 text-sm"
                    inputMode="numeric"
                    value={item.duration}
                    onChange={(event) =>
                      updateStep(item.key, { duration: event.target.value })
                    }
                    placeholder="5"
                  />
                </div>
              </div>
              <button
                type="button"
                onClick={() =>
                  setSteps((current) =>
                    current.length > 1
                      ? current.filter((row) => row.key !== item.key)
                      : current,
                  )
                }
                disabled={steps.length === 1}
                aria-label={`Quitar paso ${index + 1}`}
                className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-ink-soft transition hover:bg-wine/10 hover:text-wine disabled:cursor-not-allowed disabled:opacity-30"
              >
                <TrashIcon width={16} height={16} />
              </button>
            </li>
          ))}
        </ol>

        <button
          type="button"
          onClick={() =>
            setSteps((current) => [...current, emptyStep(makeKey("step"))])
          }
          className="inline-flex items-center gap-2 rounded-full border border-ink-soft/25 px-4 py-2 text-sm font-medium text-ink transition hover:border-wine/40 hover:bg-wine/5 hover:text-wine"
        >
          <PlusIcon width={16} height={16} />
          Añadir paso
        </button>
      </section>

      <section className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="field-label" htmlFor={`${formId}-tags`}>
            Etiquetas (separadas por comas)
          </label>
          <input
            id={`${formId}-tags`}
            className="field"
            value={tags}
            onChange={(event) => setTags(event.target.value)}
            placeholder="pollo, rápido, cena"
          />
        </div>
        <div>
          <label className="field-label" htmlFor={`${formId}-equipment`}>
            Utensilios (separados por comas)
          </label>
          <input
            id={`${formId}-equipment`}
            className="field"
            value={equipment}
            onChange={(event) => setEquipment(event.target.value)}
            placeholder="sartén, batidora"
          />
        </div>
        <div className="sm:col-span-2">
          <label className="field-label" htmlFor={`${formId}-notes`}>
            Notas
          </label>
          <textarea
            id={`${formId}-notes`}
            className="field min-h-16 resize-y"
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            placeholder="Trucos, sustituciones, cómo servir…"
          />
        </div>
      </section>

      {error ? (
        <p
          id={`${formId}-error`}
          role="alert"
          className="rounded-lg border border-wine/30 bg-wine/10 px-4 py-3 text-sm text-wine"
        >
          {error}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-3 border-t border-ink-soft/15 pt-5">
        <button
          type="submit"
          disabled={saving}
          className="inline-flex items-center gap-2 rounded-full bg-wine px-6 py-2.5 text-sm font-semibold text-paper shadow-card transition hover:bg-wine-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wine/50 focus-visible:ring-offset-2 disabled:cursor-wait disabled:opacity-70"
        >
          {saving ? <SpinnerIcon width={17} height={17} /> : null}
          {saving ? "Guardando…" : submitLabel}
        </button>
        {onCancel ? (
          <button
            type="button"
            onClick={onCancel}
            className="rounded-full border border-ink-soft/30 px-5 py-2.5 text-sm font-medium text-ink transition hover:border-ink-soft/60"
          >
            Cancelar
          </button>
        ) : null}
      </div>
    </form>
  );
}
