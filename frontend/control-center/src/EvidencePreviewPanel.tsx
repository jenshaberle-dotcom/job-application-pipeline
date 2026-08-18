import { useEffect, useMemo, useState } from "react";
import "./evidence-preview.css";

type Job = {
  silver_job_id: number;
  title?: string | null;
  company_name?: string | null;
  product_readiness_status?: string | null;
};

type ProductPayload = {
  job_readiness?: Job[];
};

type PreviewPayload = {
  status: string;
  target?: {
    silver_job_id: number;
    title?: string | null;
    company_name?: string | null;
    final_url?: string | null;
    product_readiness_status?: string | null;
  };
  assessment?: {
    employment_type?: string;
    required_languages?: string[];
    weekly_hours_min?: number | null;
    weekly_hours_max?: number | null;
    work_model?: string;
    requirements_seniority?: string;
    unresolved_fields?: string[];
  };
  ranking?: {
    profile_direction_score?: number;
    data_focus_score?: number;
    reliability_focus_score?: number;
    evidence_quality_score?: number;
    uncertainties?: string[];
  };
  capability_fit_review?: {
    status?: string;
    evidence_status?: string;
    review_required?: boolean;
    reason?: string;
    auto_pass_from_tag_overlap?: boolean;
  };
  delta?: Record<string, { stored: unknown; preview: unknown }>;
  boundaries?: Record<string, unknown>;
  reason?: string;
};

const humanize = (value: string | undefined | null) =>
  (value || "unknown").replaceAll("_", " ");

const hoursLabel = (minimum?: number | null, maximum?: number | null) => {
  if (minimum == null && maximum == null) return "unknown";
  if (minimum === maximum) return `${minimum} h/week`;
  return `${minimum ?? "?"}-${maximum ?? "?"} h/week`;
};

export default function EvidencePreviewPanel() {
  const [open, setOpen] = useState(false);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [preview, setPreview] = useState<PreviewPayload | null>(null);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || jobs.length > 0 || loadingJobs) return;
    let cancelled = false;
    setLoadingJobs(true);
    setError(null);
    fetch("/api/v1/product-v1", { headers: { Accept: "application/json" } })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Product V1 API returned ${response.status}`);
        return (await response.json()) as ProductPayload;
      })
      .then((payload) => {
        if (cancelled) return;
        const loaded = [...(payload.job_readiness || [])].sort(
          (left, right) => left.silver_job_id - right.silver_job_id
        );
        setJobs(loaded);
        if (loaded.length > 0) setSelectedId(loaded[0].silver_job_id);
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason));
      })
      .finally(() => {
        if (!cancelled) setLoadingJobs(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, jobs.length, loadingJobs]);

  const selected = useMemo(
    () => jobs.find((job) => job.silver_job_id === selectedId) || null,
    [jobs, selectedId]
  );

  const runPreview = async () => {
    if (selectedId == null) return;
    setLoadingPreview(true);
    setPreview(null);
    setError(null);
    try {
      const response = await fetch(
        `/api/v1/product-v1/evidence-preview?silver_job_id=${encodeURIComponent(selectedId)}`,
        { headers: { Accept: "application/json" } }
      );
      const payload = (await response.json()) as PreviewPayload;
      if (!response.ok) throw new Error(payload.reason || `Evidence preview returned ${response.status}`);
      setPreview(payload);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setLoadingPreview(false);
    }
  };

  const deltaCount = Object.keys(preview?.delta || {}).length;

  return (
    <div className={`evidence-preview-shell ${open ? "is-open" : ""}`}>
      <button
        className="evidence-preview-toggle"
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        <span>Evidence preview</span>
        <small>provider-free</small>
      </button>

      {open && (
        <section className="evidence-preview-panel" aria-label="Downstream evidence preview">
          <header>
            <div>
              <p className="eyebrow">Execution wiring</p>
              <h2>Assessment → Ranking preview</h2>
              <p>
                Fetches the validated employer-origin detail and runs deterministic downstream evidence only.
              </p>
            </div>
            <button className="preview-close" type="button" onClick={() => setOpen(false)}>
              Close
            </button>
          </header>

          <div className="preview-controls">
            <label>
              <span>Silver job</span>
              <select
                value={selectedId ?? ""}
                disabled={loadingJobs || jobs.length === 0}
                onChange={(event) => {
                  setSelectedId(Number(event.target.value));
                  setPreview(null);
                  setError(null);
                }}
              >
                {jobs.map((job) => (
                  <option key={job.silver_job_id} value={job.silver_job_id}>
                    #{job.silver_job_id} · {job.title || "Untitled"} · {job.company_name || "Unknown company"}
                  </option>
                ))}
              </select>
            </label>
            <button type="button" onClick={runPreview} disabled={selectedId == null || loadingPreview}>
              {loadingPreview ? "Previewing…" : "Run evidence preview"}
            </button>
          </div>

          {selected && (
            <div className="preview-selected">
              <strong>{selected.title || "Untitled"}</strong>
              <span>{selected.company_name || "Unknown company"}</span>
              <code>{humanize(selected.product_readiness_status)}</code>
            </div>
          )}

          {loadingJobs && <p className="preview-message">Loading current Silver/readiness jobs…</p>}
          {error && <p className="preview-message preview-error">{error}</p>}

          {preview?.status === "preview_ready" && preview.assessment && preview.ranking && (
            <div className="preview-results">
              <div className="preview-boundary">
                <strong>Read-only evidence</strong>
                <span>0 provider calls · 0 DB writes · 0 rank/Top-5 authority</span>
              </div>

              <div className="preview-grid">
                <article>
                  <p className="eyebrow">Assessment</p>
                  <dl>
                    <div><dt>Employment</dt><dd>{humanize(preview.assessment.employment_type)}</dd></div>
                    <div><dt>Languages</dt><dd>{preview.assessment.required_languages?.join(", ") || "unknown"}</dd></div>
                    <div><dt>Hours</dt><dd>{hoursLabel(preview.assessment.weekly_hours_min, preview.assessment.weekly_hours_max)}</dd></div>
                    <div><dt>Work model</dt><dd>{humanize(preview.assessment.work_model)}</dd></div>
                    <div><dt>Seniority evidence</dt><dd>{humanize(preview.assessment.requirements_seniority)}</dd></div>
                  </dl>
                  <p className="preview-footnote">
                    Open: {preview.assessment.unresolved_fields?.map(humanize).join(", ") || "none"}
                  </p>
                </article>

                <article>
                  <p className="eyebrow">Ranking evidence</p>
                  <dl>
                    <div><dt>Profile direction</dt><dd>{preview.ranking.profile_direction_score ?? 0}</dd></div>
                    <div><dt>Data focus</dt><dd>{preview.ranking.data_focus_score ?? 0}</dd></div>
                    <div><dt>Reliability focus</dt><dd>{preview.ranking.reliability_focus_score ?? 0}</dd></div>
                    <div><dt>Evidence quality</dt><dd>{preview.ranking.evidence_quality_score ?? 0}</dd></div>
                  </dl>
                  <p className="preview-footnote">
                    Uncertainties: {preview.ranking.uncertainties?.map(humanize).join(", ") || "none"}
                  </p>
                </article>
              </div>

              <article className={`capability-review ${preview.capability_fit_review?.review_required ? "needs-review" : "has-evidence"}`}>
                <div>
                  <p className="eyebrow">Capability-fit authority</p>
                  <h3>{preview.capability_fit_review?.review_required ? "Review still required" : "Existing evidence present"}</h3>
                  <p>{humanize(preview.capability_fit_review?.reason)}</p>
                </div>
                <div className="capability-meta">
                  <span>Status: {humanize(preview.capability_fit_review?.status)}</span>
                  <span>Evidence: {humanize(preview.capability_fit_review?.evidence_status)}</span>
                  <span>Auto-pass from tag overlap: never</span>
                </div>
              </article>

              <div className="preview-delta">
                <strong>{deltaCount} deterministic delta{deltaCount === 1 ? "" : "s"}</strong>
                <span>Preview only — nothing has been persisted.</span>
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
