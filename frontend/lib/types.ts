export type Unit =
  | "g"
  | "kg"
  | "ml"
  | "l"
  | "taza"
  | "cucharada"
  | "cucharadita"
  | "unidad";

export type Evidence = "caption" | "audio" | "pantalla";

export type RecipeStatus = "por_revisar" | "aprobada" | "descartada";

export type Difficulty = "facil" | "media" | "dificil";

export interface Ingredient {
  name: string;
  quantity: number | null;
  unit: Unit | null;
  note: string | null;
  raw_text: string;
  optional: boolean;
  group: string | null;
  evidence: Evidence | null;
}

export interface Step {
  order: number;
  text: string;
  duration_min: number | null;
  timestamp_s: number | null;
}

export interface Nutrition {
  calories_kcal?: number | null;
  protein_g?: number | null;
  carbs_g?: number | null;
  fat_g?: number | null;
  fiber_g?: number | null;
  sugar_g?: number | null;
  sodium_mg?: number | null;
  notes?: string | null;
}

export interface Source {
  url: string;
  author: string | null;
  platform: string;
  captured_at: string;
}

export interface Extraction {
  sources_used: Evidence[];
  confidence: number;
  field_confidence: Record<string, number>;
  model: string | null;
  needs_review: boolean;
  flags: string[];
}

export interface Recipe {
  id: string | null;
  schema_version: number;
  title: string;
  description: string | null;
  language: string;
  servings: number | null;
  prep_time_min: number | null;
  cook_time_min: number | null;
  difficulty: Difficulty | null;
  ingredients: Ingredient[];
  steps: Step[];
  equipment: string[];
  tags: string[];
  nutrition: Nutrition | null;
  notes: string | null;
  source: Source;
  extraction: Extraction;
  status: RecipeStatus;
}

export interface RecipePage {
  items: Recipe[];
  total: number;
  limit: number;
  offset: number;
}

/** Contenido editable de una receta (sin campos de infraestructura). */
export interface RecipeContent {
  title: string;
  description: string | null;
  language: string;
  servings: number | null;
  prep_time_min: number | null;
  cook_time_min: number | null;
  difficulty: Difficulty | null;
  ingredients: Ingredient[];
  steps: Step[];
  equipment: string[];
  tags: string[];
  notes: string | null;
}

export interface RecipeCreateInput extends RecipeContent {
  source_url?: string | null;
  author?: string | null;
}

export type RecipePatch = Partial<RecipeContent> & { status?: RecipeStatus };

export type JobStatus =
  | "en_cola"
  | "procesando"
  | "lista"
  | "fallida"
  | "cancelada";

export type JobStage =
  | "descargando"
  | "transcribiendo"
  | "leyendo_pantalla"
  | "extrayendo"
  | "guardando";

export interface AgentEvent {
  step: number;
  tool: string;
  input: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
  text: string;
  ok: boolean;
  error: string | null;
  duration_ms: number | null;
  cost_usd: number;
}

export interface Job {
  id: string;
  kind: "url" | "texto";
  source_url: string | null;
  status: JobStatus;
  stage: JobStage | null;
  error_code: string | null;
  error_message: string | null;
  recipe_id: string | null;
  cost_usd: number;
  duration_s: number | null;
  created_at: string;
  updated_at: string;
  events: AgentEvent[];
}

export interface JobCreateInput {
  source_url?: string;
  author?: string;
  caption?: string;
  transcript?: string;
  screen_text?: string;
}
