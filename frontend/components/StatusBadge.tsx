import type { JobStatus, RecipeStatus } from "@/lib/types";

const recipeTones: Record<string, string> = {
  aprobada: "border-sage/40 bg-sage/10 text-sage",
  por_revisar: "border-wine/35 bg-wine/10 text-wine",
  descartada: "border-ink-soft/30 bg-ink-soft/10 text-ink-soft",
};

const jobTones: Record<string, string> = {
  en_cola: "border-gold/50 bg-gold/10 text-gold",
  procesando: "border-gold/60 bg-gold/15 text-gold",
  lista: "border-sage/40 bg-sage/10 text-sage",
  fallida: "border-wine/40 bg-wine/10 text-wine",
  cancelada: "border-ink-soft/30 bg-ink-soft/10 text-ink-soft",
};

const jobLabels: Record<string, string> = {
  en_cola: "En cola",
  procesando: "Procesando",
  lista: "Lista",
  fallida: "Fallida",
  cancelada: "Cancelada",
};

const recipeLabels: Record<string, string> = {
  aprobada: "Aprobada",
  por_revisar: "Por revisar",
  descartada: "Descartada",
};

export function StatusBadge({
  status,
}: {
  status: RecipeStatus | JobStatus;
}) {
  const tones = status in jobLabels ? jobTones : recipeTones;
  const labels = status in jobLabels ? jobLabels : recipeLabels;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.12em] ${tones[status] ?? ""}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      {labels[status] ?? status}
    </span>
  );
}
