import { useEffect, useMemo, useState, type CSSProperties } from "react";
import FinalApprovalReviewDialog from "./FinalApprovalReviewDialog";

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
  candidate_id: number | null;
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

type Tab = "overview" | "candidates" | "approvals" | "operations";
type CandidateFilter = "all" | "attention" | "active" | "ingested";

const label = (value: string | undefined | null) =>
  (value || "unknown").replaceAll("_", " ");

const normalize = (value: string | undefined | null) =>
  (value || "").trim().toLocaleLowerCase();

const statusTone = (value: string | undefined | null) => {
  const normalized = normalize(value);
  if (
    normalized.includes("inconsistent") ||
    normalized.includes("error") ||
    normalized.includes("failed") ||
    normalized.includes("blocked") ||
    normalized === "inactive confirmed"
  ) return "bad";
  if (
    normalized === "passed" ||
    normalized === "approved" ||
    normalized === "registered" ||
    normalized === "implemented" ||
    normalized === "active" ||
    normalized === "active confirmed" ||
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
    normalized.includes("inactive") ||
    normalized.includes("pending") ||
    normalized.includes("attention") ||
    normalized.includes("no ingestion")
  ) return "warn";
  return "neutral";
};

async function readProductTruth(signal?: AbortSignal): Promise<ProductPayload> {
  const response = await fetch("/api/v1/product-v1", {
    ...(signal ? { signal } : {}),
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`API returned ${response.status}`);
  return response.json() as Promise<ProductPayload>;
}

function StatusPill({ value }: { value: string }) {
  return <span className={`status-pill ${statusTone(value)}`}>{label(value)}</span>;
}

function Metric({
  labelText,
  value,
  helper,
  tone = "cyan",
}: {
  labelText: string;
  value: number;
  helper: string;
  tone?: "cyan" | "green" | "amber" | "violet";
}) {
  return (
    <article className={`metric-card tone-${tone}`}>
      <span>{labelText}</span>
      <strong>{value}</strong>
      <small>{helper}</small>
    </article>
  );
}

const lifecycleLabels: Array<[keyof SourceConnector["lifecycle"], string]> = [
  ["implementation", "Implemented"],
  ["validation", "Validated"],
  ["final_approval", "Approved"],
  ["registration", "Registered"],
  ["activation", "Activated"],
  ["ingestion", "Ingested"],
];

const sourceLifecycleStages = (
  summary: SourceConnectorOverview["summary"]
): Array<{ key: string; label: string; value: number; helper: string }> => [
  { key: "known", label: "Known", value: summary.source_count, helper: "DB / registry identity" },
  { key: "implemented", label: "Implemented", value: summary.implemented_count, helper: "code-backed connector" },
  { key: "validated", label: "Validated", value: summary.validated_count, helper: "validation gate passed" },
  { key: "approved", label: "Final approved", value: summary.final_approved_count, helper: "reviewed gate truth" },
  { key: "registered", label: "Registered", value: summary.registered_count, helper: "registry truth" },
  { key: "active", label: "Active", value: summary.active_count, helper: "active profile truth" },
  { key: "ingested", label: "Ingested", value: summary.ingested_count, helper: "Bronze / Silver present" },
];

function lifecycleProgress(source: SourceConnector) {
  const passed = lifecycleLabels.filter(([key]) => statusTone(source.lifecycle[key]) === "ok").length;
  return Math.round((passed / lifecycleLabels.length) * 100);
}

function currentStage(source: SourceConnector) {
  if (source.current_blocker) return label(source.current_blocker);
  const lastPassed = [...lifecycleLabels]
    .reverse()
    .find(([key]) => statusTone(source.lifecycle[key]) === "ok");
  return lastPassed?.[1] || "Candidate review";
}

function truthCount(payload: ProductPayload) {
  return payload.job_readiness.reduce(
    (total, job) => total + (job.explanations?.length || 0),
    0
  );
}

function uncertaintyCount(payload: ProductPayload) {
  return payload.job_readiness.reduce(
    (total, job) => total + (job.uncertainties?.length || 0),
    0
  );
}

function sourceInitials(source: SourceConnector) {
  const parts = source.source_label.split(/\s+/).filter(Boolean);
  return (parts.slice(0, 2).map((part) => part[0]).join("") || "DO").toUpperCase();
}

function CandidateListItem({
  source,
  selected,
  onSelect,
}: {
  source: SourceConnector;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button className={`candidate-row ${selected ? "selected" : ""}`} type="button" onClick={onSelect}>
      <span className="candidate-avatar">{sourceInitials(source)}</span>
      <span className="candidate-row-copy">
        <strong>{source.source_label}</strong>
        <small>{label(source.source_type)} · #{source.candidate_id ?? "–"}</small>
        <em>{currentStage(source)}</em>
      </span>
      <StatusPill value={source.current_blocker ? "attention_required" : source.candidate_status} />
    </button>
  );
}

function SourceLifecycleRail({ source }: { source: SourceConnector }) {
  return (
    <div className="lifecycle-rail" aria-label={`${source.source_name} lifecycle`}>
      {lifecycleLabels.map(([key, text]) => (
        <div className={`lifecycle-step ${statusTone(source.lifecycle[key])}`} key={key}>
          <i />
          <span>{text}</span>
          <small>{label(source.lifecycle[key])}</small>
        </div>
      ))}
    </div>
  );
}

function ProductJobMiniCard({ job }: { job: Job }) {
  return (
    <article className="job-mini-card">
      <div>
        <span className="eyebrow">Silver #{job.silver_job_id}</span>
        <h4>{job.title || "Untitled job"}</h4>
        <p>{job.company_name || "Unknown employer"} · {job.city || "Location unconfirmed"}</p>
      </div>
      <div className="job-mini-meta">
        <StatusPill value={job.product_readiness_status || "unknown"} />
        {job.overall_quality_score != null && <strong>{job.overall_quality_score}</strong>}
      </div>
    </article>
  );
}

function OverviewScreen({
  payload,
  onSelectCandidate,
  onNavigate,
}: {
  payload: ProductPayload;
  onSelectCandidate: (source: SourceConnector) => void;
  onNavigate: (tab: Tab) => void;
}) {
  const overview = payload.source_connector_overview;
  const finalApprovals = overview.sources.filter(
    (source) => source.current_blocker === "final_approval_incomplete"
  );
  const attentionSources = overview.sources.filter((source) => Boolean(source.current_blocker));
  const blockerGroups = Array.from(
    attentionSources.reduce((groups, source) => {
      const key = source.current_blocker || "attention_required";
      groups.set(key, (groups.get(key) || 0) + 1);
      return groups;
    }, new Map<string, number>())
  ).sort((left, right) => right[1] - left[1]);
  const stages = sourceLifecycleStages(overview.summary);
  const recentJobs = payload.top_jobs.length > 0
    ? payload.top_jobs.slice(0, 5)
    : payload.job_readiness.slice(0, 5);

  return (
    <div className="screen-stack">
      <section className="screen-heading">
        <div>
          <span className="eyebrow">Repository & DB truth · operator first</span>
          <h2>Pipeline Overview</h2>
          <p>One control surface for real lifecycle state, blockers, approvals and Product V1 readiness.</p>
        </div>
        <div className="truth-stamp"><i /> Live readmodel</div>
      </section>

      <section className="metrics overview-metrics">
        <Metric labelText="Employer candidates" value={overview.summary.source_count} helper="known source candidates" />
        <Metric labelText="Needs attention" value={overview.summary.attention_count} helper="real blocker / next action" tone="amber" />
        <Metric labelText="Final approval" value={finalApprovals.length} helper="reviewed GUI action available" tone="green" />
        <Metric labelText="Active sources" value={overview.summary.active_count} helper="activation truth, not registration" tone="green" />
        <Metric labelText="Rankable jobs" value={payload.summary.rankable_job_count} helper="hard gates + lifecycle passed" tone="violet" />
        <Metric labelText="Top jobs" value={payload.summary.top_job_count} helper="bounded Product V1 output" tone="cyan" />
      </section>

      <section className="dashboard-card lifecycle-map-card">
        <header className="card-heading-row">
          <div><span className="eyebrow">Validated source pipeline</span><h3>Source & connector lifecycle</h3></div>
          <button className="text-action" type="button" onClick={() => onNavigate("operations")}>Open operations →</button>
        </header>
        <div className="pipeline-map">
          {stages.map((stage, index) => (
            <div className="pipeline-stage" key={stage.key}>
              <div className="pipeline-stage-card">
                <span>{stage.label}</span>
                <strong>{stage.value}</strong>
                <small>{stage.helper}</small>
              </div>
              {index < stages.length - 1 && <div className="pipeline-connector" aria-hidden="true"><i /></div>}
            </div>
          ))}
        </div>
        <p className="truth-note">This map intentionally reports the source/connector lifecycle already exposed by Product V1. It does not invent unprojected candidate stages.</p>
      </section>

      <section className="dashboard-grid dashboard-grid-primary">
        <article className="dashboard-card queue-card">
          <header className="card-heading-row"><div><span className="eyebrow">Operator queue</span><h3>Needs attention</h3></div><strong>{attentionSources.length}</strong></header>
          <div className="compact-list">
            {attentionSources.slice(0, 6).map((source) => (
              <button key={source.source_name} type="button" onClick={() => onSelectCandidate(source)}>
                <span className="compact-dot warn" />
                <span><b>{source.source_label}</b><small>{currentStage(source)}</small></span>
                <em>Review</em>
              </button>
            ))}
            {attentionSources.length === 0 && <p className="empty">No source candidate currently needs attention.</p>}
          </div>
          <button className="text-action footer-link" type="button" onClick={() => onNavigate("candidates")}>View candidate workspace →</button>
        </article>

        <article className="dashboard-card">
          <header className="card-heading-row"><div><span className="eyebrow">Product progression</span><h3>Current job intelligence</h3></div><strong>{payload.summary.observed_job_count}</strong></header>
          <div className="compact-list job-progress-list">
            {recentJobs.map((job) => (
              <div className="progress-row" key={job.silver_job_id}>
                <span className={`compact-dot ${statusTone(job.product_readiness_status)}`} />
                <span><b>{job.title || "Untitled job"}</b><small>{job.company_name || "Unknown employer"}</small></span>
                <StatusPill value={job.product_readiness_status || "unknown"} />
              </div>
            ))}
            {recentJobs.length === 0 && <p className="empty">No Product V1 job readiness rows are available.</p>}
          </div>
        </article>

        <article className="dashboard-card next-safe-card">
          <header className="card-heading-row"><div><span className="eyebrow">Do what matters</span><h3>Next safe actions</h3></div><span className="safe-icon">◇</span></header>
          <div className="safe-action-list">
            {blockerGroups.slice(0, 5).map(([blocker, count]) => (
              <button type="button" key={blocker} onClick={() => onNavigate(blocker === "final_approval_incomplete" ? "approvals" : "candidates")}>
                <span><b>{label(blocker)}</b><small>{count} candidate{count === 1 ? "" : "s"}</small></span>
                <em>Review →</em>
              </button>
            ))}
            {blockerGroups.length === 0 && <p className="empty">No blocker-driven action is currently exposed.</p>}
          </div>
        </article>
      </section>

      <section className="dashboard-grid dashboard-grid-secondary">
        <article className="dashboard-card blocker-card">
          <header className="card-heading-row"><div><span className="eyebrow">Real blocker mix</span><h3>Attention distribution</h3></div></header>
          <div className="bar-stack">
            {blockerGroups.slice(0, 6).map(([blocker, count]) => {
              const width = attentionSources.length ? Math.max(8, Math.round((count / attentionSources.length) * 100)) : 0;
              return (
                <div className="bar-row" key={blocker}>
                  <div><span>{label(blocker)}</span><b>{count}</b></div>
                  <i><span style={{ width: `${width}%` }} /></i>
                </div>
              );
            })}
            {blockerGroups.length === 0 && <p className="empty">No blocker distribution to report.</p>}
          </div>
        </article>

        <article className="dashboard-card truth-model-card">
          <header className="card-heading-row"><div><span className="eyebrow">PED lesson: never mix layers</span><h3>Evidence, truth & uncertainty</h3></div></header>
          <div className="truth-model-grid">
            <div className="truth-tile evidence"><span>Observed evidence</span><strong>{payload.summary.observed_job_count}</strong><small>Product readiness rows backed by current readmodel inputs.</small></div>
            <div className="truth-tile truth"><span>Verified truth signals</span><strong>{truthCount(payload)}</strong><small>Explainable positive signals currently projected for jobs.</small></div>
            <div className="truth-tile hypothesis"><span>Known uncertainties</span><strong>{uncertaintyCount(payload)}</strong><small>Unresolved statements stay explicitly separate from truth.</small></div>
          </div>
        </article>

        <article className="dashboard-card boundary-summary-card">
          <header className="card-heading-row"><div><span className="eyebrow">Authority boundary</span><h3>What this UI may do</h3></div></header>
          <div className="boundary-lines">
            <span><i className="ok" /> Read Product / DB truth</span>
            <span><i className="ok" /> Run provider-free evidence preview</span>
            <span><i className="ok" /> Review the existing final-approval action</span>
            <span><i /> No connector registration or activation</span>
            <span><i /> No provider / ranking / application mutation</span>
          </div>
        </article>
      </section>
    </div>
  );
}

function CandidatesScreen({
  payload,
  selectedSource,
  onSelectSource,
  onReviewFinalApproval,
}: {
  payload: ProductPayload;
  selectedSource: SourceConnector | null;
  onSelectSource: (source: SourceConnector) => void;
  onReviewFinalApproval: (source: SourceConnector) => void;
}) {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<CandidateFilter>("all");
  const sources = payload.source_connector_overview.sources;
  const filtered = useMemo(() => {
    const searchValue = normalize(search);
    return sources.filter((source) => {
      if (searchValue && !normalize(`${source.source_label} ${source.source_name} ${source.source_type}`).includes(searchValue)) return false;
      if (filter === "attention") return Boolean(source.current_blocker);
      if (filter === "active") return source.activation.active === true;
      if (filter === "ingested") return statusTone(source.lifecycle.ingestion) === "ok";
      return true;
    });
  }, [filter, search, sources]);

  const source = selectedSource && sources.some((item) => item.candidate_id === selectedSource.candidate_id)
    ? selectedSource
    : filtered[0] || sources[0] || null;
  const readiness = source ? lifecycleProgress(source) : 0;
  const matchingJobs = source
    ? payload.job_readiness.filter((job) => normalize(job.company_name) === normalize(source.source_label)).slice(0, 4)
    : [];
  const canFinalApprove = Boolean(
    source?.current_blocker === "final_approval_incomplete" &&
    source.candidate_id !== null &&
    source.candidate_id > 0
  );

  return (
    <div className="candidate-workspace">
      <aside className="candidate-queue-panel">
        <header><span className="eyebrow">Employer-origin truth</span><h2>Candidate Queue <small>{sources.length}</small></h2></header>
        <label className="search-box"><span>⌕</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search candidates…" /></label>
        <div className="filter-chips">
          {([
            ["all", "All", sources.length],
            ["attention", "Attention", sources.filter((item) => Boolean(item.current_blocker)).length],
            ["active", "Active", sources.filter((item) => item.activation.active === true).length],
            ["ingested", "Ingested", sources.filter((item) => statusTone(item.lifecycle.ingestion) === "ok").length],
          ] as Array<[CandidateFilter, string, number]>).map(([id, text, count]) => (
            <button className={filter === id ? "active" : ""} type="button" key={id} onClick={() => setFilter(id)}>{text} <b>{count}</b></button>
          ))}
        </div>
        <div className="candidate-list">
          {filtered.map((item) => (
            <CandidateListItem
              key={`${item.candidate_id}-${item.source_name}`}
              source={item}
              selected={source?.candidate_id === item.candidate_id}
              onSelect={() => onSelectSource(item)}
            />
          ))}
          {filtered.length === 0 && <p className="empty">No candidate matches this view.</p>}
        </div>
      </aside>

      <main className="candidate-detail-panel">
        {source ? (
          <>
            <header className="candidate-detail-header">
              <div className="candidate-title-block">
                <span className="candidate-avatar large">{sourceInitials(source)}</span>
                <div><span className="eyebrow">Candidate #{source.candidate_id ?? "–"} · {label(source.source_type)}</span><h2>{source.source_label}</h2><p><code>{source.source_name}</code> · {label(source.candidate_status)}</p></div>
              </div>
              <StatusPill value={source.current_blocker || source.candidate_status} />
            </header>

            <section className="candidate-timeline-card">
              <SourceLifecycleRail source={source} />
            </section>

            <section className="candidate-content-grid">
              <article className="candidate-card summary-card">
                <span className="eyebrow">Summary</span>
                <h3>{source.current_blocker ? "Operator attention required" : "Lifecycle truth available"}</h3>
                <p>{source.current_blocker ? `Current blocker: ${label(source.current_blocker)}.` : "No current blocker is exposed by the source/connector readmodel."}</p>
                <dl className="fact-list">
                  <div><dt>Candidate status</dt><dd>{label(source.candidate_status)}</dd></div>
                  <div><dt>Source type</dt><dd>{label(source.source_type)}</dd></div>
                  <div><dt>Connector class</dt><dd>{source.connector.connector_class || "not materialized"}</dd></div>
                  <div><dt>Search profiles</dt><dd>{source.search_profiles.active_profile_count}/{source.search_profiles.profile_count} active</dd></div>
                </dl>
              </article>

              <article className="candidate-card evidence-card wide">
                <header className="card-heading-row"><div><span className="eyebrow">Evidence observed</span><h3>Repository / DB-backed signals</h3></div></header>
                <div className="evidence-fact-grid">
                  <div><span>Implementation</span><strong>{label(source.connector.implementation_status)}</strong><small>{label(source.connector.implementation_truth_source)}</small></div>
                  <div><span>Validation gate</span><strong>{label(source.gates.connector_validation_gate.status)}</strong><small>{label(source.gates.connector_validation_gate.truth_source)}</small></div>
                  <div><span>Final approval gate</span><strong>{label(source.gates.final_approval_gate.status)}</strong><small>{label(source.gates.final_approval_gate.truth_source)}</small></div>
                  <div><span>Activation</span><strong>{label(source.activation.status)}</strong><small>{label(source.activation.truth_source)}</small></div>
                  <div><span>Ingestion</span><strong>{label(source.last_ingestion.status)}</strong><small>{source.last_ingestion.inserted_count} inserted</small></div>
                  <div><span>Data layers</span><strong>{label(source.layers.status)}</strong><small>Bronze {source.layers.bronze_count} · Silver {source.layers.silver_count}</small></div>
                </div>
              </article>

              <article className="candidate-card truth-card">
                <span className="eyebrow">Verified truth</span>
                <h3>Gate and lifecycle truth</h3>
                <div className="truth-list">
                  <span><i className={source.connector.implemented ? "ok" : ""} /> Connector implementation <b>{source.connector.implemented ? "verified" : "not verified"}</b></span>
                  <span><i className={source.gates.connector_validation_gate.passed ? "ok" : ""} /> Validation <b>{label(source.gates.connector_validation_gate.decision)}</b></span>
                  <span><i className={source.gates.final_approval_gate.passed ? "ok" : ""} /> Final approval <b>{label(source.gates.final_approval_gate.decision)}</b></span>
                  <span><i className={source.activation.active === true ? "ok" : ""} /> Activation <b>{label(source.activation.status)}</b></span>
                </div>
              </article>

              <article className="candidate-card hypothesis-card">
                <span className="eyebrow">Uncertainty / hypothesis</span>
                <h3>Never promoted to truth</h3>
                <p>{source.current_blocker ? `Unresolved: ${label(source.current_blocker)}.` : "No unresolved source blocker is projected."}</p>
                {source.inconsistencies.length > 0 ? (
                  <ul>{source.inconsistencies.map((item) => <li key={item}>{label(item)}</li>)}</ul>
                ) : (
                  <p className="muted-copy">No readmodel inconsistency is currently reported. AI hypotheses, when present elsewhere, remain non-authoritative.</p>
                )}
              </article>

              <article className="candidate-card next-action-card wide">
                <div className="safe-icon">◇</div>
                <div><span className="eyebrow">Next safe action</span><h3>{source.current_blocker ? label(source.current_blocker) : "Continue from current lifecycle truth"}</h3><p>{source.next_action}</p></div>
                {canFinalApprove ? (
                  <button className="primary-action" type="button" onClick={() => onReviewFinalApproval(source)}>Review final approval</button>
                ) : (
                  <button className="secondary-action" type="button" disabled>No reviewed write action here</button>
                )}
              </article>
            </section>

            <section className="candidate-jobs-section">
              <header className="card-heading-row"><div><span className="eyebrow">Downstream Product V1</span><h3>Jobs linked by current employer name</h3></div><span>{matchingJobs.length} shown</span></header>
              <div className="job-mini-grid">
                {matchingJobs.map((job) => <ProductJobMiniCard key={job.silver_job_id} job={job} />)}
                {matchingJobs.length === 0 && <p className="empty">No Product V1 job-readiness row currently matches this employer label. The UI does not infer one.</p>}
              </div>
            </section>
          </>
        ) : <p className="empty">No employer-origin candidate is available.</p>}
      </main>

      <aside className="candidate-side-panel">
        {source ? (
          <>
            <article className="side-card readiness-card">
              <span className="eyebrow">Lifecycle readiness</span>
              <div className="readiness-display">
                <div className="readiness-ring" style={{ "--progress": `${readiness}%` } as CSSProperties}><strong>{readiness}%</strong><small>verified</small></div>
                <div><h3>{readiness >= 80 ? "Advanced" : readiness >= 50 ? "In progress" : "Early stage"}</h3><p>Based only on six exposed source lifecycle steps.</p></div>
              </div>
            </article>

            <article className="side-card">
              <span className="eyebrow">Current boundary</span>
              <h3>{source.current_blocker ? label(source.current_blocker) : "No blocker exposed"}</h3>
              <p>{source.next_action}</p>
            </article>

            <article className="side-card checklist-card">
              <span className="eyebrow">Truth checklist</span>
              <div className="truth-list">
                <span><i className={source.connector.implemented ? "ok" : ""} /> Implementation</span>
                <span><i className={source.gates.connector_validation_gate.passed ? "ok" : ""} /> Validation</span>
                <span><i className={source.gates.final_approval_gate.passed ? "ok" : ""} /> Final approval</span>
                <span><i className={source.connector.code_backed_registered ? "ok" : ""} /> Registration</span>
                <span><i className={source.activation.active === true ? "ok" : ""} /> Activation</span>
                <span><i className={statusTone(source.lifecycle.ingestion) === "ok" ? "ok" : ""} /> Ingestion</span>
              </div>
            </article>

            <article className="side-card action-card">
              <span className="eyebrow">Actions</span>
              {canFinalApprove ? (
                <button className="primary-action" type="button" onClick={() => onReviewFinalApproval(source)}>Review final approval</button>
              ) : (
                <button className="secondary-action" type="button" disabled>No reviewed mutation available</button>
              )}
              <small>All other progression remains on existing repository-backed operator/runtime paths.</small>
            </article>
          </>
        ) : null}
      </aside>
    </div>
  );
}

function ApprovalsScreen({
  payload,
  selectedSource,
  onSelectSource,
  onReviewFinalApproval,
}: {
  payload: ProductPayload;
  selectedSource: SourceConnector | null;
  onSelectSource: (source: SourceConnector) => void;
  onReviewFinalApproval: (source: SourceConnector) => void;
}) {
  const sources = payload.source_connector_overview.sources;
  const approvalQueue = sources.filter((source) => Boolean(source.current_blocker));
  const finalApprovalQueue = approvalQueue.filter((source) => source.current_blocker === "final_approval_incomplete");
  const source = selectedSource && approvalQueue.some((item) => item.candidate_id === selectedSource.candidate_id)
    ? selectedSource
    : finalApprovalQueue[0] || approvalQueue[0] || null;
  const canFinalApprove = Boolean(source?.current_blocker === "final_approval_incomplete" && source.candidate_id !== null && source.candidate_id > 0);

  return (
    <div className="approval-screen screen-stack">
      <section className="screen-heading">
        <div><span className="eyebrow">Safe operator decisions</span><h2>Approval Center</h2><p>Review evidence and authority boundaries before any existing write action is exposed.</p></div>
        <div className="truth-stamp"><i /> Audit-first</div>
      </section>

      <section className="approval-tabs">
        <div className="approval-tab active"><span>Final approval</span><strong>{finalApprovalQueue.length}</strong><small>existing reviewed GUI action</small></div>
        <div className="approval-tab"><span>Other lifecycle blockers</span><strong>{Math.max(0, approvalQueue.length - finalApprovalQueue.length)}</strong><small>review-only in this UI</small></div>
        <div className="approval-tab"><span>Product decisions</span><strong>{payload.operator_blockers.length}</strong><small>policy / source-document boundaries</small></div>
      </section>

      <section className="approval-layout">
        <aside className="approval-queue dashboard-card">
          <header><span className="eyebrow">Review queue</span><h3>{approvalQueue.length} items</h3></header>
          <div className="approval-list">
            {approvalQueue.map((item) => (
              <button className={source?.candidate_id === item.candidate_id ? "selected" : ""} key={`${item.candidate_id}-${item.source_name}`} type="button" onClick={() => onSelectSource(item)}>
                <span className={`priority-mark ${item.current_blocker === "final_approval_incomplete" ? "ready" : "review"}`} />
                <span><b>{item.source_label}</b><small>{label(item.current_blocker)}</small></span>
                <em>#{item.candidate_id ?? "–"}</em>
              </button>
            ))}
            {approvalQueue.length === 0 && <p className="empty">No approval or blocker review is currently exposed.</p>}
          </div>
        </aside>

        <main className="approval-review-panel dashboard-card">
          {source ? (
            <>
              <header className="approval-review-header">
                <div><span className="eyebrow">Candidate #{source.candidate_id ?? "–"}</span><h2>{source.source_label}</h2><p><code>{source.source_name}</code> · {label(source.source_type)}</p></div>
                <StatusPill value={source.current_blocker || "review_required"} />
              </header>

              <section className="approval-review-grid">
                <article><span className="eyebrow">What we know</span><h3>Verified lifecycle evidence</h3><ul className="review-points positive"><li>Implementation: {label(source.connector.implementation_status)}</li><li>Validation: {label(source.gates.connector_validation_gate.status)}</li><li>Registration: {label(source.connector.registration_status)}</li><li>Activation: {label(source.activation.status)}</li></ul></article>
                <article><span className="eyebrow">What is still uncertain</span><h3>Explicit open state</h3><ul className="review-points uncertain"><li>{source.current_blocker ? label(source.current_blocker) : "No blocker exposed"}</li>{source.inconsistencies.map((item) => <li key={item}>{label(item)}</li>)}</ul></article>
                <article><span className="eyebrow">Why approval is needed</span><h3>Authority does not follow confidence</h3><p>{source.next_action}</p><small>Evidence may support a decision; it never grants authority by itself.</small></article>
              </section>

              <section className="approval-evidence-grid">
                <article><span>Validation gate</span><strong>{label(source.gates.connector_validation_gate.status)}</strong><small>{label(source.gates.connector_validation_gate.decision)}</small></article>
                <article><span>Final approval gate</span><strong>{label(source.gates.final_approval_gate.status)}</strong><small>{label(source.gates.final_approval_gate.decision)}</small></article>
                <article><span>Search profiles</span><strong>{source.search_profiles.active_profile_count}/{source.search_profiles.profile_count}</strong><small>{label(source.search_profiles.status)}</small></article>
                <article><span>Data evidence</span><strong>{source.layers.silver_count} Silver</strong><small>{source.layers.bronze_count} Bronze</small></article>
              </section>

              <section className="approval-decision-card">
                <div><span className="eyebrow">Decision boundary</span><h3>{canFinalApprove ? "Reviewed final-approval action available" : "Review only — no GUI mutation authorized"}</h3><p>{canFinalApprove ? "The existing 3A action records only the final approval gate and then reloads Product / DB truth." : "Continue through the existing repository-backed operator path. This UX does not invent a second action."}</p></div>
                {canFinalApprove ? <button className="primary-action large" type="button" onClick={() => onReviewFinalApproval(source)}>Open final approval review</button> : <button className="secondary-action large" type="button" disabled>No reviewed action</button>}
              </section>
            </>
          ) : <p className="empty">No approval item is available.</p>}
        </main>

        <aside className="approval-side-panel">
          <article className="side-card"><span className="eyebrow">Product-level operator gates</span><h3>{payload.operator_blockers.length}</h3><div className="operator-blocker-list">{payload.operator_blockers.map((blocker) => <div key={blocker.code}><b>{blocker.title}</b><small>{blocker.detail}</small></div>)}{payload.operator_blockers.length === 0 && <p className="empty">No Product V1 operator blocker is exposed.</p>}</div></article>
          <article className="side-card boundary-summary-card"><span className="eyebrow">Hard boundary</span><div className="boundary-lines"><span><i className="ok" /> Final gate recording only</span><span><i /> No registration</span><span><i /> No activation</span><span><i /> No ingestion</span><span><i /> No provider / application action</span></div></article>
        </aside>
      </section>
    </div>
  );
}

function OperationsScreen({ payload }: { payload: ProductPayload }) {
  const overview = payload.source_connector_overview;
  const stages = sourceLifecycleStages(overview.summary);
  const boundaryEntries = Object.entries({ ...payload.boundaries, ...overview.boundaries });
  const lifecycleHealth = [
    ["Current active", payload.summary.current_active_job_count, "lifecycle-confirmed vacancies"],
    ["Stale / refresh", payload.summary.stale_job_count, "not safe for current Top 5"],
    ["Unverifiable", payload.summary.unverifiable_job_count, "evidence cannot confirm current state"],
    ["Inactive", payload.summary.inactive_confirmed_job_count, "confirmed inactive"],
  ] as const;

  return (
    <div className="screen-stack operations-screen">
      <section className="screen-heading"><div><span className="eyebrow">System truth & runtime-facing state</span><h2>Operations & Observability</h2><p>Lifecycle coverage, Product V1 health, waves, data layers and authority boundaries without invented telemetry.</p></div><div className="truth-stamp"><i /> Read-only observability</div></section>

      <section className="operations-grid operations-grid-top">
        <article className="dashboard-card lifecycle-map-card compact-map"><header className="card-heading-row"><div><span className="eyebrow">Source pipeline</span><h3>Lifecycle map</h3></div></header><div className="pipeline-map">{stages.map((stage, index) => <div className="pipeline-stage" key={stage.key}><div className="pipeline-stage-card"><span>{stage.label}</span><strong>{stage.value}</strong><small>{stage.helper}</small></div>{index < stages.length - 1 && <div className="pipeline-connector"><i /></div>}</div>)}</div></article>

        <article className="dashboard-card"><header className="card-heading-row"><div><span className="eyebrow">Product V1 jobs</span><h3>Lifecycle health</h3></div></header><div className="health-grid">{lifecycleHealth.map(([name, value, helper]) => <div key={name}><span>{name}</span><strong>{value}</strong><small>{helper}</small></div>)}</div></article>
      </section>

      <section className="operations-grid operations-grid-middle">
        <article className="dashboard-card"><header className="card-heading-row"><div><span className="eyebrow">Deterministic scope rotation</span><h3>StepStone waves</h3></div><strong>{payload.wave_states.length}</strong></header><div className="wave-table">{payload.wave_states.slice(0, 10).map((wave) => <div key={wave.search_term}><span><b>{wave.search_term}</b><small>{wave.current_interval_days} day interval</small></span><StatusPill value={wave.is_not_exclusion_enabled ? "wave_enabled" : "baseline_only"} /><em>Wave {wave.current_exclusion_wave_index}</em></div>)}{payload.wave_states.length === 0 && <p className="empty">No DB-backed wave state is available.</p>}</div></article>

        <article className="dashboard-card"><header className="card-heading-row"><div><span className="eyebrow">Source truth</span><h3>Data layers & ingestion</h3></div></header><div className="operations-source-list">{overview.sources.slice(0, 10).map((source) => <div key={source.source_name}><span><b>{source.source_label}</b><small>{label(source.last_ingestion.status)}</small></span><em>Bronze {source.layers.bronze_count}</em><em>Silver {source.layers.silver_count}</em></div>)}</div></article>

        <article className="dashboard-card replay-card"><header className="card-heading-row"><div><span className="eyebrow">Determinism contract</span><h3>Replay-safe by design</h3></div><span className="safe-icon">◇</span></header><p>Provider execution is not a dashboard effect. Current Product V1 readmodels are served without provider calls, and deterministic evidence preview remains read-only.</p><div className="boundary-lines"><span><i className="ok" /> Readmodel has no provider call</span><span><i className="ok" /> Evidence preview has no DB write</span><span><i className="ok" /> Uncertainty remains explicit</span><span><i /> No hidden auto-apply</span></div></article>
      </section>

      <section className="operations-grid operations-grid-bottom">
        <article className="dashboard-card"><header className="card-heading-row"><div><span className="eyebrow">Authority matrix</span><h3>Product boundaries</h3></div></header><div className="boundary-matrix">{boundaryEntries.map(([name, enabled]) => <div key={name}><span>{label(name)}</span><StatusPill value={enabled ? "enforced" : "not_enforced"} /></div>)}</div></article>

        <article className="dashboard-card"><header className="card-heading-row"><div><span className="eyebrow">Application preparation</span><h3>Source document readiness</h3></div></header><div className="application-readiness-grid"><div><span>Base CV</span><strong>{payload.application_sources_ready.base_cv ? "Approved" : "Required"}</strong></div><div><span>Base letter</span><strong>{payload.application_sources_ready.base_application_letter ? "Approved" : "Required"}</strong></div><div><span>Generation-ready jobs</span><strong>{payload.summary.application_ready_count}</strong></div></div><p className="truth-note">Draft generation is separate from application submission. This screen exposes no auto-apply action.</p></article>
      </section>
    </div>
  );
}

export default function App() {
  const [payload, setPayload] = useState<ProductPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [selectedCandidateId, setSelectedCandidateId] = useState<number | null>(null);
  const [finalApprovalSource, setFinalApprovalSource] = useState<SourceConnector | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    readProductTruth(controller.signal)
      .then(setPayload)
      .catch((reason: unknown) => {
        if ((reason as Error).name !== "AbortError") setError(String(reason));
      });
    return () => controller.abort();
  }, []);

  const refreshProductTruth = async () => {
    const nextPayload = await readProductTruth();
    setPayload(nextPayload);
    setError(null);
  };

  const selectedSource = useMemo(() => {
    const sources = payload?.source_connector_overview.sources || [];
    if (selectedCandidateId !== null) {
      const exact = sources.find((source) => source.candidate_id === selectedCandidateId);
      if (exact) return exact;
    }
    return sources.find((source) => Boolean(source.current_blocker)) || sources[0] || null;
  }, [payload, selectedCandidateId]);

  const chooseCandidate = (source: SourceConnector) => {
    setSelectedCandidateId(source.candidate_id);
    setTab("candidates");
  };

  if (error) {
    return <main className="fatal"><div className="fatal-card"><span className="eyebrow">Fail closed</span><h1>Control Center unavailable</h1><pre>{error}</pre></div></main>;
  }
  if (!payload) {
    return <main className="loading"><div className="sonar" /><p>Reading Deep Ocean product state…</p></main>;
  }

  return (
    <div className="control-center-shell">
      <header className="topbar">
        <div className="topbar-brand"><div className="brand-mark"><span>DO</span></div><div><strong>Deep Ocean</strong><small>Intelligence</small></div></div>
        <nav className="topnav" aria-label="Primary navigation">
          {([
            ["overview", "Overview"],
            ["candidates", "Candidates"],
            ["approvals", "Approvals"],
            ["operations", "Operations"],
          ] as Array<[Tab, string]>).map(([id, text]) => (
            <button type="button" className={tab === id ? "active" : ""} key={id} onClick={() => setTab(id)}>{text}{id === "approvals" && payload.source_connector_overview.summary.attention_count > 0 ? <span>{payload.source_connector_overview.summary.attention_count}</span> : null}</button>
          ))}
        </nav>
        <div className="topbar-status"><span className="truth-stamp"><i /> DB truth</span><button type="button" className="refresh-button" onClick={() => void refreshProductTruth()}>↻ Refresh</button></div>
      </header>

      <div className="app-body">
        <aside className="icon-rail" aria-label="Quick navigation">
          <button type="button" className={tab === "overview" ? "active" : ""} onClick={() => setTab("overview")} title="Overview">⌘</button>
          <button type="button" className={tab === "candidates" ? "active" : ""} onClick={() => setTab("candidates")} title="Candidates">◉</button>
          <button type="button" className={tab === "approvals" ? "active" : ""} onClick={() => setTab("approvals")} title="Approvals">◇</button>
          <button type="button" className={tab === "operations" ? "active" : ""} onClick={() => setTab("operations")} title="Operations">⌁</button>
          <div className="rail-spacer" />
          <span title="Product schema">v1</span>
        </aside>

        <main className="app-main">
          {tab === "overview" && <OverviewScreen payload={payload} onSelectCandidate={chooseCandidate} onNavigate={setTab} />}
          {tab === "candidates" && <CandidatesScreen payload={payload} selectedSource={selectedSource} onSelectSource={(source) => setSelectedCandidateId(source.candidate_id)} onReviewFinalApproval={setFinalApprovalSource} />}
          {tab === "approvals" && <ApprovalsScreen payload={payload} selectedSource={selectedSource} onSelectSource={(source) => setSelectedCandidateId(source.candidate_id)} onReviewFinalApproval={setFinalApprovalSource} />}
          {tab === "operations" && <OperationsScreen payload={payload} />}
        </main>
      </div>

      <FinalApprovalReviewDialog
        source={finalApprovalSource}
        refreshProductTruth={refreshProductTruth}
        onClose={() => setFinalApprovalSource(null)}
      />
    </div>
  );
}
