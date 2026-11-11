import Link from "next/link";

import { StatusBadge } from "@/components/StatusBadge";
import { authorName, formatTotalTime } from "@/lib/format";
import type { Recipe } from "@/lib/types";

const spines = [
  "bg-wine",
  "bg-sage",
  "bg-gold",
  "bg-[#4c5d73]",
  "bg-[#8a5a3b]",
];

function spineColor(seed: string): string {
  let hash = 0;
  for (const char of seed) hash = (hash * 31 + char.charCodeAt(0)) % 997;
  return spines[hash % spines.length];
}

export function RecipeCard({ recipe }: { recipe: Recipe }) {
  return (
    <Link
      href={`/recetas/${recipe.id ?? ""}`}
      className="group relative flex h-full overflow-hidden rounded-r-xl rounded-l-md shadow-card outline-none transition duration-200 hover:-translate-y-1 hover:shadow-book focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-2 focus-visible:ring-offset-desk"
    >
      <span
        aria-hidden
        className={`spine w-3 shrink-0 sm:w-4 ${spineColor(recipe.title)}`}
      />
      <article className="paper flex min-h-52 w-full flex-col p-5">
        <div className="mb-3 flex items-start justify-between gap-3">
          <span className="text-[0.62rem] font-semibold uppercase tracking-[0.22em] text-ink-soft/70">
            Receta
          </span>
          <StatusBadge status={recipe.status} />
        </div>

        <h3 className="font-serif text-2xl leading-snug text-ink transition group-hover:text-wine">
          {recipe.title}
        </h3>
        <p className="mt-2 line-clamp-3 text-sm leading-relaxed text-ink-soft">
          {recipe.description ??
            "Una receta guardada en tu recetario, lista para cocinar."}
        </p>

        <div className="mt-auto flex flex-wrap items-center gap-x-4 gap-y-1 pt-4 text-[0.72rem] text-ink-soft">
          <span>{recipe.ingredients.length} {recipe.ingredients.length === 1 ? "ingrediente" : "ingredientes"}</span>
          <span aria-hidden>·</span>
          <span>{recipe.steps.length} {recipe.steps.length === 1 ? "paso" : "pasos"}</span>
          <span aria-hidden>·</span>
          <span>{formatTotalTime(recipe.prep_time_min, recipe.cook_time_min)}</span>
        </div>
        <p className="mt-1 truncate text-[0.7rem] italic text-ink-soft/80">
          {authorName(recipe.source.author)}
        </p>
      </article>
    </Link>
  );
}
