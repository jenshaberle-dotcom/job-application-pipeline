import { useEffect, useMemo, useState, type CSSProperties } from "react";
import FinalApprovalReviewDialog from "./FinalApprovalReviewDialog";
import JobReviewLabelControls, {
  type JobReviewLabelState,
} from "./JobReviewLabelControls";

type OperatorBlocker = { code: string; title: string; detail: string };
type WaveState = {
  search_term: string;
  is_not_exclusion_enabled: boolean;
  current_exclusion_wave_index: number;
  current_interval_days: number;
};
type Job = {
  silver_job_id: number;
  product_rank?: number;
  title?: string | null;
  company_name?: string | null;
  city?: string | null;
  country?: string | null;
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
  review_label?: JobReviewLabelState | null;
};
type GateState = { status: string; decision?: string | null; passed: boolean; truth_source: string };
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
  gates: { connector_validation_gate: GateState; final_approval_gate: GateState };
  activation: { status: string; active: boolean | null; truth_source: string };
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
    reviewed_job_count?: number;
    training_eligible_review_label_count?: number;
  };
  wave_states: WaveState[];
  ranking_policy: Record<string, unknown>;
  job_readiness: Job[];
  top_jobs: Job[];
  application_readiness: Array<Record<string, unknown>>;
  application_sources_ready: { base_cv: boolean; base_application_letter: boolean };
  source_connector_overview: SourceConnectorOverview;
  operator_blockers: OperatorBlocker[];
  review_label_capture?: {
    available: boolean;
    action_path: string;
    labels: string[];
    selection_reason: string;
    product_authority: boolean;
  };
  boundaries: Record<string, boolean>;
};

type Tab = "jobs" | "sources" | "approvals" | "operations";
type JobFilter = "current" | "all" | "stale" | "rankable";
type SourceFilter = "attention" | "all" | "active" | "ingested";
type BlockerKind = "TECH" | "APPROVAL" | "CONFIG" | "OBSERVABILITY" | "OPERATION" | "CLEAR";

const label = (value: string | undefined | null) => (value || "unknown").replaceAll("_", " ");
const normalize = (value: string | undefined | null) => (value || "").trim().toLocaleLowerCase();
const lifecycleLabels: Array<[keyof SourceConnector["lifecycle"], string]> = [
  ["implementation", "Implemented"], ["validation", "Validated"], ["final_approval", "Approved"],
  ["registration", "Registered"], ["activation", "Activated"], ["ingestion", "Ingested"],
];

const statusTone = (value: string | undefined | null) => {
  const v = normalize(value);
  if (v.includes("error") || v.includes("failed") || v.includes("blocked") || v.includes("inconsistent")) return "bad";
  if (["passed", "approved", "registered", "implemented", "active", "active confirmed", "ingested", "success", "rankable"].includes(v)) return "ok";
  if (v.includes("required") || v.includes("stale") || v.includes("unknown") || v.includes("pending") || v.includes("attention") || v.includes("not ")) return "warn";
  return "neutral";
};

function blockerKind(blocker: string | null | undefined): BlockerKind {
  if (!blocker) return "CLEAR";
  if (["final_approval_incomplete", "controlled_activation_not_completed"].includes(blocker)) return "APPROVAL";
  if (["activation_truth_unavailable", "ingestion_truth_unavailable"].includes(blocker)) return "OBSERVABILITY";
  if (["persisted_ingestion_data_without_active_search_profile", "candidate_marked_active_without_active_search_profile"].includes(blocker)) return "CONFIG";
  if (["no_persisted_ingestion", "silver_processing_pending"].includes(blocker)) return "OPERATION";
  return "TECH";
}

function blockerKindLabel(kind: BlockerKind) {
  return ({ TECH: "Technical", APPROVAL: "Approval / authority", CONFIG: "Configuration", OBSERVABILITY: "Truth / observability", OPERATION: "Operational step", CLEAR: "Clear" })[kind];
}

function sourceInitials(source: SourceConnector) {
  return (source.source_label.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("") || "DO").toUpperCase();
}
function jobFit(job: Job) {
  return job.overall_quality_score ?? null;
}
function jobCurrent(job: Job) {
  return normalize(job.lifecycle_status) === "active confirmed" || normalize(job.lifecycle_status) === "active_confirmed";
}
function jobStale(job: Job) {
  return normalize(job.lifecycle_status).includes("stale");
}
function scoreText(value: number | null | undefined) {
  return value == null ? "—" : `${Math.round(value)}%`;
}

async function readProductTruth(signal?: AbortSignal): Promise<ProductPayload> {
  const response = await fetch("/api/v1/product-v1", { ...(signal ? { signal } : {}), headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`API returned ${response.status}`);
  return response.json() as Promise<ProductPayload>;
}

function StatusPill({ value }: { value: string }) {
  return <span className={`status-pill ${statusTone(value)}`}>{label(value)}</span>;
}
function KindPill({ blocker }: { blocker?: string | null }) {
  const kind = blockerKind(blocker);
  return <span className={`kind-pill kind-${kind.toLowerCase()}`}>{kind}</span>;
}
function Metric({ labelText, value, helper, tone = "cyan" }: { labelText: string; value: number; helper: string; tone?: "cyan" | "green" | "amber" | "violet" }) {
  return <article className={`metric-card tone-${tone}`}><span>{labelText}</span><strong>{value}</strong><small>{helper}</small></article>;
}
function SourceLifecycleRail({ source }: { source: SourceConnector }) {
  return <div className="lifecycle-rail">{lifecycleLabels.map(([key, text]) => <div className={`lifecycle-step ${statusTone(source.lifecycle[key])}`} key={key}><i /><span>{text}</span><small>{label(source.lifecycle[key])}</small></div>)}</div>;
}

function JobsScreen({ payload, refreshProductTruth }: { payload: ProductPayload; refreshProductTruth: () => Promise<void> }) {
  const [filter, setFilter] = useState<JobFilter>("current");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const currentJobs = payload.job_readiness.filter(jobCurrent);
  const rankableJobs = payload.job_readiness.filter((job) => job.product_readiness_status === "rankable");
  const assessedJobs = payload.job_readiness.filter((job) => jobFit(job) != null).sort((a, b) => Number(jobFit(b) || 0) - Number(jobFit(a) || 0));
  const filtered = useMemo(() => {
    const q = normalize(search);
    return payload.job_readiness.filter((job) => {
      if (filter === "current" && !jobCurrent(job)) return false;
      if (filter === "stale" && !jobStale(job)) return false;
      if (filter === "rankable" && job.product_readiness_status !== "rankable") return false;
      return !q || normalize(`${job.title} ${job.company_name} ${job.city} ${job.source_url}`).includes(q);
    });
  }, [filter, payload.job_readiness, search]);
  const selected = payload.job_readiness.find((job) => job.silver_job_id === selectedId) || filtered[0] || null;
  const topJobs = payload.top_jobs.slice(0, 5);

  return <div className="page-stack jobs-page">
    <section className="page-toolbar">
      <div><span className="eyebrow">Job market · current Product V1 truth</span><h1>Jobs</h1></div>
      <div className="toolbar-note">CV source: <b>{payload.application_sources_ready.base_cv ? "approved" : "not approved"}</b> · current scoring is profile-fit, not a CV-match claim.</div>
    </section>

    <section className="metrics jobs-metrics">
      <Metric labelText="Current active" value={payload.summary.current_active_job_count} helper="lifecycle-confirmed vacancies" tone="green" />
      <Metric labelText="Observed" value={payload.summary.observed_job_count} helper="all Product V1 readiness rows" />
      <Metric labelText="Stale / refresh" value={payload.summary.stale_job_count} helper="not safe for current Top 5" tone="amber" />
      <Metric labelText="Rankable" value={payload.summary.rankable_job_count} helper="all hard gates passed" tone="violet" />
      <Metric labelText="Top 5 now" value={payload.summary.top_job_count} helper="authoritative application shortlist" />
    </section>

    <section className="jobs-top-grid">
      <article className="dashboard-card top-five-card">
        <header className="card-heading-row"><div><span className="eyebrow">What should I apply to now?</span><h2>Authoritative Top 5</h2></div><strong>{topJobs.length}/5</strong></header>
        {topJobs.length > 0 ? <div className="top-five-list">{topJobs.map((job, index) => <article key={job.silver_job_id} className="top-job"><span className="rank-badge">#{job.product_rank || index + 1}</span><div><h3>{job.title || "Untitled job"}</h3><p>{job.company_name || "Unknown employer"} · {job.city || "Location unconfirmed"}</p><small>{scoreText(job.overall_quality_score)} profile fit · {label(job.work_model)}</small></div>{job.source_url ? <a href={job.source_url} target="_blank" rel="noreferrer">Open job ↗</a> : <span className="missing-link">No source URL</span>}</article>)}</div> : <div className="honest-empty"><strong>No authoritative application recommendation yet.</strong><p>Current truth is {payload.summary.current_active_job_count} active, {payload.summary.rankable_job_count} rankable and therefore {payload.summary.top_job_count} Top-5 jobs. The UI will not manufacture a shortlist from stale or incomplete evidence.</p></div>}
      </article>

      <article className="dashboard-card fit-explainer-card">
        <header className="card-heading-row"><div><span className="eyebrow">Matching truth</span><h2>Profile fit ≠ CV match</h2></div></header>
        <p>Product V1 currently scores profile direction, data focus, reliability focus and evidence quality. A job-wise score explicitly grounded in the approved base CV is not projected yet.</p>
        <div className="mini-stats"><div><span>Assessed jobs</span><strong>{assessedJobs.length}</strong></div><div><span>Approved base CV</span><strong>{payload.application_sources_ready.base_cv ? "Yes" : "No"}</strong></div><div><span>CV-match metric</span><strong>Not available</strong></div></div>
      </article>
    </section>

    <section className="jobs-workspace dashboard-card">
      <header className="jobs-list-toolbar">
        <div className="filter-chips">{([ ["current", "Current", currentJobs.length], ["rankable", "Rankable", rankableJobs.length], ["stale", "Stale", payload.summary.stale_job_count], ["all", "All observed", payload.job_readiness.length] ] as Array<[JobFilter, string, number]>).map(([id, text, count]) => <button type="button" className={filter === id ? "active" : ""} onClick={() => setFilter(id)} key={id}>{text} <b>{count}</b></button>)}</div>
        <label className="search-box jobs-search"><span>⌕</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search title, employer, location…" /></label>
      </header>
      <div className="jobs-split">
        <div className="jobs-table-wrap">
          <table className="jobs-table"><thead><tr><th>Fit</th><th>Job</th><th>Location</th><th>Lifecycle</th><th>Product gate</th><th>Published</th><th>Link</th></tr></thead><tbody>{filtered.map((job) => <tr key={job.silver_job_id} className={selected?.silver_job_id === job.silver_job_id ? "selected" : ""} onClick={() => setSelectedId(job.silver_job_id)}><td><strong className="fit-score">{scoreText(job.overall_quality_score)}</strong></td><td><b>{job.title || "Untitled job"}</b><small>{job.company_name || "Unknown employer"}</small></td><td>{job.city || job.country || "—"}<small>{label(job.work_model)}</small></td><td><StatusPill value={job.lifecycle_status || "unknown"} /></td><td><StatusPill value={job.product_readiness_status || "unknown"} /></td><td>{job.publication_date || "—"}</td><td>{job.source_url ? <a href={job.source_url} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()}>Open ↗</a> : "—"}</td></tr>)}</tbody></table>
          {filtered.length === 0 && <p className="empty">No jobs match this truth filter.</p>}
        </div>
        <aside className="job-detail-panel">{selected ? <><span className="eyebrow">Silver #{selected.silver_job_id}</span><h2>{selected.title || "Untitled job"}</h2><p>{selected.company_name || "Unknown employer"} · {selected.city || "Location unconfirmed"}</p>{selected.source_url ? <a className="primary-link" href={selected.source_url} target="_blank" rel="noreferrer">Open original job ↗</a> : <span className="missing-link">No source URL projected</span>}
          <JobReviewLabelControls silverJobId={selected.silver_job_id} currentLabel={selected.review_label} captureAvailable={payload.review_label_capture?.available === true} refreshProductTruth={refreshProductTruth} />
          <section className="score-breakdown"><h3>Profile-fit signals</h3>{([ ["Overall", selected.overall_quality_score], ["Profile direction", selected.profile_direction_score], ["Data focus", selected.data_focus_score], ["Reliability", selected.reliability_focus_score], ["Evidence quality", selected.evidence_quality_score] ] as Array<[string, number | null | undefined]>).map(([name, value]) => <div key={name}><span>{name}</span><i><b style={{ width: `${Math.max(0, Math.min(100, value || 0))}%` }} /></i><strong>{scoreText(value)}</strong></div>)}</section>
          <section className="detail-facts"><div><span>Lifecycle</span><StatusPill value={selected.lifecycle_status || "unknown"} /></div><div><span>Product gate</span><StatusPill value={selected.product_readiness_status || "unknown"} /></div><div><span>Work model</span><b>{label(selected.work_model)}</b></div><div><span>Commute</span><b>{selected.commute_minutes == null ? "—" : `${selected.commute_minutes} min`}</b></div></section>
          <section className="evidence-columns"><div><span className="eyebrow">Verified / explanations</span>{selected.explanations?.length ? <ul>{selected.explanations.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="muted-copy">No explanation signals projected.</p>}</div><div><span className="eyebrow">Uncertainty / hypothesis</span>{selected.uncertainties?.length ? <ul>{selected.uncertainties.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="muted-copy">No uncertainty statements projected.</p>}</div></section>
        </> : <p className="empty">Select a job.</p>}</aside>
      </div>
    </section>
  </div>;
}

function SourcesScreen({ payload, selectedSource, onSelectSource, onReviewFinalApproval }: { payload: ProductPayload; selectedSource: SourceConnector | null; onSelectSource: (source: SourceConnector) => void; onReviewFinalApproval: (source: SourceConnector) => void }) {
  const [filter, setFilter] = useState<SourceFilter>("attention");
  const [search, setSearch] = useState("");
  const sources = payload.source_connector_overview.sources;
  const filtered = useMemo(() => {
    const q = normalize(search);
    return sources.filter((source) => {
      if (q && !normalize(`${source.source_label} ${source.source_name} ${source.current_blocker}`).includes(q)) return false;
      if (filter === "attention") return Boolean(source.current_blocker);
      if (filter === "active") return source.activation.active === true;
      if (filter === "ingested") return source.layers.bronze_present === true || source.layers.silver_present === true;
      return true;
    });
  }, [filter, search, sources]);
  const source = selectedSource && filtered.some((item) => item.candidate_id === selectedSource.candidate_id) ? selectedSource : filtered[0] || sources[0] || null;
  const kindCounts = sources.reduce((counts, item) => { const kind = blockerKind(item.current_blocker); counts[kind] = (counts[kind] || 0) + (item.current_blocker ? 1 : 0); return counts; }, {} as Record<BlockerKind, number>);
  const canFinalApprove = Boolean(source?.current_blocker === "final_approval_incomplete" && source.candidate_id && source.candidate_id > 0);

  return <div className="page-stack sources-page">
    <section className="page-toolbar"><div><span className="eyebrow">Connector & source control</span><h1>Sources</h1></div><div className="blocker-kind-summary"><span><b>{kindCounts.TECH || 0}</b> tech</span><span><b>{kindCounts.APPROVAL || 0}</b> approval</span><span><b>{kindCounts.CONFIG || 0}</b> config</span><span><b>{kindCounts.OBSERVABILITY || 0}</b> truth</span><span><b>{kindCounts.OPERATION || 0}</b> operation</span></div></section>
    <section className="source-workspace">
      <aside className="source-list-panel dashboard-card"><div className="filter-chips">{([ ["attention", "Attention", sources.filter((item) => item.current_blocker).length], ["all", "All", sources.length], ["active", "Active", sources.filter((item) => item.activation.active === true).length], ["ingested", "Ingested", sources.filter((item) => item.layers.bronze_present || item.layers.silver_present).length] ] as Array<[SourceFilter, string, number]>).map(([id, text, count]) => <button type="button" key={id} className={filter === id ? "active" : ""} onClick={() => setFilter(id)}>{text} <b>{count}</b></button>)}</div><label className="search-box"><span>⌕</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search source or blocker…" /></label><div className="source-list">{filtered.map((item) => <button key={`${item.candidate_id}-${item.source_name}`} type="button" className={source?.candidate_id === item.candidate_id ? "selected" : ""} onClick={() => onSelectSource(item)}><span className="candidate-avatar">{sourceInitials(item)}</span><span><b>{item.source_label}</b><small>{label(item.current_blocker || item.candidate_status)}</small></span><KindPill blocker={item.current_blocker} /></button>)}</div></aside>
      <main className="source-detail dashboard-card">{source ? <><header className="source-detail-header"><div><span className="eyebrow">Candidate #{source.candidate_id ?? "–"} · {label(source.source_type)}</span><h2>{source.source_label}</h2><code>{source.source_name}</code></div><div className="source-state"><KindPill blocker={source.current_blocker} /><StatusPill value={source.current_blocker || source.candidate_status} /></div></header><SourceLifecycleRail source={source} />
        <section className="source-diagnosis"><article className="diagnosis-primary"><span className="eyebrow">Where does it stick?</span><h3>{source.current_blocker ? label(source.current_blocker) : "No blocker exposed"}</h3><p>{source.current_blocker ? blockerKindLabel(blockerKind(source.current_blocker)) : "Lifecycle currently has no blocking state."}</p></article><article><span className="eyebrow">Next safe action</span><h3>{source.next_action}</h3><p>Evidence and confidence never grant authority by themselves.</p></article></section>
        <section className="source-fact-grid"><article><span>Implementation</span><strong>{label(source.connector.implementation_status)}</strong><small>{label(source.connector.implementation_truth_source)}</small></article><article><span>Validation</span><strong>{label(source.gates.connector_validation_gate.status)}</strong><small>{label(source.gates.connector_validation_gate.decision)}</small></article><article><span>Final approval</span><strong>{label(source.gates.final_approval_gate.status)}</strong><small>{label(source.gates.final_approval_gate.decision)}</small></article><article><span>Registration</span><strong>{label(source.connector.registration_status)}</strong><small>{source.connector.connector_class || "not materialized"}</small></article><article><span>Activation</span><strong>{label(source.activation.status)}</strong><small>{source.search_profiles.active_profile_count}/{source.search_profiles.profile_count} profiles active</small></article><article><span>Ingestion / layers</span><strong>{label(source.last_ingestion.status)}</strong><small>Bronze {source.layers.bronze_count} · Silver {source.layers.silver_count}</small></article></section>
        <section className="source-bottom-grid"><article><span className="eyebrow">Evidence observed</span><h3>Repository / DB-backed signals</h3><p>Implementation, gate, profile, ingestion and layer truth are shown independently.</p></article><article><span className="eyebrow">Verified truth</span><h3>{source.inconsistencies.length ? "Lifecycle inconsistency detected" : "No readmodel inconsistency reported"}</h3>{source.inconsistencies.length ? <ul>{source.inconsistencies.map((item) => <li key={item}>{label(item)}</li>)}</ul> : <p className="muted-copy">Registration is not activation; historical data is not current source health.</p>}</article><article><span className="eyebrow">Uncertainty / hypothesis</span><h3>Never promoted to truth</h3><p>Unknown states remain unknown. No model hypothesis can complete a gate or activation step.</p></article></section>
        <section className="next-action-strip"><div><span className="eyebrow">Next safe action</span><strong>{source.next_action}</strong></div>{canFinalApprove ? <button className="primary-action" type="button" onClick={() => onReviewFinalApproval(source)}>Review final approval</button> : <button className="secondary-action" type="button" disabled>No reviewed write action here</button>}</section>
      </> : <p className="empty">No source is available.</p>}</main>
    </section>
  </div>;
}

function ApprovalsScreen({ payload, selectedSource, onSelectSource, onReviewFinalApproval }: { payload: ProductPayload; selectedSource: SourceConnector | null; onSelectSource: (source: SourceConnector) => void; onReviewFinalApproval: (source: SourceConnector) => void }) {
  const finalQueue = payload.source_connector_overview.sources.filter((source) => source.current_blocker === "final_approval_incomplete");
  const source = selectedSource && finalQueue.some((item) => item.candidate_id === selectedSource.candidate_id) ? selectedSource : finalQueue[0] || null;
  return <div className="page-stack approvals-page"><section className="page-toolbar"><div><span className="eyebrow">Human authority only</span><h1>Approvals</h1></div><div className="toolbar-note">Only actual approval gates appear here. Technical blockers stay in Sources.</div></section>
    <section className="approval-focus-grid"><article className="dashboard-card"><header className="card-heading-row"><div><span className="eyebrow">Final approval queue</span><h2>{finalQueue.length} waiting</h2></div></header><div className="approval-list">{finalQueue.map((item) => <button className={source?.candidate_id === item.candidate_id ? "selected" : ""} type="button" key={item.candidate_id} onClick={() => onSelectSource(item)}><span><b>{item.source_label}</b><small>{label(item.gates.connector_validation_gate.status)} validation · candidate #{item.candidate_id}</small></span><KindPill blocker={item.current_blocker} /></button>)}{finalQueue.length === 0 && <div className="honest-empty"><strong>No approval is waiting.</strong><p>The previous 63-count mixed technical blockers with approval work. This queue now reports authority decisions only.</p></div>}</div></article>
      <article className="dashboard-card approval-review-panel">{source ? <><span className="eyebrow">What we know</span><h2>{source.source_label}</h2><div className="approval-review-grid"><article><span>Validation</span><strong>{label(source.gates.connector_validation_gate.status)}</strong><small>{label(source.gates.connector_validation_gate.decision)}</small></article><article><span>Final approval</span><strong>{label(source.gates.final_approval_gate.status)}</strong><small>{label(source.gates.final_approval_gate.decision)}</small></article><article><span>Registration</span><strong>{label(source.connector.registration_status)}</strong><small>not implied by approval</small></article></div><section className="approval-decision-card"><div><span className="eyebrow">Why approval is needed</span><h3>Authority does not follow confidence</h3><p>{source.next_action}</p><small>Evidence may support a decision; it never grants authority by itself.</small></div><button className="primary-action large" type="button" onClick={() => onReviewFinalApproval(source)}>Open final approval review</button></section></> : <div className="honest-empty"><strong>Nothing to approve right now.</strong><p>Use Sources for technical, configuration, observability and operational blockers.</p></div>}</article>
      <aside className="dashboard-card product-gates-card"><span className="eyebrow">Product-level gates</span><h2>{payload.operator_blockers.length}</h2>{payload.operator_blockers.map((blocker) => <div className="product-gate" key={blocker.code}><b>{blocker.title}</b><small>{blocker.detail}</small></div>)}<div className="boundary-lines"><span><i className="ok" /> Final gate recording only</span><span><i /> No connector registration or activation</span><span><i /> No provider / ranking / application action</span></div></aside>
    </section></div>;
}

function OperationsScreen({ payload }: { payload: ProductPayload }) {
  const overview = payload.source_connector_overview;
  const stages = [ ["Known", overview.summary.source_count], ["Implemented", overview.summary.implemented_count], ["Validated", overview.summary.validated_count], ["Approved", overview.summary.final_approved_count], ["Registered", overview.summary.registered_count], ["Activated", overview.summary.active_count], ["Ingested", overview.summary.ingested_count] ] as Array<[string, number]>;
  const blockerGroups = Array.from(overview.sources.reduce((m, source) => { if (source.current_blocker) { const key = `${blockerKind(source.current_blocker)} · ${label(source.current_blocker)}`; m.set(key, (m.get(key) || 0) + 1); } return m; }, new Map<string, number>())).sort((a, b) => b[1] - a[1]);
  return <div className="page-stack operations-page"><section className="page-toolbar"><div><span className="eyebrow">System truth & runtime-facing state</span><h1>Operations</h1></div><div className="toolbar-note">Read-only observability · without invented telemetry</div></section>
    <section className="operations-grid"><article className="dashboard-card operations-wide"><header className="card-heading-row"><div><span className="eyebrow">Source & connector lifecycle</span><h2>Lifecycle map</h2></div></header><div className="pipeline-map">{stages.map(([name, value], index) => <div className="pipeline-stage" key={name}><div className="pipeline-stage-card"><span>{name}</span><strong>{value}</strong></div>{index < stages.length - 1 && <div className="pipeline-connector"><i /></div>}</div>)}</div><p className="truth-note">Registration is not activation. Historical Silver presence alone never qualifies a vacancy.</p></article>
      <article className="dashboard-card"><header className="card-heading-row"><div><span className="eyebrow">Product V1 jobs</span><h2>Lifecycle health</h2></div></header><div className="health-grid"><div><span>Current active</span><strong>{payload.summary.current_active_job_count}</strong></div><div><span>Stale / refresh</span><strong>{payload.summary.stale_job_count}</strong></div><div><span>Unverifiable</span><strong>{payload.summary.unverifiable_job_count}</strong></div><div><span>Inactive</span><strong>{payload.summary.inactive_confirmed_job_count}</strong></div></div></article>
      <article className="dashboard-card operations-wide"><header className="card-heading-row"><div><span className="eyebrow">Connector diagnosis</span><h2>What is blocking progress?</h2></div><strong>{overview.summary.attention_count}</strong></header><div className="blocker-table">{blockerGroups.map(([name, count]) => <div key={name}><span>{name}</span><strong>{count}</strong></div>)}</div></article>
      <article className="dashboard-card"><header className="card-heading-row"><div><span className="eyebrow">Deterministic scope rotation</span><h2>StepStone waves</h2></div><strong>{payload.wave_states.length}</strong></header><div className="wave-table">{payload.wave_states.slice(0, 8).map((wave) => <div key={wave.search_term}><span><b>{wave.search_term}</b><small>{wave.current_interval_days} day interval</small></span><StatusPill value={wave.is_not_exclusion_enabled ? "wave_enabled" : "baseline_only"} /><em>Wave {wave.current_exclusion_wave_index}</em></div>)}</div></article>
      <article className="dashboard-card"><header className="card-heading-row"><div><span className="eyebrow">Application preparation</span><h2>Source document readiness</h2></div></header><div className="application-readiness-grid"><div><span>Base CV</span><strong>{payload.application_sources_ready.base_cv ? "Approved" : "Required"}</strong></div><div><span>Base letter</span><strong>{payload.application_sources_ready.base_application_letter ? "Approved" : "Required"}</strong></div><div><span>Generation-ready jobs</span><strong>{payload.summary.application_ready_count}</strong></div></div><p className="truth-note">Draft generation is separate from application submission. No hidden auto-apply.</p></article>
    </section></div>;
}

export default function App() {
  const [payload, setPayload] = useState<ProductPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("jobs");
  const [selectedCandidateId, setSelectedCandidateId] = useState<number | null>(null);
  const [finalApprovalSource, setFinalApprovalSource] = useState<SourceConnector | null>(null);
  useEffect(() => { const controller = new AbortController(); readProductTruth(controller.signal).then(setPayload).catch((reason: unknown) => { if ((reason as Error).name !== "AbortError") setError(String(reason)); }); return () => controller.abort(); }, []);
  const refreshProductTruth = async () => { setPayload(await readProductTruth()); setError(null); };
  const selectedSource = useMemo(() => { const sources = payload?.source_connector_overview.sources || []; return sources.find((source) => source.candidate_id === selectedCandidateId) || sources.find((source) => Boolean(source.current_blocker)) || sources[0] || null; }, [payload, selectedCandidateId]);
  if (error) return <main className="fatal"><div className="fatal-card"><span className="eyebrow">Fail closed</span><h1>Control Center unavailable</h1><pre>{error}</pre></div></main>;
  if (!payload) return <main className="loading"><div className="sonar" /><p>Reading Deep Ocean product state…</p></main>;
  const finalApprovalCount = payload.source_connector_overview.sources.filter((source) => source.current_blocker === "final_approval_incomplete").length;
  return <div className="control-center-shell"><header className="topbar"><div className="topbar-brand"><div className="brand-mark"><span>DO</span></div><div><strong>Deep Ocean</strong><small>Intelligence</small></div></div><nav className="topnav" aria-label="Primary navigation">{([ ["jobs", "Jobs"], ["sources", "Sources"], ["approvals", "Approvals"], ["operations", "Operations"] ] as Array<[Tab, string]>).map(([id, text]) => <button type="button" className={tab === id ? "active" : ""} key={id} onClick={() => setTab(id)}>{text}{id === "approvals" && finalApprovalCount > 0 ? <span>{finalApprovalCount}</span> : null}</button>)}</nav><div className="topbar-status"><span className="truth-stamp"><i /> DB truth</span><button type="button" className="refresh-button" onClick={() => void refreshProductTruth()}>↻ Refresh</button></div></header><main className="app-main">{tab === "jobs" && <JobsScreen payload={payload} refreshProductTruth={refreshProductTruth} />}{tab === "sources" && <SourcesScreen payload={payload} selectedSource={selectedSource} onSelectSource={(source) => setSelectedCandidateId(source.candidate_id)} onReviewFinalApproval={setFinalApprovalSource} />}{tab === "approvals" && <ApprovalsScreen payload={payload} selectedSource={selectedSource} onSelectSource={(source) => setSelectedCandidateId(source.candidate_id)} onReviewFinalApproval={setFinalApprovalSource} />}{tab === "operations" && <OperationsScreen payload={payload} />}</main><FinalApprovalReviewDialog source={finalApprovalSource} refreshProductTruth={refreshProductTruth} onClose={() => setFinalApprovalSource(null)} /></div>;
}
