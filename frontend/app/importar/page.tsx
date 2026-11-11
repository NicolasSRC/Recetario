"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  ArrowLeftIcon,
  CheckIcon,
  ImportIcon,
  SpinnerIcon,
} from "@/components/Icons";
import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import type { Job, JobStage } from "@/lib/types";

const stages: { key: JobStage; label: string; hint: string }[] = [
  {
    key: "descargando",
    label: "Descargar el video",
    hint: "Metadatos y audio con yt-dlp.",
  },
  {
    key: "transcribiendo",
    label: "Transcribir el audio",
    hint: "faster-whisper, en tu equipo.",
  },
  {
    key: "leyendo_pantalla",
    label: "Leer el texto en pantalla",
    hint: "Solo si faltan datos: frames con ffmpeg y OCR o visión.",
  },
  {
    key: "extrayendo",
    label: "Extraer la receta",
    hint: "El modelo ordena ingredientes y pasos.",
  },
  {
    key: "guardando",
    label: "Guardar la página",
    hint: "La receta entra en el recetario.",
  },
];

const toolLabels: Record<string, string> = {
  get_metadata: "Leer metadatos",
  transcribe_audio: "Transcribir el audio",
  extract_frames: "Leer el texto en pantalla",
  extract_recipe: "Extraer la receta",
  validate_recipe: "Validar la receta",
  save_recipe: "Guardar la receta",
  ask_user: "Preguntar al usuario",
  decision: "Decisión del agente",
};

const errorText: Record<string, string> = {
  url_invalida: "El enlace no parece ser de TikTok.",
  descarga_bloqueada:
    "No se pudo descargar el video: puede ser privado, estar bloqueado o yt-dlp necesita actualizarse.",
  transcripcion_vacia:
    "El audio no tiene voz reconocible. Prueba pegando el texto del video.",
  esquema_invalido:
    "El modelo no devolvió una receta válida. Reintenta o escríbela a mano.",
  cuota_agotada:
    "Se agotó la cuota del modelo gratuito. Espera un rato, cambia de proveedor o escribe la receta a mano.",
  no_es_receta: "El contenido no parece describir una receta de cocina.",
  error_interno:
    "Algo falló en el servidor. Revisa la consola del backend para ver el detalle.",
};

export default function ImportPage() {
  const [mode, setMode] = useState<"url" | "texto">("url");
  const [url, setUrl] = useState("");
  const [caption, setCaption] = useState("");
  const [transcript, setTranscript] = useState("");
  const [screenText, setScreenText] = useState("");
  const [author, setAuthor] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const jobId = job?.id;
  const jobStatus = job?.status;

  useEffect(() => {
    if (!jobId || (jobStatus !== "en_cola" && jobStatus !== "procesando")) {
      return;
    }

    let cancelled = false;
    const timer = window.setInterval(async () => {
      try {
        const updated = await api.getJob(jobId);
        if (!cancelled) setJob(updated);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "No se pudo consultar el estado del trabajo.",
          );
        }
      }
    }, 2000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [jobId, jobStatus]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (mode === "url" && !url.trim()) {
      setError("Pega el enlace del video de TikTok.");
      return;
    }
    if (
      mode === "texto" &&
      !caption.trim() &&
      !transcript.trim() &&
      !screenText.trim()
    ) {
      setError("Pega al menos el caption, la transcripción o el texto en pantalla.");
      return;
    }

    setSubmitting(true);
    try {
      const created = await api.createJob(
        mode === "url"
          ? { source_url: url.trim() }
          : {
              author: author.trim() || undefined,
              caption: caption.trim() || undefined,
              transcript: transcript.trim() || undefined,
              screen_text: screenText.trim() || undefined,
            },
      );
      setJob(created);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "No se pudo crear el trabajo.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRetry() {
    if (!job) return;
    setError(null);
    try {
      const updated = await api.retryJob(job.id);
      setJob(updated);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "No se pudo reintentar el trabajo.",
      );
    }
  }

  async function handleCancel() {
    if (!job) return;
    try {
      const updated = await api.cancelJob(job.id);
      setJob(updated);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "No se pudo cancelar el trabajo.",
      );
    }
  }

  function reset() {
    setJob(null);
    setError(null);
    setUrl("");
    setCaption("");
    setTranscript("");
    setScreenText("");
    setAuthor("");
  }

  const visibleStages =
    job?.kind === "texto"
      ? stages.filter(
          (s) =>
            s.key !== "descargando" &&
            s.key !== "transcribiendo" &&
            s.key !== "leyendo_pantalla",
        )
      : stages;
  const currentStage = job?.stage
    ? visibleStages.findIndex((stage) => stage.key === job.stage)
    : -1;
  const completed = job?.status === "lista" ? visibleStages.length : currentStage;

  return (
    <div className="fade-in space-y-6">
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
          Nueva página
        </p>
        <h1 className="mt-2 font-serif text-4xl text-paper">
          De un video a tu recetario
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-paper/65">
          Pega el enlace de TikTok y el recetario descarga el audio, lo
          transcribe y convierte la receta en una página editable. Si el video
          no tiene una receta, no se guarda nada.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
        <section>
          {!job ? (
            <div className="paper rounded-xl p-6 shadow-book sm:p-8">
              <div
                className="mb-6 inline-flex rounded-full border border-ink-soft/20 bg-paper-2 p-1"
                role="tablist"
                aria-label="Origen de la receta"
              >
                <button
                  type="button"
                  role="tab"
                  aria-selected={mode === "url"}
                  onClick={() => setMode("url")}
                  className={`rounded-full px-4 py-1.5 text-sm font-medium transition ${
                    mode === "url"
                      ? "bg-wine text-paper shadow"
                      : "text-ink-soft hover:text-ink"
                  }`}
                >
                  Desde un enlace
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={mode === "texto"}
                  onClick={() => setMode("texto")}
                  className={`rounded-full px-4 py-1.5 text-sm font-medium transition ${
                    mode === "texto"
                      ? "bg-wine text-paper shadow"
                      : "text-ink-soft hover:text-ink"
                  }`}
                >
                  Pegar texto
                </button>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                {mode === "url" ? (
                  <div>
                    <label className="field-label" htmlFor="tiktok-url">
                      Enlace de TikTok
                    </label>
                    <input
                      id="tiktok-url"
                      className="field font-mono text-sm"
                      value={url}
                      onChange={(event) => setUrl(event.target.value)}
                      placeholder="https://www.tiktok.com/@chef/video/…"
                      inputMode="url"
                      autoComplete="off"
                    />
                    <p className="mt-2 text-xs text-ink-soft/80">
                      También valen los enlaces cortos{" "}
                      <span className="font-mono">vm.tiktok.com/…</span>.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div>
                      <label className="field-label" htmlFor="caption">
                        Caption del video
                      </label>
                      <textarea
                        id="caption"
                        className="field min-h-20 resize-y text-sm"
                        value={caption}
                        onChange={(event) => setCaption(event.target.value)}
                        placeholder="El texto que escribió el autor…"
                      />
                    </div>
                    <div>
                      <label className="field-label" htmlFor="transcript">
                        Transcripción del audio
                      </label>
                      <textarea
                        id="transcript"
                        className="field min-h-28 resize-y text-sm"
                        value={transcript}
                        onChange={(event) => setTranscript(event.target.value)}
                        placeholder="Acepta líneas con marcas [0.0s-3.2s] o texto plano…"
                      />
                    </div>
                    <div>
                      <label className="field-label" htmlFor="screen">
                        Texto en pantalla
                      </label>
                      <textarea
                        id="screen"
                        className="field min-h-16 resize-y text-sm"
                        value={screenText}
                        onChange={(event) => setScreenText(event.target.value)}
                        placeholder="Una línea por frame, por ejemplo: 200 g de harina"
                      />
                    </div>
                    <div>
                      <label className="field-label" htmlFor="author">
                        Autor (opcional)
                      </label>
                      <input
                        id="author"
                        className="field text-sm"
                        value={author}
                        onChange={(event) => setAuthor(event.target.value)}
                        placeholder="@chef"
                      />
                    </div>
                  </div>
                )}

                {error ? (
                  <p
                    role="alert"
                    className="rounded-lg border border-wine/30 bg-wine/10 px-3 py-2 text-sm text-wine"
                  >
                    {error}
                  </p>
                ) : null}

                <button
                  type="submit"
                  disabled={submitting}
                  className="inline-flex items-center gap-2 rounded-full bg-wine px-6 py-2.5 text-sm font-semibold text-paper shadow-card transition hover:bg-wine-soft disabled:cursor-wait disabled:opacity-70"
                >
                  {submitting ? (
                    <SpinnerIcon width={17} height={17} />
                  ) : (
                    <ImportIcon width={17} height={17} />
                  )}
                  {submitting ? "Creando el trabajo…" : "Extraer la receta"}
                </button>
              </form>
            </div>
          ) : (
            <div className="paper page-in rounded-xl p-6 shadow-book sm:p-8">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ink-soft/15 pb-4">
                <div>
                  <p className="text-[0.62rem] font-semibold uppercase tracking-[0.24em] text-ink-soft/70">
                    Trabajo de ingesta
                  </p>
                  <h2 className="mt-1 font-serif text-2xl text-ink">
                    {job.status === "lista"
                      ? "La página está lista"
                      : job.status === "fallida"
                        ? "No se pudo completar"
                        : job.status === "cancelada"
                          ? "Trabajo cancelado"
                          : "Tu página se está escribiendo"}
                  </h2>
                </div>
                <StatusBadge status={job.status} />
              </div>

              {job.status === "lista" && job.recipe_id ? (
                <div className="mt-6 space-y-5">
                  <p className="flex items-start gap-2 text-sm leading-relaxed text-ink">
                    <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-sage/15 text-sage">
                      <CheckIcon width={15} height={15} />
                    </span>
                    La receta se guardó en tu recetario. Puede quedar marcada
                    como <strong>por revisar</strong> si faltaba algún dato.
                  </p>
                  <div className="flex flex-wrap gap-3">
                    <Link
                      href={`/recetas/${job.recipe_id}`}
                      className="inline-flex items-center gap-2 rounded-full bg-wine px-5 py-2.5 text-sm font-semibold text-paper transition hover:bg-wine-soft"
                    >
                      Abrir la receta
                    </Link>
                    <Link
                      href="/"
                      className="inline-flex items-center gap-2 rounded-full border border-ink-soft/30 px-5 py-2.5 text-sm font-medium text-ink transition hover:border-ink-soft/60"
                    >
                      Ver la estantería
                    </Link>
                  </div>
                </div>
              ) : job.status === "fallida" ? (
                <div className="mt-6 space-y-4">
                  <div className="rounded-lg border border-wine/25 bg-wine/5 p-4">
                    <p className="text-sm font-semibold text-wine">
                      {job.error_code
                        ? (errorText[job.error_code] ??
                          "Ocurrió un error inesperado.")
                        : "Ocurrió un error inesperado."}
                    </p>
                    {job.error_message ? (
                      <p className="mt-1 break-words text-xs text-ink-soft">
                        {job.error_message}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <button
                      type="button"
                      onClick={() => void handleRetry()}
                      className="rounded-full bg-wine px-5 py-2.5 text-sm font-semibold text-paper transition hover:bg-wine-soft"
                    >
                      Reintentar
                    </button>
                    <button
                      type="button"
                      onClick={reset}
                      className="rounded-full border border-ink-soft/30 px-5 py-2.5 text-sm font-medium text-ink transition hover:border-ink-soft/60"
                    >
                      Cambiar los datos
                    </button>
                  </div>
                </div>
              ) : job.status === "cancelada" ? (
                <div className="mt-6 space-y-4">
                  <p className="text-sm text-ink-soft">
                    Cancelaste este trabajo. No se guardó ninguna receta.
                  </p>
                  <div className="flex flex-wrap gap-3">
                    <button
                      type="button"
                      onClick={() => void handleRetry()}
                      className="rounded-full bg-wine px-5 py-2.5 text-sm font-semibold text-paper transition hover:bg-wine-soft"
                    >
                      Volver a intentar
                    </button>
                    <button
                      type="button"
                      onClick={reset}
                      className="rounded-full border border-ink-soft/30 px-5 py-2.5 text-sm font-medium text-ink transition hover:border-ink-soft/60"
                    >
                      Nuevo trabajo
                    </button>
                  </div>
                </div>
              ) : (
                <div className="mt-6 space-y-5">
                  <p className="flex items-center gap-2 text-sm text-ink-soft">
                    <SpinnerIcon width={16} height={16} className="text-gold" />
                    {job.status === "en_cola"
                      ? "Esperando turno…"
                      : "Trabajando en tu receta…"}
                  </p>

                  <ol className="space-y-4">
                    {visibleStages.map((stage, index) => {
                      const done = index < completed;
                      const active = index === currentStage;
                      return (
                        <li key={stage.key} className="flex gap-3">
                          <span
                            aria-hidden
                            className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[0.68rem] font-semibold ${
                              done
                                ? "border-sage bg-sage text-paper"
                                : active
                                  ? "border-gold bg-gold/20 text-gold"
                                  : "border-ink-soft/25 text-ink-soft/50"
                            }`}
                          >
                            {done ? <CheckIcon width={13} height={13} /> : index + 1}
                          </span>
                          <div>
                            <p
                              className={`text-sm font-medium ${
                                active
                                  ? "text-ink"
                                  : done
                                    ? "text-ink-soft"
                                    : "text-ink-soft/60"
                              }`}
                            >
                              {stage.label}
                              {active ? (
                                <span className="ml-2 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-gold" />
                              ) : null}
                            </p>
                            <p className="text-xs text-ink-soft/70">
                              {stage.hint}
                            </p>
                          </div>
                        </li>
                      );
                    })}
                  </ol>

                  <div className="flex flex-wrap items-center gap-3 border-t border-ink-soft/15 pt-4">
                    <button
                      type="button"
                      onClick={() => void handleCancel()}
                      className="rounded-full border border-ink-soft/30 px-4 py-2 text-sm font-medium text-ink transition hover:border-wine/50 hover:text-wine"
                    >
                      Cancelar
                    </button>
                    <span className="text-[0.68rem] text-ink-soft/60">
                      Se actualiza cada 2 s · id {job.id.slice(0, 8)}…
                    </span>
                  </div>
                </div>
              )}

              {job.events.length > 0 ? (
                <details className="mt-6 rounded-lg border border-ink-soft/15 bg-paper-2/60 p-4">
                  <summary className="cursor-pointer text-sm font-medium text-ink">
                    Qué hizo el agente
                    <span className="ml-2 text-xs font-normal text-ink-soft">
                      {job.events.filter((event) => event.tool !== "decision").length}{" "}
                      llamadas · ${job.cost_usd.toFixed(4)}
                    </span>
                  </summary>
                  <ol className="mt-3 space-y-2">
                    {job.events.map((event, index) => (
                      <li
                        key={`${event.tool}-${index}`}
                        className="border-l-2 border-ink-soft/20 pl-3 text-xs text-ink-soft"
                      >
                        <p className="font-medium text-ink">
                          {toolLabels[event.tool] ?? event.tool}
                          {event.tool !== "decision" ? (
                            <span className="ml-2 font-normal text-ink-soft/70">
                              {event.duration_ms ?? 0} ms
                            </span>
                          ) : null}
                          {!event.ok ? (
                            <span className="ml-2 font-normal text-wine">
                              falló
                            </span>
                          ) : null}
                        </p>
                        <p className="mt-0.5 break-words">
                          {event.text}
                          {event.error ? ` · ${event.error}` : ""}
                        </p>
                      </li>
                    ))}
                  </ol>
                </details>
              ) : null}

              {error ? (
                <p
                  role="alert"
                  className="mt-4 rounded-lg border border-wine/30 bg-wine/10 px-3 py-2 text-sm text-wine"
                >
                  {error}
                </p>
              ) : null}
            </div>
          )}
        </section>

        <aside className="space-y-4">
          <div className="rounded-xl border border-white/10 bg-white/[0.03] p-5">
            <h2 className="font-serif text-lg text-paper">Qué ocurre al pulsar</h2>
            <ol className="mt-3 space-y-2 text-sm text-paper/60">
              <li>1. Se descarga solo el audio del video.</li>
              <li>2. Se transcribe en tu equipo con faster-whisper.</li>
              <li>3. El modelo une caption, audio y texto en pantalla.</li>
              <li>4. La receta se valida y se guarda con su fuente.</li>
              <li>5. El video temporal se borra al terminar.</li>
            </ol>
          </div>

          <div className="rounded-xl border border-gold/20 bg-gold/5 p-5 text-sm leading-relaxed text-paper/60">
            <p className="font-medium text-gold-soft">Si algo falla</p>
            <p className="mt-2">
              El modelo gratuito de OpenCode tiene cuota diaria. Si se agota,
              el trabajo queda como <em>fallido</em> con el código{" "}
              <span className="font-mono text-xs">cuota_agotada</span> y puedes
              reintentarlo más tarde.
            </p>
            <p className="mt-2">
              También puedes pegar el texto del video o escribir la receta a
              mano.
            </p>
          </div>

          <Link
            href="/nueva"
            className="block rounded-xl border border-white/10 bg-white/[0.03] p-5 text-sm text-paper/70 transition hover:border-gold/30 hover:text-paper"
          >
            <span className="font-medium text-paper">¿Sin video?</span>
            <span className="mt-1 block">
              Escribe la receta desde cero en una página en blanco.
            </span>
          </Link>
        </aside>
      </div>
    </div>
  );
}
