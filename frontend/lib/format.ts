import type { Ingredient, RecipeStatus, Step } from "./types";

export function formatQuantity(quantity: number | null): string {
  if (quantity === null || Number.isNaN(quantity)) return "";
  return Number.isInteger(quantity)
    ? String(quantity)
    : String(Number(quantity.toFixed(2)));
}

export function formatIngredient(ingredient: Ingredient): string {
  if (ingredient.raw_text.trim()) return ingredient.raw_text.trim();

  const parts = [
    formatQuantity(ingredient.quantity),
    ingredient.unit ?? "",
    ingredient.name,
  ].filter(Boolean);
  const base = parts.join(" ");
  return ingredient.note ? `${base} (${ingredient.note})` : base;
}

export function formatStep(step: Step): string {
  return step.text.trim();
}

export function formatMinutes(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return "—";
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours} h` : `${hours} h ${rest} min`;
}

export function formatTotalTime(
  prep: number | null,
  cook: number | null,
): string {
  if (prep === null && cook === null) return "—";
  return formatMinutes((prep ?? 0) + (cook ?? 0));
}

export function statusLabel(status: RecipeStatus): string {
  switch (status) {
    case "aprobada":
      return "Aprobada";
    case "por_revisar":
      return "Por revisar";
    default:
      return "Descartada";
  }
}

export function difficultyLabel(
  difficulty: "facil" | "media" | "dificil" | null,
): string {
  switch (difficulty) {
    case "facil":
      return "Fácil";
    case "media":
      return "Media";
    case "dificil":
      return "Difícil";
    default:
      return "—";
  }
}

export function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("es", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(date);
}

export function authorName(author: string | null): string {
  return author?.trim() ? author : "Autor desconocido";
}
