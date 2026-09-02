import { useEffect, useMemo, useState } from "react";
import JobReviewLabelControls, {
  type JobReviewLabelState,
} from "./JobReviewLabelControls";
import "./operator-workspace-v2.css";

type Job = {
  silver_job_id: number;
  product_rank?: number;
  title?: string | null;
  company_name?: string | null;
  display_company_name?: string | null;
  legal_entity_name?: string | null;
  city?: string | null;
  country?: string | null;
  publication_date?: string | null;
  source_url?: string | null;
  product_readiness_status?: string;
  lifecycle_status?: string;
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

type SourceConnector = {
  candidate_id: number | null;
  source_name: string;
  source_label: string;
  source_type: string;
  candidate_status: string;
  current_blocker?: string | null;
  next_action: string;
  connector: {
    implementation_status: string;
    registration_status: string;
  };
  activation: { status: string; active: boolean | null };
  search_profiles: { active_profile_count: number; profile_count: number };
  gates: {
    connector_validation_gate: { status: string; decision?: string | null };
    final_approval_gate: { status: string; decision?: string | null };
  };
  last_ingestion: { status: string; total_loaded: number; inserted_count: number };
  layers: { bronze_count: number; silver_count: number };
};

type ProductPayload = {
  summary: {
    observed_job_count: number;
    current_active_job_count: number;
    stale_job_count: number;
    inactive_confirmed_job_count: number;
    unverifiable_job_count: number;
    rankable_job_count: number;
    top_job_count: number;
    application_ready_count: number;
  };
  job_readiness: Job[];
  top_jobs: Job[];
  application_sources_ready: {
    base_cv: boolean;
    base_application_letter: boolean;
  };
  source_connector_overview: {
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
  };
  operator_blockers: Array<{ code: string; title: string; detail: string }>;
  review_label_capture?: {
    available: boolean;
  };
};

type View = "overview" | "jobs" | "top5" | "application" | "sources" | "approvals" | "operations";
type JobFilter = "current" | "unreviewed" | "interesting" | "not_relevant" | "rankable" | "all";

const normalize = (value: string | undefined | null) => (value || "").trim().toLocaleLowerCase();
const label = (value: string | undefined | null) => (value || "unknown").replaceAll("_", " ");
const scoreText = (value: number | null | undefined) => value == null ? "—" : `${Math.round(value)}%`;
const isCurrent = (job: Job) => ["active confirmed", "active_confirmed"].includes(normalize(job.lifecycle_status));
const employerName = (job: Job) => job.display_company_name || job.company_name || "Employer not resolved";
const locationText = (job: Job) => job.city || job.country || (normalize(job.work_model) === "remote" ? "Remote" : "Location not confirmed");

function tone(value: string | undefined | null) {
  const normalized = normalize(value);
  if (["rankable", "active", "active confirmed", "active_confirmed", "approved", "interesting", "passed"].includes(normalized)) return "good";
  if (normalized.includes("failed") || normalized.includes("blocked") || normalized === "not_relevant") return "bad";
  if (normalized.includes("required") || normalized.includes("unknown") || normalized.includes("stale") || normalized === "unsure") return "warn";
  return "neutral";
}

async function readProductTruth(signal?: AbortSignal): Promise<ProductPayload> {
  const response = await fetch("/api/v1/product-v1", {
    ...(signal ? { signal } : {}),
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`API returned ${response.status}`);
  return response.json() as Promise<ProductPayload>;
}

function Status({ value }: { value?: string | null }) {
  return <span className={`ow-status ${tone(value)}`}>{label(value)}</span>;
}

function Metric({ labelText, value, helper }: { labelText: string; value: number | string; helper: string }) {
  return <article className="ow-metric"><span>{labelText}</span><strong>{value}</strong><small>{helper}</small></article>;
}

function OpenApplicationButton({ disabled = false }: { disabled?: boolean }) {
  return <button
    type="button"
    className="ow-primary"
    disabled={disabled}
    onClick={() => window.dispatchEvent(new CustomEvent("product-v1:open-application-workspace"))}
  >Prepare application</button>;
}

function Overview({ payload, onNavigate }: { payload: ProductPayload; onNavigate: (view: View) => void }) {
  const currentJobs = payload.job_readiness.filter(isCurrent);
  const reviewed = payload.job_readiness.filter((job) => Boolean(job.review_label));
  const interesting = reviewed.filter((job) => job.review_label?.label === "interesting").length;
  const rejected = reviewed.filter((job) => job.review_label?.label === "not_relevant").length;
  const top = payload.top_jobs[0] || null;
  const docsReady = payload.application_sources_ready.base_cv && payload.application_sources_ready.base_application_letter;

  return <div className="ow-stack">
    <header className="ow-page-header">
      <div><span>Overall</span><h1>What matters now</h1><p>Current Product V1 truth, reduced to the next useful decisions.</p></div>
    </header>

    <section className="ow-metrics">
      <Metric labelText="Current jobs" value={currentJobs.length} helper="confirmed active" />
      <Metric labelText="Rankable" value={payload.summary.rankable_job_count} helper="hard gates passed" />
      <Metric labelText="Top 5" value={`${payload.summary.top_job_count}/5`} helper="authoritative shortlist" />
      <Metric labelText="Application ready" value={payload.summary.application_ready_count} helper="review draft context" />
    </section>

    <section className="ow-overview-grid">
      <article className="ow-card ow-now-card">
        <div className="ow-card-title"><div><span>Best current option</span><h2>{top ? top.title : "No rankable job yet"}</h2></div>{top && <strong>#{top.product_rank || 1}</strong>}</div>
        {top ? <>
          <p className="ow-job-meta">{employerName(top)} · {locationText(top)}</p>
          <div className="ow-fit-line"><b>{scoreText(top.overall_quality_score)}</b><span>profile fit</span></div>
          <div className="ow-actions"><button type="button" onClick={() => onNavigate("top5")}>Open Top 5</button>{top.source_url && <a href={top.source_url} target="_blank" rel="noreferrer">Original job ↗</a>}</div>
        </> : <p className="ow-muted">The UI will not manufacture a recommendation.</p>}
      </article>

      <article className="ow-card">
        <div className="ow-card-title"><div><span>Your feedback</span><h2>Relevance labels</h2></div><strong>{reviewed.length}</strong></div>
        <div className="ow-feedback-summary"><div><span>Interesting</span><b>{interesting}</b></div><div><span>Not relevant</span><b>{rejected}</b></div><div><span>Unreviewed</span><b>{payload.job_readiness.length - reviewed.length}</b></div></div>
        <p className="ow-muted">These labels build personal relevance evidence; they do not directly rewrite ranking.</p>
        <button type="button" className="ow-text-action" onClick={() => onNavigate("jobs")}>Review jobs →</button>
      </article>

      <article className="ow-card">
        <div className="ow-card-title"><div><span>Application</span><h2>{docsReady ? "Source documents ready" : "Source documents still required"}</h2></div></div>
        <div className="ow-readiness"><div className={payload.application_sources_ready.base_cv ? "ready" : "blocked"}><i /><span>Base CV</span><b>{payload.application_sources_ready.base_cv ? "Approved" : "Required"}</b></div><div className={payload.application_sources_ready.base_application_letter ? "ready" : "blocked"}><i /><span>Base letter</span><b>{payload.application_sources_ready.base_application_letter ? "Approved" : "Required"}</b></div></div>
        <button type="button" className="ow-text-action" onClick={() => onNavigate("application")}>Open application step →</button>
      </article>

      <article className="ow-card">
        <div className="ow-card-title"><div><span>Discovery health</span><h2>Remote is producing value</h2></div></div>
        <p>{payload.summary.current_active_job_count} current vacancies are in the product set. Remote Germany stays in scope while we finish Personio quality hardening before adding more local employers.</p>
        <div className="ow-actions"><button type="button" onClick={() => onNavigate("sources")}>Sources</button><button type="button" onClick={() => onNavigate("operations")}>Operations</button></div>
      </article>
    </section>
  </div>;
}

function JobDetail({ job, payload, refresh }: { job: Job; payload: ProductPayload; refresh: () => Promise<void> }) {
  return <aside className="ow-job-detail">
    <div className="ow-detail-head"><span>Silver #{job.silver_job_id}</span><h2>{job.title || "Untitled job"}</h2><p>{employerName(job)} · {locationText(job)}</p>{job.legal_entity_name && normalize(job.legal_entity_name) !== normalize(employerName(job)) && <small>Legal entity: {job.legal_entity_name}</small>}</div>
    <div className="ow-actions">{job.source_url && <a className="ow-primary-link" href={job.source_url} target="_blank" rel="noreferrer">Open original ↗</a>}{job.product_readiness_status === "rankable" && <OpenApplicationButton />}</div>
    <JobReviewLabelControls silverJobId={job.silver_job_id} currentLabel={job.review_label} captureAvailable={payload.review_label_capture?.available === true} refreshProductTruth={refresh} />
    <section className="ow-score-card"><h3>Profile fit</h3>{([ ["Overall", job.overall_quality_score], ["Profile direction", job.profile_direction_score], ["Data focus", job.data_focus_score], ["Reliability", job.reliability_focus_score], ["Evidence quality", job.evidence_quality_score] ] as Array<[string, number | null | undefined]>).map(([name, value]) => <div key={name}><span>{name}</span><i><b style={{ width: `${Math.max(0, Math.min(100, value || 0))}%` }} /></i><strong>{scoreText(value)}</strong></div>)}</section>
    <section className="ow-facts"><div><span>Lifecycle</span><Status value={job.lifecycle_status} /></div><div><span>Product gate</span><Status value={job.product_readiness_status} /></div><div><span>Work model</span><b>{label(job.work_model)}</b></div><div><span>Commute</span><b>{job.commute_minutes == null ? "—" : `${job.commute_minutes} min`}</b></div></section>
    <section className="ow-evidence"><div><span>Verified</span>{job.explanations?.length ? <ul>{job.explanations.map((item) => <li key={item}>{item}</li>)}</ul> : <p>No projected explanation evidence.</p>}</div><div><span>Unknown / review</span>{job.uncertainties?.length ? <ul>{job.uncertainties.map((item) => <li key={item}>{item}</li>)}</ul> : <p>No projected uncertainty.</p>}</div></section>
  </aside>;
}

function Jobs({ payload, refresh }: { payload: ProductPayload; refresh: () => Promise<void> }) {
  const [filter, setFilter] = useState<JobFilter>("current");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const filtered = useMemo(() => {
    const q = normalize(search);
    return payload.job_readiness.filter((job) => {
      if (filter === "current" && !isCurrent(job)) return false;
      if (filter === "unreviewed" && job.review_label) return false;
      if (filter === "interesting" && job.review_label?.label !== "interesting") return false;
      if (filter === "not_relevant" && job.review_label?.label !== "not_relevant") return false;
      if (filter === "rankable" && job.product_readiness_status !== "rankable") return false;
      if (q && !normalize(`${job.title} ${employerName(job)} ${job.city} ${job.country}`).includes(q)) return false;
      return true;
    });
  }, [filter, payload.job_readiness, search]);
  const selected = filtered.find((job) => job.silver_job_id === selectedId) || filtered[0] || null;
  const counts: Record<JobFilter, number> = {
    current: payload.job_readiness.filter(isCurrent).length,
    unreviewed: payload.job_readiness.filter((job) => !job.review_label).length,
    interesting: payload.job_readiness.filter((job) => job.review_label?.label === "interesting").length,
    not_relevant: payload.job_readiness.filter((job) => job.review_label?.label === "not_relevant").length,
    rankable: payload.job_readiness.filter((job) => job.product_readiness_status === "rankable").length,
    all: payload.job_readiness.length,
  };

  return <div className="ow-stack">
    <header className="ow-page-header"><div><span>Review surface</span><h1>All jobs</h1><p>Focused review list. Current vacancies first; historical/stale rows are available only when requested.</p></div></header>
    <section className="ow-job-toolbar">
      <div className="ow-filter-row">{([ ["current", "Current"], ["unreviewed", "Unreviewed"], ["interesting", "Interesting"], ["not_relevant", "Not relevant"], ["rankable", "Rankable"], ["all", "All observed"] ] as Array<[JobFilter, string]>).map(([id, text]) => <button type="button" key={id} className={filter === id ? "active" : ""} onClick={() => setFilter(id)}>{text}<b>{counts[id]}</b></button>)}</div>
      <label className="ow-search"><span>⌕</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Title, employer, location…" /></label>
    </section>
    <section className="ow-job-workspace">
      <div className="ow-job-list"><div className="ow-job-list-head"><span>Fit</span><span>Review</span><span>Job</span><span>Location</span><span>Gate</span></div>{filtered.map((job) => <button type="button" key={job.silver_job_id} className={selected?.silver_job_id === job.silver_job_id ? "selected" : ""} onClick={() => setSelectedId(job.silver_job_id)}><strong>{scoreText(job.overall_quality_score)}</strong><Status value={job.review_label?.label || "unreviewed"} /><span className="ow-job-name"><b>{job.title || "Untitled job"}</b><small>{employerName(job)}</small></span><span className="ow-location"><b>{locationText(job)}</b><small>{label(job.work_model)}</small></span><Status value={job.product_readiness_status} /></button>)}{filtered.length === 0 && <p className="ow-empty">No jobs match this filter.</p>}</div>
      {selected ? <JobDetail job={selected} payload={payload} refresh={refresh} /> : <aside className="ow-job-detail"><p className="ow-empty">Select a job.</p></aside>}
    </section>
  </div>;
}

function TopFive({ payload, refresh }: { payload: ProductPayload; refresh: () => Promise<void> }) {
  const [selectedId, setSelectedId] = useState<number | null>(payload.top_jobs[0]?.silver_job_id ?? null);
  const jobs = payload.top_jobs.slice(0, 5);
  const selected = jobs.find((job) => job.silver_job_id === selectedId) || jobs[0] || null;
  return <div className="ow-stack"><header className="ow-page-header"><div><span>Application shortlist</span><h1>Top 5</h1><p>Only authoritative rankable jobs. Empty slots stay empty.</p></div><strong className="ow-big-count">{jobs.length}/5</strong></header>
    {jobs.length ? <section className="ow-top5-workspace"><div className="ow-top5-list">{jobs.map((job, index) => <button type="button" key={job.silver_job_id} className={selected?.silver_job_id === job.silver_job_id ? "selected" : ""} onClick={() => setSelectedId(job.silver_job_id)}><span className="ow-rank">#{job.product_rank || index + 1}</span><span><b>{job.title}</b><small>{employerName(job)} · {locationText(job)}</small></span><strong>{scoreText(job.overall_quality_score)}</strong></button>)}</div>{selected && <JobDetail job={selected} payload={payload} refresh={refresh} />}</section> : <section className="ow-card"><h2>No Top-5 job currently qualifies.</h2><p>The product does not fill the shortlist with weaker or stale jobs.</p></section>}
  </div>;
}

function Application({ payload }: { payload: ProductPayload }) {
  const top = payload.top_jobs[0] || null;
  const docsReady = payload.application_sources_ready.base_cv && payload.application_sources_ready.base_application_letter;
  return <div className="ow-stack"><header className="ow-page-header"><div><span>Final product step</span><h1>Application</h1><p>Verified vacancy + Candidate Facts + approved base documents → review draft. Never auto-submit.</p></div></header>
    <section className="ow-application-grid"><article className="ow-card"><span className="ow-kicker">Selected target</span><h2>{top?.title || "No authoritative Top-5 job"}</h2>{top && <p>{employerName(top)} · {locationText(top)} · {scoreText(top.overall_quality_score)} fit</p>}<div className="ow-readiness"><div className={top ? "ready" : "blocked"}><i /><span>Top-5 target</span><b>{top ? "Ready" : "Required"}</b></div><div className={payload.application_sources_ready.base_cv ? "ready" : "blocked"}><i /><span>Base CV</span><b>{payload.application_sources_ready.base_cv ? "Approved" : "Required"}</b></div><div className={payload.application_sources_ready.base_application_letter ? "ready" : "blocked"}><i /><span>Base letter</span><b>{payload.application_sources_ready.base_application_letter ? "Approved" : "Required"}</b></div></div><OpenApplicationButton disabled={!top} /></article>
      <article className="ow-card ow-boundary-card"><span className="ow-kicker">Boundary</span><h2>{docsReady ? "Ready to bind full context" : "Documents still block generation"}</h2><p>Preparing a draft creates no application approval, submission or send authority. The final package remains <b>draft_for_review</b>.</p><ul><li>Current employer-origin vacancy</li><li>Approved Candidate Facts only</li><li>Base CV/letter are structure and style sources, not fact authority</li><li>No hidden auto-apply</li></ul></article></section>
  </div>;
}

function Sources({ payload }: { payload: ProductPayload }) {
  const [selectedName, setSelectedName] = useState(payload.source_connector_overview.sources.find((source) => source.current_blocker)?.source_name || payload.source_connector_overview.sources[0]?.source_name || "");
  const [showAll, setShowAll] = useState(false);
  const sources = payload.source_connector_overview.sources;
  const visible = showAll ? sources : sources.filter((source) => source.current_blocker || source.activation.active === true);
  const selected = sources.find((source) => source.source_name === selectedName) || visible[0] || null;
  return <div className="ow-stack"><header className="ow-page-header"><div><span>Source control</span><h1>Sources</h1><p>Connector detail stays available, but out of the main job-review workflow.</p></div><button type="button" className="ow-secondary" onClick={() => setShowAll((value) => !value)}>{showAll ? "Show active/attention" : "Show all sources"}</button></header>
    <section className="ow-source-workspace"><div className="ow-source-list">{visible.map((source) => <button type="button" key={source.source_name} className={selected?.source_name === source.source_name ? "selected" : ""} onClick={() => setSelectedName(source.source_name)}><span><b>{source.source_label}</b><small>{source.source_name}</small></span><Status value={source.current_blocker || source.activation.status} /></button>)}</div>{selected && <article className="ow-card ow-source-detail"><span className="ow-kicker">{selected.source_type}</span><h2>{selected.source_label}</h2><code>{selected.source_name}</code><div className="ow-source-facts"><div><span>Implementation</span><b>{label(selected.connector.implementation_status)}</b></div><div><span>Validation</span><b>{label(selected.gates.connector_validation_gate.status)}</b></div><div><span>Approval</span><b>{label(selected.gates.final_approval_gate.status)}</b></div><div><span>Activation</span><b>{label(selected.activation.status)}</b></div><div><span>Profiles</span><b>{selected.search_profiles.active_profile_count}/{selected.search_profiles.profile_count} active</b></div><div><span>Layers</span><b>Bronze {selected.layers.bronze_count} · Silver {selected.layers.silver_count}</b></div></div>{selected.current_blocker ? <div className="ow-callout warn"><b>{label(selected.current_blocker)}</b><span>{selected.next_action}</span></div> : <div className="ow-callout good"><b>No current blocker</b><span>{selected.next_action}</span></div>}</article>}</section>
  </div>;
}

function Approvals({ payload }: { payload: ProductPayload }) {
  const waiting = payload.source_connector_overview.sources.filter((source) => source.current_blocker === "final_approval_incomplete");
  return <div className="ow-stack"><header className="ow-page-header"><div><span>Human authority</span><h1>Approvals</h1><p>Only real authority decisions belong here. Technical work stays in Sources.</p></div><strong className="ow-big-count">{waiting.length}</strong></header><section className="ow-approval-grid"><article className="ow-card"><h2>{waiting.length ? "Final source approvals" : "Nothing waiting"}</h2>{waiting.length ? waiting.map((source) => <div className="ow-approval-row" key={source.source_name}><span><b>{source.source_label}</b><small>{source.next_action}</small></span><Status value="approval_required" /></div>) : <p className="ow-muted">No source approval decision is currently waiting.</p>}</article><article className="ow-card"><h2>Product-level gates</h2>{payload.operator_blockers.length ? payload.operator_blockers.map((blocker) => <div className="ow-approval-row" key={blocker.code}><span><b>{blocker.title}</b><small>{blocker.detail}</small></span></div>) : <p className="ow-muted">No product-level approval blocker.</p>}</article></section></div>;
}

function Operations({ payload }: { payload: ProductPayload }) {
  const overview = payload.source_connector_overview.summary;
  const stages: Array<[string, number]> = [["Known", overview.source_count], ["Implemented", overview.implemented_count], ["Validated", overview.validated_count], ["Approved", overview.final_approved_count], ["Registered", overview.registered_count], ["Active", overview.active_count], ["Ingested", overview.ingested_count]];
  return <div className="ow-stack"><header className="ow-page-header"><div><span>Runtime truth</span><h1>Operations</h1><p>Observability and lifecycle health, separated from daily job review.</p></div></header><section className="ow-card"><h2>Source lifecycle</h2><div className="ow-pipeline">{stages.map(([name, value]) => <div key={name}><span>{name}</span><strong>{value}</strong></div>)}</div></section><section className="ow-metrics"><Metric labelText="Current active" value={payload.summary.current_active_job_count} helper="vacancies" /><Metric labelText="Stale" value={payload.summary.stale_job_count} helper="refresh required" /><Metric labelText="Unverifiable" value={payload.summary.unverifiable_job_count} helper="not current truth" /><Metric labelText="Attention sources" value={overview.attention_count} helper="need action" /></section></div>;
}

const navItems: Array<{ id: View; label: string; glyph: string }> = [
  { id: "overview", label: "Overall", glyph: "◉" },
  { id: "jobs", label: "All jobs", glyph: "≡" },
  { id: "top5", label: "Top 5", glyph: "★" },
  { id: "application", label: "Application", glyph: "↗" },
  { id: "sources", label: "Sources", glyph: "⌁" },
  { id: "approvals", label: "Approvals", glyph: "✓" },
  { id: "operations", label: "Operations", glyph: "⌘" },
];

export default function OperatorWorkspace() {
  const [payload, setPayload] = useState<ProductPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>("overview");
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    readProductTruth(controller.signal).then(setPayload).catch((reason: unknown) => {
      if ((reason as Error).name !== "AbortError") setError(String(reason));
    });
    return () => controller.abort();
  }, []);

  const refresh = async () => {
    setRefreshing(true);
    try {
      setPayload(await readProductTruth());
      setError(null);
    } finally {
      setRefreshing(false);
    }
  };

  if (error) return <main className="ow-fatal"><div><span>Fail closed</span><h1>Control Center unavailable</h1><pre>{error}</pre></div></main>;
  if (!payload) return <main className="ow-loading"><div /><p>Reading Product V1 truth…</p></main>;

  const navBadges: Partial<Record<View, number>> = {
    jobs: payload.summary.current_active_job_count,
    top5: payload.summary.top_job_count,
    approvals: payload.source_connector_overview.sources.filter((source) => source.current_blocker === "final_approval_incomplete").length,
    sources: payload.source_connector_overview.summary.attention_count,
  };

  return <div className="ow-shell">
    <aside className="ow-sidebar">
      <div className="ow-brand"><div>DO</div><span><b>Deep Ocean</b><small>Intelligence</small></span></div>
      <nav aria-label="Primary navigation">{navItems.map((item, index) => <div key={item.id} className={index === 4 ? "ow-nav-break" : undefined}><button type="button" className={view === item.id ? "active" : ""} onClick={() => setView(item.id)}><i>{item.glyph}</i><span>{item.label}</span>{navBadges[item.id] != null && <b>{navBadges[item.id]}</b>}</button></div>)}</nav>
      <footer><span><i /> DB truth</span><small>Product V1 · review-first</small></footer>
    </aside>
    <div className="ow-content-shell">
      <header className="ow-topline"><div><b>{navItems.find((item) => item.id === view)?.label}</b><span>DEMO-001 · Personio pilot</span></div><button type="button" disabled={refreshing} onClick={() => void refresh()}>{refreshing ? "Refreshing…" : "↻ Refresh"}</button></header>
      <main className="ow-main">{view === "overview" && <Overview payload={payload} onNavigate={setView} />}{view === "jobs" && <Jobs payload={payload} refresh={refresh} />}{view === "top5" && <TopFive payload={payload} refresh={refresh} />}{view === "application" && <Application payload={payload} />}{view === "sources" && <Sources payload={payload} />}{view === "approvals" && <Approvals payload={payload} />}{view === "operations" && <Operations payload={payload} />}</main>
    </div>
  </div>;
}
