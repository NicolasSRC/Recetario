import type {
  Job,
  JobCreateInput,
  Recipe,
  RecipeCreateInput,
  RecipePage,
  RecipePatch,
  RecipeStatus,
} from "./types";

const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"
).replace(/\/$/, "");

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      cache: "no-store",
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError(
      "No se pudo conectar con la API. ¿Está corriendo el backend en " +
        `${API_URL}?`,
      0,
    );
  }

  if (!response.ok) {
    let detail = `Error ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") {
        detail = body.detail;
      } else if (Array.isArray(body.detail)) {
        detail = body.detail
          .map((item) =>
            typeof item === "object" && item && "msg" in item
              ? String((item as { msg: unknown }).msg)
              : JSON.stringify(item),
          )
          .join(" · ");
      }
    } catch {
      // La respuesta no era JSON: se conserva el mensaje genérico.
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export interface ListParams {
  limit?: number;
  offset?: number;
  status?: RecipeStatus;
  q?: string;
}

export const api = {
  listRecipes(params: ListParams = {}): Promise<RecipePage> {
    const search = new URLSearchParams();
    search.set("limit", String(params.limit ?? 100));
    search.set("offset", String(params.offset ?? 0));
    if (params.status) search.set("status", params.status);
    if (params.q?.trim()) search.set("q", params.q.trim());
    return request<RecipePage>(`/api/v1/recipes?${search.toString()}`);
  },

  getRecipe(id: string): Promise<Recipe> {
    return request<Recipe>(`/api/v1/recipes/${encodeURIComponent(id)}`);
  },

  createRecipe(payload: RecipeCreateInput): Promise<Recipe> {
    return request<Recipe>("/api/v1/recipes", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  updateRecipe(id: string, patch: RecipePatch): Promise<Recipe> {
    return request<Recipe>(`/api/v1/recipes/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
  },

  deleteRecipe(id: string): Promise<void> {
    return request<void>(`/api/v1/recipes/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  },

  createJob(payload: JobCreateInput): Promise<Job> {
    return request<Job>("/api/v1/jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getJob(id: string): Promise<Job> {
    return request<Job>(`/api/v1/jobs/${encodeURIComponent(id)}`);
  },

  retryJob(id: string): Promise<Job> {
    return request<Job>(`/api/v1/jobs/${encodeURIComponent(id)}/retry`, {
      method: "POST",
    });
  },

  cancelJob(id: string): Promise<Job> {
    return request<Job>(`/api/v1/jobs/${encodeURIComponent(id)}/cancel`, {
      method: "POST",
    });
  },

  exportUrl(id: string, format: "jsonld" | "md" | "pdf"): string {
    return `${API_URL}/api/v1/recipes/${encodeURIComponent(id)}/export?format=${format}`;
  },
};
