"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { ArrowLeftIcon } from "@/components/Icons";
import { RecipeForm } from "@/components/RecipeForm";
import { api } from "@/lib/api";
import type { RecipeContent } from "@/lib/types";

export default function NewRecipePage() {
  const router = useRouter();

  async function handleCreate(content: RecipeContent) {
    const recipe = await api.createRecipe({ ...content, source_url: null });
    router.push(`/recetas/${recipe.id ?? ""}`);
  }

  return (
    <div className="fade-in mx-auto max-w-3xl space-y-6">
      <div className="no-print">
        <Link
          href="/"
          className="inline-flex items-center gap-2 rounded-full border border-white/15 px-4 py-2 text-sm text-paper/80 transition hover:border-white/35 hover:text-paper"
        >
          <ArrowLeftIcon width={16} height={16} />
          Estantería
        </Link>
      </div>

      <header className="max-w-2xl">
        <p className="text-[0.68rem] font-semibold uppercase tracking-[0.32em] text-gold-soft/80">
          Página en blanco
        </p>
        <h1 className="mt-2 font-serif text-4xl text-paper">
          Escribe una receta
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-paper/65">
          Sin video ni inteligencia artificial: tu receta, tus palabras. Al
          guardarla quedará aprobada y lista para cocinar. Puedes editar los
          ingredientes y los pasos tantas veces como quieras.
        </p>
      </header>

      <div className="paper rounded-xl p-6 shadow-book sm:p-9">
        <RecipeForm
          submitLabel="Guardar en el recetario"
          onSubmit={handleCreate}
          onCancel={() => router.push("/")}
        />
      </div>
    </div>
  );
}
