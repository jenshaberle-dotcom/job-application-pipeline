import { useEffect, useMemo, useState } from "react";

type Pillar = {
  id: string;
  title: string;
  status: string;
  summary: string;
};

type OperatorBlocker = {
  code: string;
  title: string;
  detail: string;
};

type WaveState = {
  search_term: string;
  is_not_exclusion_enabled: boolean;
  current_exclusion_wave_index: number;
  current_interval_days: number;
  next_due_at?: string | null;
  last_new_company_count?: number | null;
  last_quality_score?: number | null;
};

type Job = {
  silver_job_id: number;
  product_rank?: number;
  title?: string | null;
  company_name?: string | null;
  city?: string | null;
  publication_date?: string | null;
  source_url?: string | null;
  product_readiness_status?: string;
  overall_quality_score?: number | null;
  profile_direction_score?: number | null;
  data_focus_score?: number | null;
  reliability_focus_score?: number | null;
  evidence_quality_score?: number | null;
  work_model?: string;
  commute_minutes?: number | null;
  explanations?: string[];
  uncertainties?: string[];
};

type ProductPayload = {
  schema_version: string;
  product: {
    name: string;
    character: string;
    target_profile: string;
  };
  pillars: Pillar[];
  summary: {
    wave_term_count: number;
    observed_job_count: number;
    rankable_job_count: number;
    origin_blocker_count: number;
    top_job_count: number;
    application_ready_count: number;
  };
  wave_states: WaveState[];
  ranking_policy: Record<string, unknown>;
  job_readiness: Job[];
  top_jobs: Job[];
  application_readiness: Array<Record<string, unknown>>;
  application_sources_ready: {
    base_cv: boolean;
    base_application_letter: boolean;
  };
  operator_blockers: OperatorBlocker[];
  boundaries: Record<string, boolean>;
};

type Tab = "overview" | "waves" | "top-jobs" | "applications";

const label = (value: string | undefined) =>
  (value || "unknown").replaceAll("_", " ");

function StatusPill({ value }: { value: string }) {
  const tone = value.includes("available") || value.includes("ready") || value === "approved"
    ? "ok"
    : value.includes("required") || value.includes("waiting")
      ? "warn"
      : "neutral";
  return <span className={`status-pill ${tone}`}>{label(value)}</span>;
}

function Metric({ labelText, value, helper }: { labelText: string; value: number; helper: string }) {
  return (
    <article className="metric-card">
      <span>{labelText}</span>
      <strong>{value}</strong>
      <small>{helper}</small>
    </article>
  );
}

function JobCard({ job, ranked }: { job: Job; ranked?: boolean }) {
  return (
    <article className="job-card">
      <header>
        <div>
          <span className="eyebrow">{ranked ? `Rank ${job.product_rank}` : label(job.product_readiness_status)}</span>
          <h3>{job.title || "Untitled job"}</h3>
          <p>{job.company_name || "Unknown employer"} · {job.city || "Location not confirmed"}</p>
        </div>
        {job.overall_quality_score != null && <strong className="score">{job.overall_quality_score}</strong>}
      </header>
      <div className="signal-grid">
        <span>ML direction <b>{job.profile_direction_score ?? "–"}</b></span>
        <span>Data focus <b>{job.data_focus_score ?? "–"}</b></span>
        <span>Reliability <b>{job.reliability_focus_score ?? "–"}</b></span>
        <span>Evidence <b>{job.evidence_quality_score ?? "–"}</b></span>
        <span>Model <b>{label(job.work_model)}</b></span>
        <span>Commute <b>{job.commute_minutes == null ? "unknown" : `${job.commute_minutes} min`}</b></span>
      </div>
      {(job.explanations?.length || job.uncertainties?.length) ? (
        <div className="evidence-panel">
          {job.explanations?.map((item) => <p key={item}>✓ {item}</p>)}
          {job.uncertainties?.map((item) => <p className="uncertain" key={item}>? {item}</p>)}
        </div>
      ) : null}
      {job.source_url && <a href={job.source_url} target="_blank" rel="noreferrer">Open origin evidence</a>}
    </article>
  );
}

export default function App() {
  const [payload, setPayload] = useState<ProductPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("overview");

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/v1/product-v1", { signal: controller.signal, headers: { Accept: "application/json" } })
      .then(async (response) => {
        if (!response.ok) throw new Error(`API returned ${response.status}`);
        return response.json() as Promise<ProductPayload>;
      })
      .then(setPayload)
      .catch((reason: unknown) => {
        if ((reason as Error).name !== "AbortError") setError(String(reason));
      });
    return () => controller.abort();
  }, []);

  const readinessPreview = useMemo(
    () => payload?.job_readiness.slice(0, 12) || [],
    [payload]
  );

  if (error) {
    return <main className="fatal"><h1>Control Center unavailable</h1><pre>{error}</pre></main>;
  }
  if (!payload) {
    return <main className="loading"><div className="sonar" /><p>Reading Deep Ocean product state…</p></main>;
  }

  return (
    <div className="app-shell">
      <aside>
        <div className="brand-mark"><span>DO</span></div>
        <div className="brand-copy">
          <span className="eyebrow">Deep Ocean Intelligence</span>
          <h1>Job Pipeline</h1>
          <p>{payload.product.target_profile}</p>
        </div>
        <nav>
          {([
            ["overview", "Overview"],
            ["waves", "StepStone Waves"],
            ["top-jobs", "Top 5"],
            ["applications", "Applications"]
          ] as Array<[Tab, string]>).map(([id, text]) => (
            <button className={tab === id ? "active" : ""} key={id} onClick={() => setTab(id)}>{text}</button>
          ))}
        </nav>
        <div className="boundary-card">
          <strong>Read-only surface</strong>
          <span>No provider call</span>
          <span>No auto-apply</span>
          <span>No source activation</span>
        </div>
      </aside>

      <main>
        <header className="page-header">
          <div>
            <span className="eyebrow">Intent locked · implementation adaptive</span>
            <h2>{tab === "overview" ? "Product V1 command surface" : label(tab)}</h2>
          </div>
          <span className="live-indicator"><i /> repository & DB truth</span>
        </header>

        {payload.operator_blockers.length > 0 && (
          <section className="operator-gate">
            <header><span className="eyebrow">Operator gate</span><h3>Decisions or source documents required</h3></header>
            <div className="blocker-grid">
              {payload.operator_blockers.map((blocker) => (
                <article key={blocker.code}><strong>{blocker.title}</strong><p>{blocker.detail}</p><code>{blocker.code}</code></article>
              ))}
            </div>
          </section>
        )}

        {tab === "overview" && (
          <>
            <section className="metrics">
              <Metric labelText="Wave terms" value={payload.summary.wave_term_count} helper="bounded StepStone search spaces" />
              <Metric labelText="Observed jobs" value={payload.summary.observed_job_count} helper="Silver jobs in Product V1 view" />
              <Metric labelText="Rankable" value={payload.summary.rankable_job_count} helper="origin + activity + hard gates passed" />
              <Metric labelText="Top jobs" value={payload.summary.top_job_count} helper="only after approved ranking policy" />
            </section>
            <section className="pillar-grid">
              {payload.pillars.map((pillar, index) => (
                <article className="pillar-card" key={pillar.id}>
                  <span className="pillar-index">0{index + 1}</span>
                  <StatusPill value={pillar.status} />
                  <h3>{pillar.title}</h3>
                  <p>{pillar.summary}</p>
                </article>
              ))}
            </section>
          </>
        )}

        {tab === "waves" && (
          <section className="content-panel">
            <header><span className="eyebrow">Conservative aggregator sensing</span><h3>StepStone company-discovery waves</h3><p>Stable terms, temporary company cooldowns, one bounded page and persisted wave rotation.</p></header>
            <div className="wave-grid">
              {payload.wave_states.map((wave) => (
                <article key={wave.search_term}>
                  <div className="wave-ring"><strong>{wave.current_exclusion_wave_index}</strong><span>wave</span></div>
                  <div><h4>{wave.search_term}</h4><StatusPill value={wave.is_not_exclusion_enabled ? "wave_enabled" : "baseline_only"} /><p>{wave.current_interval_days} day interval · {wave.last_new_company_count ?? 0} new companies last cycle</p></div>
                </article>
              ))}
              {payload.wave_states.length === 0 && <p className="empty">No DB-backed wave state is available yet.</p>}
            </div>
          </section>
        )}

        {tab === "top-jobs" && (
          <section className="content-panel">
            <header><span className="eyebrow">Origin validated · explainable</span><h3>Top-5 job review</h3><p>Authoritative ranks stay empty until the operator-owned ranking policy is approved.</p></header>
            <div className="job-grid">
              {(payload.top_jobs.length ? payload.top_jobs : readinessPreview).map((item) => <JobCard job={item} ranked={payload.top_jobs.length > 0} key={item.silver_job_id} />)}
              {!payload.top_jobs.length && !readinessPreview.length && <p className="empty">No Product V1 job assessments are available.</p>}
            </div>
          </section>
        )}

        {tab === "applications" && (
          <section className="content-panel">
            <header><span className="eyebrow">Source grounded · review first</span><h3>CV & application-letter assistant</h3><p>The assistant prepares evidence-bound draft packages. It never invents experience and never submits an application.</p></header>
            <div className="source-grid">
              <article className={payload.application_sources_ready.base_cv ? "ready" : "blocked"}><span>CV</span><strong>{payload.application_sources_ready.base_cv ? "Approved source ready" : "Base CV required"}</strong></article>
              <article className={payload.application_sources_ready.base_application_letter ? "ready" : "blocked"}><span>Letter</span><strong>{payload.application_sources_ready.base_application_letter ? "Approved source ready" : "Base letter required"}</strong></article>
              <article><span>Ready jobs</span><strong>{payload.summary.application_ready_count}</strong></article>
            </div>
            <div className="safety-copy">
              <h4>Generation boundary</h4>
              <p>Only approved source documents, verified job evidence and explicitly registered facts may enter a draft manifest. Provider execution remains a separate operator-controlled action.</p>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
