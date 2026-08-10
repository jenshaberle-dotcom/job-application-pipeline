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
  lifecycle_status?: string;
  last_positive_observed_at?: string | null;
  last_health_checked_at?: string | null;
  lifecycle_evidence_reason?: string | null;
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

type GateState = {
  status: string;
  decision?: string | null;
  passed: boolean;
  truth_source: string;
};

type SourceConnector = {
  source_name: string;
  source_label: string;
  source_type: string;
  candidate_status: string;
  connector: {
    implemented: boolean;
    implementation_status: string;
    implementation_truth_source: string;
    code_backed_registered: boolean;
    registration_status: string;
    connector_class?: string | null;
    registration_error?: string | null;
  };
  gates: {
    connector_validation_gate: GateState;
    final_approval_gate: GateState;
  };
  activation: {
    status: string;
    active: boolean | null;
    truth_source: string;
  };
  search_profiles: {
    status: string;
    profile_count: number;
    active_profile_count: number;
    active_search_term_count: number;
    truth_source: string;
  };
  last_ingestion: {
    status: string;
    started_at?: string | null;
    finished_at?: string | null;
    total_loaded: number;
    inserted_count: number;
    error_message?: string | null;
    truth_source: string;
  };
  layers: {
    status: string;
    bronze_present: boolean | null;
    bronze_count: number;
    silver_present: boolean | null;
    silver_count: number;
    truth_source: string;
  };
  lifecycle: {
    implementation: string;
    validation: string;
    final_approval: string;
    registration: string;
    activation: string;
    ingestion: string;
  };
  inconsistencies: string[];
  current_blocker?: string | null;
  next_action: string;
};

type SourceConnectorOverview = {
  schema_version: string;
  summary: {
    source_count: number;
    implemented_count: number;
    validated_count: number;
    final_approved_count: number;
    registered_count: number;
    active_count: number;
    ingested_count: number;
    attention_count: number;
  };
  sources: SourceConnector[];
  boundaries: Record<string, boolean>;
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
    current_active_job_count: number;
    stale_job_count: number;
    inactive_confirmed_job_count: number;
    unverifiable_job_count: number;
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
  source_connector_overview: SourceConnectorOverview;
  operator_blockers: OperatorBlocker[];
  boundaries: Record<string, boolean>;
};

type Tab = "overview" | "sources" | "waves" | "top-jobs" | "applications";
type SourceFilter = "all" | "attention" | "active" | "not-activated";

const label = (value: string | undefined) =>
  (value || "unknown").replaceAll("_", " ");

const statusTone = (value: string) => {
  const normalized = value.toLowerCase();
  if (
    normalized.includes("inconsistent") ||
    normalized.includes("error") ||
    normalized.includes("failed") ||
    normalized.includes("blocked") ||
    normalized === "inactive_confirmed"
  ) return "bad";
  if (
    normalized === "passed" ||
    normalized === "approved" ||
    normalized === "registered" ||
    normalized === "implemented" ||
    normalized === "active" ||
    normalized === "active_confirmed" ||
    normalized === "ingested" ||
    normalized.includes("available") ||
    normalized.includes("ready") ||
    normalized.includes("present") ||
    normalized === "success"
  ) return "ok";
  if (
    normalized.includes("required") ||
    normalized.includes("waiting") ||
    normalized.includes("unknown") ||
    normalized.includes("stale") ||
    normalized.includes("unverifiable") ||
    normalized.includes("not ") ||
    normalized.includes("not_") ||
    normalized.includes("inactive") ||
    normalized.includes("pending") ||
    normalized.includes("no ingestion")
  ) return "warn";
  return "neutral";
};

function StatusPill({ value }: { value: string }) {
  return <span className={`status-pill ${statusTone(value)}`}>{label(value)}</span>;
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
      {job.lifecycle_status && <StatusPill value={job.lifecycle_status} />}
      <div className="signal-grid">
        <span>ML direction <b>{job.profile_direction_score ?? "–"}</b></span>
        <span>Data focus <b>{job.data_focus_score ?? "–"}</b></span>
        <span>Reliability <b>{job.reliability_focus_score ?? "–"}</b></span>
        <span>Evidence <b>{job.evidence_quality_score ?? "–"}</b></span>
        <span>Model <b>{label(job.work_model)}</b></span>
        <span>Commute <b>{job.commute_minutes == null ? "unknown" : `${job.commute_minutes} min`}</b></span>
        <span>Last health <b>{job.last_health_checked_at || "not checked"}</b></span>
        <span>Last positive <b>{job.last_positive_observed_at || "not observed"}</b></span>
        <span>Health reason <b>{label(job.lifecycle_evidence_reason || undefined)}</b></span>
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

const lifecycleLabels: Array<[keyof SourceConnector["lifecycle"], string]> = [
  ["implementation", "Implemented"],
  ["validation", "Validated"],
  ["final_approval", "Approved"],
  ["registration", "Registered"],
  ["activation", "Activated"],
  ["ingestion", "Ingested"]
];

function SourceConnectorCard({ source }: { source: SourceConnector }) {
  return (
    <article className={`source-card ${source.inconsistencies.length ? "has-inconsistency" : ""}`}>
      <header>
        <div>
          <code>{source.source_name}</code>
          <h4>{source.source_label}</h4>
          <p>{label(source.source_type)} · {source.connector.connector_class || "connector class unknown"}</p>
        </div>
        <StatusPill value={source.current_blocker ? "attention_required" : "truth_available"} />
      </header>

      <div className="lifecycle-rail" aria-label={`${source.source_name} lifecycle`}>
        {lifecycleLabels.map(([key, text]) => (
          <div className={`lifecycle-step ${statusTone(source.lifecycle[key])}`} key={key}>
            <i />
            <span>{text}</span>
            <small>{label(source.lifecycle[key])}</small>
          </div>
        ))}
      </div>

      <div className="source-facts">
        <span>Search profiles <b>{label(source.search_profiles.status)} ({source.search_profiles.active_profile_count}/{source.search_profiles.profile_count})</b></span>
        <span>Last ingestion <b>{label(source.last_ingestion.status)}</b></span>
        <span>Bronze <b>{source.layers.bronze_count}</b></span>
        <span>Silver <b>{source.layers.silver_count}</b></span>
      </div>

      <div className="next-action-panel">
        <span className="eyebrow">Current blocker / next safe action</span>
        <strong>{source.current_blocker ? label(source.current_blocker) : "No current blocker"}</strong>
        <p>{source.next_action}</p>
      </div>

      <details>
        <summary>Truth provenance</summary>
        <p>Implementation and registration: {label(source.connector.implementation_truth_source)}.</p>
        <p>Validation and approval: employer-origin gate reviews.</p>
        <p>Activation: {source.activation.truth_source}; ingestion: {source.last_ingestion.truth_source}; layers: {source.layers.truth_source}.</p>
        {source.inconsistencies.length > 0 && <p className="inconsistency-copy">Detected: {source.inconsistencies.map(label).join(", ")}</p>}
      </details>
    </article>
  );
}

export default function App() {
  const [payload, setPayload] = useState<ProductPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("all");

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

  const filteredSources = useMemo(() => {
    const sources = payload?.source_connector_overview.sources || [];
    if (sourceFilter === "attention") return sources.filter((source) => Boolean(source.current_blocker));
    if (sourceFilter === "active") return sources.filter((source) => source.activation.active === true);
    if (sourceFilter === "not-activated") return sources.filter((source) => source.activation.active === false);
    return sources;
  }, [payload, sourceFilter]);

  if (error) {
    return <main className="fatal"><h1>Control Center unavailable</h1><pre>{error}</pre></main>;
  }
  if (!payload) {
    return <main className="loading"><div className="sonar" /><p>Reading Deep Ocean product state…</p></main>;
  }

  const tabTitle: Record<Tab, string> = {
    overview: "Product V1 command surface",
    sources: "Source & Connector Overview",
    waves: "StepStone Waves",
    "top-jobs": "Top Jobs",
    applications: "Applications"
  };
  const sourceOverview = payload.source_connector_overview;

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
            ["sources", "Sources & Connectors"],
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
          <span>Lifecycle-gated Top 5</span>
        </div>
      </aside>

      <main>
        <header className="page-header">
          <div>
            <span className="eyebrow">Intent locked · implementation adaptive</span>
            <h2>{tabTitle[tab]}</h2>
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
              <Metric labelText="Observed jobs" value={payload.summary.observed_job_count} helper="historical Silver inventory" />
              <Metric labelText="Current active" value={payload.summary.current_active_job_count} helper="explicit lifecycle-confirmed vacancies" />
              <Metric labelText="Needs refresh" value={payload.summary.stale_job_count + payload.summary.unverifiable_job_count} helper="not safe for current Top 5" />
              <Metric labelText="Rankable" value={payload.summary.rankable_job_count} helper="lifecycle + origin + hard gates passed" />
              <Metric labelText="Registered sources" value={sourceOverview.summary.registered_count} helper="registration is not activation" />
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

        {tab === "sources" && (
          <section className="content-panel source-overview-panel">
            <header>
              <span className="eyebrow">Separate lifecycle truths · no optimistic defaults</span>
              <h3>Sources and code-backed connectors</h3>
              <p>Implementation, validation, final approval, registration, activation and ingestion are reported independently from runtime registry and database evidence.</p>
            </header>
            <section className="source-metrics">
              <Metric labelText="Known sources" value={sourceOverview.summary.source_count} helper="registry or DB-backed identity" />
              <Metric labelText="Validated" value={sourceOverview.summary.validated_count} helper="connector validation passed" />
              <Metric labelText="Active" value={sourceOverview.summary.active_count} helper="active search profile present" />
              <Metric labelText="Ingested" value={sourceOverview.summary.ingested_count} helper="Bronze or Silver rows present" />
              <Metric labelText="Needs attention" value={sourceOverview.summary.attention_count} helper="blocker or next bounded action" />
            </section>
            <div className="source-filter" aria-label="Filter source overview">
              {([
                ["all", "All"],
                ["attention", "Needs attention"],
                ["active", "Active"],
                ["not-activated", "Not activated"]
              ] as Array<[SourceFilter, string]>).map(([id, text]) => (
                <button className={sourceFilter === id ? "active" : ""} key={id} onClick={() => setSourceFilter(id)}>{text}</button>
              ))}
            </div>
            <div className="source-card-grid">
              {filteredSources.map((source) => <SourceConnectorCard source={source} key={source.source_name} />)}
              {filteredSources.length === 0 && <p className="empty">No source matches this filter.</p>}
            </div>
          </section>
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
            <header><span className="eyebrow">Lifecycle confirmed · origin validated · explainable</span><h3>Top-5 job review</h3><p>Historical Silver presence alone never qualifies a vacancy. Current lifecycle evidence is required before ranking.</p></header>
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
