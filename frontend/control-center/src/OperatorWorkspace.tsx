import { useEffect, useMemo, useState } from "react";
import ApplicationSourceUpload from "./ApplicationSourceUpload";
import JobReviewLabelControls, {
  type JobReviewLabelState,
} from "./JobReviewLabelControls";
import F5ApplicationTracking, { type F5ProductPayload } from "./F5ApplicationTracking";
import { useProductTruth } from "./ProductTruthContext";
import "./operator-workspace-v2.css";
import "./operator-demo-hardening.css";

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
  first_jap_observed_at?: string | null;
  source_url?: string | null;
  discovery_source_url?: string | null;
  product_readiness_status?: string;
  lifecycle_status?: string;
  origin_validation_status?: string;
  hard_filter_status?: string;
  overall_quality_score?: number | null;
  product_overall_quality_score?: number | null;
  display_fit_score?: number | null;
  display_fit_scope?: string | null;
  profile_direction_score?: number | null;
  data_focus_score?: number | null;
  reliability_focus_score?: number | null;
  evidence_quality_score?: number | null;
  work_model?: string;
  commute_minutes?: number | null;
  explanations?: string[];
  uncertainties?: string[];
  profile_fit_coverage_status?: string;
  profile_fit_decision?: string;
  profile_fit_reason?: string;
  profile_fit_factors?: Record<string, { status: string; reason: string }>;
  profile_fit_missing_factors?: string[];
  profile_fit_failed_factors?: string[];
  review_label?: JobReviewLabelState | null;
  demo_live_verified?: boolean;
  demo_live_reason?: string | null;
  last_health_checked_at?: string | null;
  latest_health_observed_at?: string | null;
};

type SourceConnector = {
  candidate_id: number | null;
  source_name: string;
  source_label: string;
  source_type: string;
  source_role: string;
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

type ApplicationStage = "prepared" | "applied" | "reply" | "interview" | "offer" | "closed";
type VacancyRevalidationPayload = {
  status?: "active" | "closed" | "unverifiable" | "blocked";
  outcome?: string;
  reason?: string;
  silver_job_id?: number;
  vacancy_revalidation_http_gets?: number;
  database_writes?: number;
  lifecycle_health_observation_writes?: number;
};
type LinkedApplication = {
  application_id?: number;
  silver_job_id?: number | null;
  effective_stage: ApplicationStage;
  observed_at?: string | null;
  linkage_status?: "persisted" | "exact_projected";
  linkage_basis?: string;
};

type ProductPayload = {
  summary: {
    observed_job_count: number;
    current_active_job_count: number;
    review_scope_current_active_job_count?: number;
    profile_fit_complete_count?: number;
    profile_fit_insufficient_evidence_count?: number;
    profile_fit_unclassified_count?: number;
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
  f6_template_authority?: {
    status?: string;
    layout_policy?: string;
    legacy_template_authority?: boolean;
    templates?: Array<{
      template_id?: string;
      document_type?: string;
      canonical_filename?: string;
      sha256?: string;
      page_count?: number;
      page_format?: string[];
      editable_text_zone_count?: number;
      exact_authority_match?: boolean;
    }>;
  };
  source_connector_overview: {
    summary: {
      source_count: number;
      sensor_count: number;
      healthy_sensor_count: number;
      employer_origin_count: number;
      employer_origin_active_count: number;
      active_last_run_loaded_count: number;
      active_last_run_zero_count: number;
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
  application_tracking?: {
    available: boolean;
    applications: LinkedApplication[];
    job_linkage?: {
      read_only: boolean;
      exact_matches: LinkedApplication[];
      exact_match_count: number;
      unresolved_count: number;
      database_writes: number;
      authoritative_lifecycle_mutations: number;
    };
  };
  review_label_capture?: {
    available: boolean;
  };
};

type View = "overview" | "jobs" | "top5" | "application" | "applications" | "sources" | "operations";
type JobFilter = "unreviewed" | "interesting" | "not_relevant" | "rankable" | "applied" | "all";
type JobSort =
  | "newest"
  | "oldest"
  | "observed_newest"
  | "observed_oldest"
  | "fit_desc"
  | "fit_asc"
  | "review_asc"
  | "review_desc"
  | "job_asc"
  | "job_desc"
  | "location_asc"
  | "location_desc"
  | "gate_asc"
  | "gate_desc";
type SortColumn = "fit" | "review" | "job" | "location" | "published" | "observed" | "gate";
type SourceGroup = "Needs attention" | "Delivering now" | "Active, 0 current jobs" | "Market sensors" | "Pending" | "Not implemented";
type SourceTab = "All" | SourceGroup;

function downloadBase64Document(contentBase64: string, filename: string, mimeType: string) {
  const binary = atob(contentBase64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  const url = URL.createObjectURL(new Blob([bytes], { type: mimeType }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

const normalize = (value: string | undefined | null) => (value || "").trim().toLocaleLowerCase();
const label = (value: string | undefined | null) => (value || "unknown").replaceAll("_", " ");
const scoreText = (value: number | null | undefined) => value == null ? "—" : `${Math.round(value)}%`;
const hasPersistedActiveLifecycle = (job: Job) =>
  ["active confirmed", "active_confirmed"].includes(normalize(job.lifecycle_status));

const isCurrent = (job: Job) => hasPersistedActiveLifecycle(job);
const isRankable = (job: Job) => normalize(job.product_readiness_status) === "rankable";
const employerName = (job: Job) => job.display_company_name || job.company_name || "Employer not resolved";
const locationText = (job: Job) => job.city || job.country || (normalize(job.work_model) === "remote" ? "Remote" : "Location not confirmed");
const reviewText = (job: Job) => job.review_label?.label || "unreviewed";
const gateText = (job: Job) => job.product_readiness_status || "unknown";
const applicationStageLabel: Record<ApplicationStage, string> = {
  prepared: "Detected",
  applied: "Applied",
  reply: "Reply",
  interview: "Interview",
  offer: "Offer",
  closed: "Closed",
};
const isAppliedStage = (stage: ApplicationStage) => stage !== "prepared";
const canPrepareApplication = (stage: ApplicationStage | null | undefined) =>
  stage == null || stage === "prepared";

const fitFactorLabel: Record<string, string> = {
  geography_work_model_commute: "location / work model",
  skills_capabilities: "capability evidence",
  seniority: "seniority evidence",
  hard_requirements: "hard requirements",
};

function candidateFitText(job: Job) {
  const decision = normalize(job.profile_fit_decision);
  if (decision === "passed") return "Fit confirmed";
  if (decision === "failed") return "Fit conflict";
  const missing = (job.profile_fit_missing_factors || [])
    .map((item) => fitFactorLabel[item] || label(item));
  if (missing.length) return `Needs ${missing.join(", ")}`;
  return "Fit evidence incomplete";
}

function top5ReadinessText(job: Job) {
  const value = normalize(job.product_readiness_status);
  if (value === "rankable") return "Ready for Top 5";
  if (value === "assessment_required") return "Job assessment needed";
  if (value === "hard_filter_evidence_required") return "Requirements evidence needed";
  if (value === "hard_filter_failed" || value === "blocked") return "Blocked by requirements";
  if (value === "ranking_required") return "Ranking review needed";
  return "More evidence needed";
}

function sourceGroupDisplay(group: SourceGroup) {
  return ({
    "Needs attention": "Needs attention",
    "Delivering now": "Delivering jobs",
    "Active, 0 current jobs": "Active · no current jobs",
    "Market sensors": "Market discovery",
    "Pending": "Setup pending",
    "Not implemented": "Not connected",
  } as Record<SourceGroup, string>)[group];
}

function sourcePurpose(source: SourceConnector) {
  return normalize(source.source_role) === "sensor" ? "Employer discovery" : "Job delivery";
}

function buildApplicationByJobId(payload: ProductPayload): Map<number, LinkedApplication> {
  const linked = new Map<number, LinkedApplication>();
  for (const application of payload.application_tracking?.applications || []) {
    if (typeof application.silver_job_id === "number") {
      linked.set(application.silver_job_id, {
        ...application,
        linkage_status: "persisted",
      });
    }
  }
  for (const application of payload.application_tracking?.job_linkage?.exact_matches || []) {
    if (
      typeof application.silver_job_id === "number" &&
      !linked.has(application.silver_job_id)
    ) {
      linked.set(application.silver_job_id, {
        ...application,
        linkage_status: "exact_projected",
      });
    }
  }
  return linked;
}

function externalJobUrl(job: Job): string | null {
  // Product/application authority still uses the guarded source_url. For review
  // navigation only, fall back to the exact Silver discovery URL when the old
  // demo-origin guard intentionally withholds an application-authoritative URL.
  const raw = (job.source_url || job.discovery_source_url || "").trim();
  if (!raw) return null;
  if (raw.startsWith("https://") || raw.startsWith("http://")) return raw;
  if (raw.startsWith("ba://")) {
    const reference = raw.slice("ba://".length).trim();
    return reference
      ? `https://www.arbeitsagentur.de/jobsuche/jobdetail/${encodeURIComponent(reference)}`
      : null;
  }
  return null;
}

const publicationTime = (job: Job) => {
  if (!job.publication_date) return null;
  const value = Date.parse(job.publication_date);
  return Number.isNaN(value) ? null : value;
};

const observedTime = (job: Job) => {
  if (!job.first_jap_observed_at) return null;
  const value = Date.parse(job.first_jap_observed_at);
  return Number.isNaN(value) ? null : value;
};

const displayDate = (value: string | null | undefined) => {
  if (!value) return "—";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Intl.DateTimeFormat("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(parsed));
};

const compareText = (left: string, right: string) => left.localeCompare(right, "de", { sensitivity: "base" });

function compareJobs(a: Job, b: Job, sort: JobSort) {
  if (sort === "fit_desc" || sort === "fit_asc") {
    const aFit = a.overall_quality_score ?? -1;
    const bFit = b.overall_quality_score ?? -1;
    const fitDelta = sort === "fit_desc" ? bFit - aFit : aFit - bFit;
    if (fitDelta !== 0) return fitDelta;
  }

  if (sort === "review_asc" || sort === "review_desc") {
    const delta = compareText(reviewText(a), reviewText(b));
    if (delta !== 0) return sort === "review_asc" ? delta : -delta;
  }

  if (sort === "job_asc" || sort === "job_desc") {
    const delta = compareText(`${a.title || ""} ${employerName(a)}`, `${b.title || ""} ${employerName(b)}`);
    if (delta !== 0) return sort === "job_asc" ? delta : -delta;
  }

  if (sort === "location_asc" || sort === "location_desc") {
    const delta = compareText(locationText(a), locationText(b));
    if (delta !== 0) return sort === "location_asc" ? delta : -delta;
  }

  if (sort === "gate_asc" || sort === "gate_desc") {
    const delta = compareText(gateText(a), gateText(b));
    if (delta !== 0) return sort === "gate_asc" ? delta : -delta;
  }

  if (sort === "observed_newest" || sort === "observed_oldest") {
    const aObserved = observedTime(a);
    const bObserved = observedTime(b);
    if (aObserved == null && bObserved != null) return 1;
    if (aObserved != null && bObserved == null) return -1;
    if (aObserved != null && bObserved != null) {
      const delta = sort === "observed_oldest" ? aObserved - bObserved : bObserved - aObserved;
      if (delta !== 0) return delta;
    }
  }

  const aDate = publicationTime(a);
  const bDate = publicationTime(b);

  if (aDate == null && bDate != null) return 1;
  if (aDate != null && bDate == null) return -1;

  if (aDate != null && bDate != null) {
    const dateDelta = sort === "oldest" ? aDate - bDate : bDate - aDate;
    if (dateDelta !== 0) return dateDelta;
  }

  return b.silver_job_id - a.silver_job_id;
}

function tone(value: string | undefined | null) {
  const normalized = normalize(value);
  if (["rankable", "active", "active confirmed", "active_confirmed", "approved", "interesting", "passed", "profile_fit_complete", "fresh"].includes(normalized) || normalized.startsWith("active_last_run_")) return "good";
  if (normalized.includes("failed") || normalized.includes("blocked") || normalized.includes("rejected") || normalized === "not_relevant") return "bad";
  if (normalized.includes("stale") || normalized.includes("ambiguous") || normalized === "unsure") return "warn";
  if (normalized.includes("required") || normalized.includes("unknown") || normalized.includes("insufficient")) return "pending";
  return "neutral";
}

function Status({ value }: { value?: string | null }) {
  return <span className={`ow-status ${tone(value)}`}>{label(value)}</span>;
}

function Metric({ labelText, value, helper }: { labelText: string; value: number | string; helper: string }) {
  return <article className="ow-metric"><span>{labelText}</span><strong>{value}</strong><small>{helper}</small></article>;
}

function OpenApplicationButton({
  disabled = false,
  silverJobId,
}: {
  disabled?: boolean;
  silverJobId?: number;
}) {
  return <button
    type="button"
    className="ow-primary"
    disabled={disabled}
    onClick={() => window.dispatchEvent(new CustomEvent(
      "product-v1:open-application-workspace",
      { detail: silverJobId ? { silverJobId } : {} },
    ))}
  >Prepare application</button>;
}

function Overview({ payload, onNavigate }: { payload: ProductPayload; onNavigate: (view: View) => void }) {
  const currentJobs = payload.job_readiness.filter(isCurrent);
  const reviewed = payload.job_readiness.filter((job) => Boolean(job.review_label));
  const interesting = reviewed.filter((job) => job.review_label?.label === "interesting").length;
  const rejected = reviewed.filter((job) => job.review_label?.label === "not_relevant").length;
  const top = payload.top_jobs.find(isCurrent) || null;
  const docsReady = payload.application_sources_ready.base_cv && payload.application_sources_ready.base_application_letter;
  const topUrl = top ? externalJobUrl(top) : null;

  return <div className="ow-stack">
    <header className="ow-page-header">
      <div><span>Overview</span><h1>What matters now</h1><p>Your current jobs, fit evidence and next useful actions at a glance.</p></div>
    </header>

    <section className="ow-metrics">
      <Metric labelText="Current jobs" value={currentJobs.length} helper="currently active jobs from verified employer sources" />
      <Metric labelText="Candidate Fit complete" value={payload.summary.profile_fit_complete_count ?? 0} helper="jobs with enough evidence for a fit decision" />
      <Metric labelText="Needs fit evidence" value={payload.summary.profile_fit_insufficient_evidence_count ?? 0} helper="jobs still missing evidence for a fit decision" />
      <Metric labelText="Ready to rank" value={payload.summary.rankable_job_count} helper="jobs that passed all required checks" />
      <Metric labelText="Top 5" value={`${payload.summary.top_job_count}/5`} helper="current shortlist" />
      <Metric labelText="Ready to prepare" value={payload.summary.application_ready_count} helper="shortlisted jobs ready for document preparation" />
    </section>

    <section className="ow-overview-grid">
      <article className="ow-card ow-now-card">
        <div className="ow-card-title"><div><span>Best current option</span><h2>{top ? top.title : "No rankable job yet"}</h2></div>{top && <strong>#{top.product_rank || 1}</strong>}</div>
        {top ? <>
          <p className="ow-job-meta">{employerName(top)} · {locationText(top)}</p>
          <div className="ow-fit-line"><b>{scoreText(top.overall_quality_score)}</b><span>overall match score</span></div>
          <div className="ow-actions"><button type="button" onClick={() => onNavigate("top5")}>Open Top 5</button>{topUrl && <a href={topUrl} target="_blank" rel="noreferrer">Original job ↗</a>}</div>
        </> : <p className="ow-muted">No job has enough verified evidence for the shortlist yet.</p>}
      </article>

      <article className="ow-card">
        <div className="ow-card-title"><div><span>Your feedback</span><h2>Relevance labels</h2></div><strong>{reviewed.length}</strong></div>
        <div className="ow-feedback-summary"><div><span>Interesting</span><b>{interesting}</b></div><div><span>Not relevant</span><b>{rejected}</b></div><div><span>Unreviewed</span><b>{payload.job_readiness.length - reviewed.length}</b></div></div>
        <p className="ow-muted">Your labels capture what interests you. Candidate Fit is assessed separately from your preference.</p>
        <button type="button" className="ow-text-action" onClick={() => onNavigate("jobs")}>Review jobs →</button>
      </article>

      <article className="ow-card">
        <div className="ow-card-title"><div><span>Application Builder</span><h2>{docsReady ? "Source documents ready" : "Source documents needed"}</h2></div></div>
        <div className="ow-readiness"><div className={payload.application_sources_ready.base_cv ? "ready" : "blocked"}><i /><span>CV</span><b>{payload.application_sources_ready.base_cv ? "Ready" : "Required"}</b></div><div className={payload.application_sources_ready.base_application_letter ? "ready" : "blocked"}><i /><span>Cover letter</span><b>{payload.application_sources_ready.base_application_letter ? "Ready" : "Required"}</b></div></div>
        <button type="button" className="ow-text-action" onClick={() => onNavigate("application")}>Open Application Builder →</button>
      </article>

      <article className="ow-card">
        <div className="ow-card-title"><div><span>Job discovery</span><h2>Current coverage</h2></div></div>
        <p>{currentJobs.length} active jobs from verified employer sources are currently available for review. Discovery channels continue to expand employer coverage in the background.</p>
        <div className="ow-actions"><button type="button" onClick={() => onNavigate("sources")}>Sources</button><button type="button" onClick={() => onNavigate("applications")}>Application Tracker</button></div>
      </article>
    </section>
  </div>;
}

function JobDetail({ job, payload, refresh, applicationStage, onOpenApplications }: { job: Job; payload: ProductPayload; refresh: () => Promise<void>; applicationStage?: ApplicationStage | null; onOpenApplications?: () => void }) {
  const sourceUrl = externalJobUrl(job);
  const [liveCheck, setLiveCheck] = useState<{
    status: "idle" | "checking" | "active" | "closed" | "unverifiable" | "error";
    reason?: string;
  }>({ status: "idle" });

  useEffect(() => {
    if (!hasPersistedActiveLifecycle(job)) {
      setLiveCheck({ status: "idle" });
      return;
    }

    let mounted = true;
    setLiveCheck({ status: "checking" });
    void fetch("/api/v1/product-v1/application-workspace/revalidate", {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({
        action: "revalidate_selected_vacancy",
        silver_job_id: job.silver_job_id,
      }),
    })
      .then(async (response) => {
        const payload = await response.json() as VacancyRevalidationPayload;
        if (!mounted) return;
        if (!response.ok) {
          setLiveCheck({
            status: "error",
            reason: payload.reason || `live check returned ${response.status}`,
          });
          return;
        }

        const status = payload.status || "unverifiable";
        setLiveCheck({
          status: status === "active"
            ? "active"
            : status === "closed"
              ? "closed"
              : "unverifiable",
          reason: payload.reason,
        });
        if (status === "closed") {
          await refresh().catch(() => undefined);
        }
      })
      .catch((reason: unknown) => {
        if (mounted) {
          setLiveCheck({ status: "error", reason: String(reason) });
        }
      });

    return () => { mounted = false; };
  }, [job.silver_job_id, job.lifecycle_status, refresh]);

  const rankable = isRankable(job);
  const profileFitFactors = job.profile_fit_factors || {};
  const profileFitFactorRows = [
    ["Geography / work model / commute", profileFitFactors.geography_work_model_commute?.status],
    ["Skills / capabilities", profileFitFactors.skills_capabilities?.status],
    ["Seniority", profileFitFactors.seniority?.status],
    ["Hard requirements", profileFitFactors.hard_requirements?.status],
  ] as Array<[string, string | undefined]>;
  const scoreRows = rankable
    ? ([
        ["Overall", job.overall_quality_score],
        ["Profile direction", job.profile_direction_score],
        ["Data focus", job.data_focus_score],
        ["Reliability", job.reliability_focus_score],
        ["Evidence quality", job.evidence_quality_score],
      ] as Array<[string, number | null | undefined]>)
    : ([ ["Role affinity", job.overall_quality_score] ] as Array<[string, number | null | undefined]>);

  return <aside className="ow-job-detail">
    <div className="ow-detail-head"><span>Job #{job.silver_job_id}</span><h2>{job.title || "Untitled job"}</h2><p>{employerName(job)} · {locationText(job)}</p>{job.legal_entity_name && normalize(job.legal_entity_name) !== normalize(employerName(job)) && <small>Legal entity: {job.legal_entity_name}</small>}</div>
    <div className="ow-actions">{sourceUrl && <a className="ow-primary-link" href={sourceUrl} target="_blank" rel="noreferrer">Open original ↗</a>}{hasPersistedActiveLifecycle(job) && job.hard_filter_status !== "failed" && canPrepareApplication(applicationStage) && <OpenApplicationButton silverJobId={job.silver_job_id} disabled={liveCheck.status === "checking"} />}{applicationStage && onOpenApplications && <button type="button" onClick={onOpenApplications}>Open Application Tracker</button>}</div>
    <JobReviewLabelControls silverJobId={job.silver_job_id} currentLabel={job.review_label} captureAvailable={payload.review_label_capture?.available === true} refreshProductTruth={refresh} />
    <section className="ow-facts"><div><span>Candidate fit</span><b>{candidateFitText(job)}</b></div><div><span>Fit evidence</span><Status value={job.profile_fit_coverage_status === "profile_fit_complete" ? "complete" : "incomplete"} /></div>{profileFitFactorRows.map(([name, value]) => <div key={name}><span>{name}</span><Status value={value || "unknown"} /></div>)}</section>
    <section className="ow-score-card"><h3>{rankable ? "Match score" : "Role affinity · preliminary"}</h3>{scoreRows.map(([name, value]) => <div key={name}><span>{name}</span><i><b style={{ width: `${Math.max(0, Math.min(100, value || 0))}%` }} /></i><strong>{scoreText(value)}</strong></div>)}{!rankable && <p className="ow-score-note">More job-detail evidence is needed before this can become Candidate Fit or a ranking score.</p>}</section>
    <section className="ow-facts"><div><span>Lifecycle</span><Status value={job.lifecycle_status} /></div><div><span>Live availability</span><Status value={liveCheck.status === "checking" ? "checking" : liveCheck.status === "idle" ? "not checked" : liveCheck.status} /></div><div><span>Top 5 readiness</span><b>{top5ReadinessText(job)}</b></div><div><span>Application</span>{applicationStage ? <b className={`ow-application-status ${applicationStage}`}>{applicationStageLabel[applicationStage]}</b> : <b>—</b>}</div><div><span>Work model</span><b>{label(job.work_model)}</b></div><div><span>Commute</span><b>{job.commute_minutes == null ? "—" : `${job.commute_minutes} min`}</b></div><div><span>Published</span><b>{displayDate(job.publication_date)}</b></div><div><span>First JAP observed</span><b>{displayDate(job.first_jap_observed_at)}</b></div></section>
    <section className="ow-evidence"><div><span>Verified</span>{job.explanations?.length ? <ul>{job.explanations.map((item) => <li key={item}>{item}</li>)}</ul> : <p>No verified explanation available yet.</p>}</div><div><span>Unknown / review</span>{job.uncertainties?.length ? <ul>{job.uncertainties.map((item) => <li key={item}>{item}</li>)}</ul> : <p>No unresolved fit question recorded.</p>}</div></section>
  </aside>;
}

function Jobs({
  payload,
  refresh,
  selectedJobId,
  onSelectJob,
  onOpenApplication,
}: {
  payload: ProductPayload;
  refresh: () => Promise<void>;
  selectedJobId: number | null;
  onSelectJob: (silverJobId: number) => void;
  onOpenApplication: (applicationId: number | null) => void;
}) {
  const [filter, setFilter] = useState<JobFilter>("all");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<JobSort>("fit_desc");

  useEffect(() => {
    if (selectedJobId == null) return;
    setFilter("all");
    setSearch("");
  }, [selectedJobId]);
  const applicationByJobId = useMemo(
    () => buildApplicationByJobId(payload),
    [
      payload.application_tracking?.applications,
      payload.application_tracking?.job_linkage?.exact_matches,
    ],
  );

  const filtered = useMemo(() => {
    const q = normalize(search);

    return payload.job_readiness
      .filter((job) => {
        if (filter === "unreviewed" && job.review_label) return false;
        if (filter === "interesting" && job.review_label?.label !== "interesting") return false;
        if (filter === "not_relevant" && job.review_label?.label !== "not_relevant") return false;
        if (filter === "rankable" && job.product_readiness_status !== "rankable") return false;
        if (filter === "applied") {
          const application = applicationByJobId.get(job.silver_job_id);
          if (!application || !isAppliedStage(application.effective_stage)) return false;
        }
        if (
          q &&
          !normalize(
            `${job.title} ${employerName(job)} ${job.city} ${job.country}`
          ).includes(q)
        ) return false;
        return true;
      })
      .sort((a, b) => compareJobs(a, b, sort));
  }, [applicationByJobId, filter, payload.job_readiness, search, sort]);

  const selected =
    filtered.find((job) => job.silver_job_id === selectedJobId) ||
    filtered[0] ||
    null;

  const counts: Record<JobFilter, number> = {
    unreviewed: payload.job_readiness.filter((job) => !job.review_label).length,
    interesting: payload.job_readiness.filter(
      (job) => job.review_label?.label === "interesting"
    ).length,
    not_relevant: payload.job_readiness.filter(
      (job) => job.review_label?.label === "not_relevant"
    ).length,
    rankable: payload.job_readiness.filter(
      (job) => job.product_readiness_status === "rankable"
    ).length,
    applied: payload.job_readiness.filter((job) => {
      const application = applicationByJobId.get(job.silver_job_id);
      return Boolean(application && isAppliedStage(application.effective_stage));
    }).length,
    all: payload.job_readiness.length,
  };

  const sortFor = (column: SortColumn): [JobSort, JobSort] => {
    if (column === "fit") return ["fit_desc", "fit_asc"];
    if (column === "review") return ["review_asc", "review_desc"];
    if (column === "job") return ["job_asc", "job_desc"];
    if (column === "location") return ["location_asc", "location_desc"];
    if (column === "observed") return ["observed_newest", "observed_oldest"];
    if (column === "gate") return ["gate_asc", "gate_desc"];
    return ["newest", "oldest"];
  };

  const sortHeader = (column: SortColumn, text: string) => {
    const [first, second] = sortFor(column);
    const active = sort === first || sort === second;
    return <button
      type="button"
      className={active ? "active" : ""}
      onClick={() => setSort(sort === first ? second : first)}
      title={`Sort by ${text}`}
    >{text}</button>;
  };

  return <div className="ow-stack">
    <header className="ow-page-header">
      <div>
        <span>Review surface</span>
        <h1>All Jobs</h1>
        <p>
          Current employer-origin vacancies only. Market sensors and historical jobs remain auditable outside this review list.
          A real Profile Fit exists only after detail evidence, capability fit and hard gates.
        </p>
      </div>
    </header>

    <section className="ow-job-toolbar">
      <div className="ow-filter-row">
        {([
          ["all", "All Jobs"],
          ["unreviewed", "Unreviewed"],
          ["interesting", "Interesting"],
          ["not_relevant", "Not relevant"],
          ["rankable", "Rankable"],
          ["applied", "Applied"],
        ] as Array<[JobFilter, string]>).map(([id, text]) =>
          <button
            type="button"
            key={id}
            className={filter === id ? "active" : ""}
            onClick={() => setFilter(id)}
          >
            {text}<b>{counts[id]}</b>
          </button>
        )}
      </div>

      <div className="ow-toolbar-controls">
        <label className="ow-search">
          <span>⌕</span>
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Title, employer, location…"
          />
        </label>

        <label className="ow-sort">
          <span>Sort</span>
          <select
            value={sort}
            onChange={(event) => setSort(event.target.value as JobSort)}
          >
            <option value="newest">Published newest</option>
            <option value="oldest">Published oldest</option>
            <option value="observed_newest">First observed newest</option>
            <option value="observed_oldest">First observed oldest</option>
            <option value="fit_desc">Affinity high → low</option>
            <option value="fit_asc">Affinity low → high</option>
            <option value="review_asc">Review A → Z</option>
            <option value="job_asc">Job A → Z</option>
            <option value="location_asc">Location A → Z</option>
            <option value="gate_asc">Candidate Fit A → Z</option>
          </select>
        </label>
      </div>
    </section>

    <section className="ow-job-workspace">
      <div className="ow-job-list">
        <div className="ow-job-list-head">
          {sortHeader("fit", "Affinity")}
          {sortHeader("review", "Review")}
          {sortHeader("job", "Job")}
          {sortHeader("location", "Location")}
          {sortHeader("published", "Published")}
          {sortHeader("observed", "First JAP observed")}
          {sortHeader("gate", "Candidate Fit")}
          <span>Application</span>
        </div>

        {filtered.map((job) => {
          const linkedApplication = applicationByJobId.get(job.silver_job_id);
          const applicationActive = Boolean(
            linkedApplication &&
            ["applied", "reply", "interview", "offer"].includes(linkedApplication.effective_stage),
          );
          const applicationClosed = linkedApplication?.effective_stage === "closed";
          return <button
            type="button"
            key={job.silver_job_id}
            className={[
              selected?.silver_job_id === job.silver_job_id ? "selected" : "",
              applicationActive ? "application-active" : "",
              applicationClosed ? "application-closed" : "",
            ].filter(Boolean).join(" ")}
            onClick={() => onSelectJob(job.silver_job_id)}
          >
            <strong title={isRankable(job) ? "Verified ranking score" : "Role affinity only · more fit evidence needed"}>{scoreText(job.overall_quality_score)}</strong>
            <Status value={job.review_label?.label || "unreviewed"} />

            <span className="ow-job-name">
              <b>{job.title || "Untitled job"}</b>
              <small>{employerName(job)}</small>
            </span>

            <span className="ow-location">
              <b>{locationText(job)}</b>
              <small>{label(job.work_model)}</small>
            </span>

            <span className="ow-published">
              {displayDate(job.publication_date)}
            </span>

            <span className="ow-observed">
              {displayDate(job.first_jap_observed_at)}
            </span>

            <span className="ow-gate-state"><span className="ow-fit-summary">{candidateFitText(job)}</span><small>{top5ReadinessText(job)}</small></span>

            {linkedApplication
              ? <span
                  className={`ow-application-status linked ${linkedApplication.effective_stage}`}
                  onClick={(event) => {
                    event.stopPropagation();
                    onOpenApplication(linkedApplication.application_id ?? null);
                  }}
                  title={linkedApplication.linkage_status === "exact_projected"
                    ? "Exactly matched from mailbox evidence to this JAP job; the DB link is not persisted yet. Click to open the application."
                    : "Persisted application link. Click to open the application."}
                >
                  {applicationStageLabel[linkedApplication.effective_stage]}
                </span>
              : <span
                  className="ow-application-status none"
                  title="No safe match exists between this JAP job and a known application. This does not mean that no application was submitted."
                >Unresolved</span>}
          </button>;
        })}

        {filtered.length === 0 &&
          <p className="ow-empty">No jobs match this filter.</p>}
      </div>

      {selected
        ? <JobDetail job={selected} payload={payload} refresh={refresh} applicationStage={applicationByJobId.get(selected.silver_job_id)?.effective_stage || null} onOpenApplications={() => onOpenApplication(applicationByJobId.get(selected.silver_job_id)?.application_id ?? null)} />
        : <aside className="ow-job-detail">
            <p className="ow-empty">Select a job.</p>
          </aside>}
    </section>
  </div>;
}

function TopFive({ payload, refresh }: { payload: ProductPayload; refresh: () => Promise<void> }) {
  const jobs = payload.top_jobs.filter(isCurrent).slice(0, 5);
  const [selectedId, setSelectedId] = useState<number | null>(jobs[0]?.silver_job_id ?? null);
  const applicationByJobId = useMemo(
    () => buildApplicationByJobId(payload),
    [
      payload.application_tracking?.applications,
      payload.application_tracking?.job_linkage?.exact_matches,
    ],
  );
  const selected = jobs.find((job) => job.silver_job_id === selectedId) || jobs[0] || null;
  return <div className="ow-stack"><header className="ow-page-header"><div><span>Application shortlist</span><h1>Top 5</h1><p>Only authoritative rankable jobs. Empty slots stay empty.</p></div><strong className="ow-big-count">{jobs.length}/5</strong></header>
    {jobs.length ? <section className="ow-top5-workspace"><div className="ow-top5-list">{jobs.map((job, index) => <button type="button" key={job.silver_job_id} className={selected?.silver_job_id === job.silver_job_id ? "selected" : ""} onClick={() => setSelectedId(job.silver_job_id)}><span className="ow-rank">#{job.product_rank || index + 1}</span><span><b>{job.title}</b><small>{employerName(job)} · {locationText(job)}</small></span><strong>{scoreText(job.overall_quality_score)}</strong></button>)}</div>{selected && <JobDetail job={selected} payload={payload} refresh={refresh} applicationStage={applicationByJobId.get(selected.silver_job_id)?.effective_stage || null} />}</section> : <section className="ow-card"><h2>No Top-5 job currently qualifies.</h2><p>The product does not fill the shortlist with weaker or stale jobs.</p></section>}
  </div>;
}

function Application({ payload, refresh }: { payload: ProductPayload; refresh: () => Promise<void> }) {
  const [starterLoading, setStarterLoading] = useState(false);
  const [starterError, setStarterError] = useState<string | null>(null);
  const applicationByJobId = useMemo(
    () => buildApplicationByJobId(payload),
    [
      payload.application_tracking?.applications,
      payload.application_tracking?.job_linkage?.exact_matches,
    ],
  );
  const top = payload.top_jobs.find(
    (job) =>
      isCurrent(job)
      && canPrepareApplication(applicationByJobId.get(job.silver_job_id)?.effective_stage),
  ) || null;
  const firstSelectable = payload.job_readiness.find(
    (job) =>
      isCurrent(job) &&
      job.hard_filter_status !== "failed" &&
      canPrepareApplication(applicationByJobId.get(job.silver_job_id)?.effective_stage),
  ) || null;
  const target = top || firstSelectable;
  const docsReady = payload.application_sources_ready.base_cv && payload.application_sources_ready.base_application_letter;
  const authorityTemplates = payload.f6_template_authority?.templates || [];
  const cvTemplate = authorityTemplates.find((item) => item.document_type === "base_cv");
  const letterTemplate = authorityTemplates.find((item) => item.document_type === "base_application_letter");

  const downloadStarterTemplate = async () => {
    setStarterLoading(true);
    setStarterError(null);
    try {
      const response = await fetch("/api/v1/product-v1/application-starter-template", {
        headers: { Accept: "application/json" },
      });
      const result = await response.json() as {
        download_filename?: string;
        docx_base64?: string;
        reason?: string;
      };
      if (!response.ok || !result.docx_base64) {
        throw new Error(result.reason || "Fillable starter template is unavailable.");
      }
      downloadBase64Document(
        result.docx_base64,
        result.download_filename || "JAP_Fillable_Application_Template.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      );
    } catch (reason) {
      setStarterError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setStarterLoading(false);
    }
  };

  return <div className="ow-stack">
    <header className="ow-page-header"><div><span>Prepare documents for one job</span><h1>Application Builder</h1><p>Create a tailored CV and cover letter from your approved source documents, or start with a local fillable Word template. JAP never submits automatically.</p></div></header>
    <section className="ow-application-grid">
      <article className="ow-card"><span className="ow-kicker">Application target</span><h2>{target?.title || "No current selectable job"}</h2>{target && <p>{employerName(target)} · {locationText(target)} · {top ? `${scoreText(top.overall_quality_score)} verified match score` : `${scoreText(target.overall_quality_score)} Affinity · operator selected`}</p>}<div className="ow-readiness"><div className={target ? "ready" : "blocked"}><i /><span>{top ? "Top-5 recommendation" : "Explicit current-job selection"}</span><b>{target ? "Ready for review drafting" : "Required"}</b></div><div className={payload.application_sources_ready.base_cv ? "ready" : "blocked"}><i /><span>CV source</span><b>{payload.application_sources_ready.base_cv ? "Ready" : "Required"}</b></div><div className={payload.application_sources_ready.base_application_letter ? "ready" : "blocked"}><i /><span>Cover letter source</span><b>{payload.application_sources_ready.base_application_letter ? "Ready" : "Required"}</b></div></div><OpenApplicationButton silverJobId={target?.silver_job_id} disabled={!target || !docsReady} /></article>
      <article className="ow-card ow-boundary-card"><span className="ow-kicker">Document layout</span><h2>{docsReady ? "Approved templates ready" : "Add your approved CV and cover letter"}</h2><p>Your source documents stay private. JAP preserves their layout and changes only the intended text areas.</p><ul><li>Layout and graphics stay unchanged</li><li>Only approved text areas may change</li><li>Profile facts and verified job evidence ground the content</li><li>No automatic apply, submit or send</li></ul></article>
    </section>
    <article className="ow-card">
      <span className="ow-kicker">Source documents</span>
      <h2>Use your own layout or start from a local template</h2>
      <p>Your approved PDF sources remain the layout reference for automatic document creation. If you do not have them yet, JAP can create a fillable local Word starter without contacting an AI provider.</p>
      <div className="ow-document-grid">
        <ApplicationSourceUpload
          documentType="base_cv"
          title="CV source"
          ready={payload.application_sources_ready.base_cv}
          canonicalFilename={cvTemplate?.canonical_filename || "Hornetsecurity_Jens_Haberle_Resume.pdf"}
          canonicalSha256={cvTemplate?.sha256 || ""}
          onUploaded={refresh}
        />
        <ApplicationSourceUpload
          documentType="base_application_letter"
          title="Cover letter source"
          ready={payload.application_sources_ready.base_application_letter}
          canonicalFilename={letterTemplate?.canonical_filename || "Hornetsecurity_Jens_Haberle_Cover_Letter.pdf"}
          canonicalSha256={letterTemplate?.sha256 || ""}
          onUploaded={refresh}
        />
      </div>
      <div className="ow-callout">
        <b>No source CV or cover letter available?</b>
        <span>Download a local fillable Word starter. It contains placeholders only, sends nothing to an AI provider and can be completed manually.</span>
        <button type="button" disabled={starterLoading} onClick={() => void downloadStarterTemplate()}>
          {starterLoading ? "Building local Word template…" : "Download fillable Word starter"}
        </button>
        {starterError && <small>{starterError}</small>}
      </div>
    </article>
  </div>;
}

function Applications({
  payload,
  focusApplicationId,
  onOpenJob,
  onSelectApplication,
  refresh,
}: {
  payload: ProductPayload;
  focusApplicationId: number | null;
  onOpenJob: (silverJobId: number) => void;
  onSelectApplication: (applicationId: number) => void;
  refresh: () => Promise<void>;
}) {
  return <div className="ow-stack">
    <header className="ow-page-header">
      <div>
        <span>After you apply</span>
        <h1>Application Tracker</h1>
        <p>Track submitted applications, replies, interviews and outcomes. Mailbox evidence and All Jobs stay linked without guessing across different vacancies.</p>
      </div>
    </header>
    <F5ApplicationTracking
      payload={payload as unknown as F5ProductPayload}
      focusApplicationId={focusApplicationId}
      onOpenJob={onOpenJob}
      onSelectApplication={onSelectApplication}
      refreshProductTruth={refresh}
    />
  </div>;
}
function sourceGroup(source: SourceConnector): SourceGroup {
  if (source.current_blocker) return "Needs attention";
  if (normalize(source.source_role) === "sensor") return "Market sensors";
  if (source.activation.active === true) {
    if (normalize(source.last_ingestion.status) === "success" && source.last_ingestion.total_loaded > 0) return "Delivering now";
    if (normalize(source.last_ingestion.status) === "success" && source.last_ingestion.total_loaded === 0) return "Active, 0 current jobs";
    return "Pending";
  }
  if (normalize(source.connector.implementation_status).includes("not implemented")) return "Not implemented";
  return "Pending";
}

function Sources({ payload }: { payload: ProductPayload }) {
  const sources = payload.source_connector_overview.sources;
  const overview = payload.source_connector_overview.summary;
  const groups: SourceGroup[] = ["Needs attention", "Delivering now", "Active, 0 current jobs", "Market sensors", "Pending", "Not implemented"];
  const groupCounts = Object.fromEntries(
    groups.map((group) => [group, sources.filter((source) => sourceGroup(source) === group).length]),
  ) as Record<SourceGroup, number>;
  const initialTab: SourceTab =
    groups.find((group) => groupCounts[group] > 0) || "All";
  const [activeTab, setActiveTab] = useState<SourceTab>(initialTab);
  const [selectedName, setSelectedName] = useState(
    sources.find((source) => source.current_blocker)?.source_name ||
    sources.find((source) => sourceGroup(source) === "Delivering now")?.source_name ||
    sources.find((source) => sourceGroup(source) === "Active, 0 current jobs")?.source_name ||
    sources.find((source) => sourceGroup(source) === "Market sensors")?.source_name ||
    sources[0]?.source_name || ""
  );
  const sourceTabs: Array<{ id: SourceTab; label: string; count: number }> = [
    { id: "All", label: "All sources", count: sources.length },
    { id: "Needs attention", label: "Needs attention", count: groupCounts["Needs attention"] },
    { id: "Delivering now", label: "Delivering jobs", count: groupCounts["Delivering now"] },
    { id: "Active, 0 current jobs", label: "Active · no jobs", count: groupCounts["Active, 0 current jobs"] },
    { id: "Market sensors", label: "Market discovery", count: groupCounts["Market sensors"] },
    { id: "Pending", label: "Setup pending", count: groupCounts.Pending },
    { id: "Not implemented", label: "Not connected", count: groupCounts["Not implemented"] },
  ];
  const visibleGroups = groups
    .filter((group) => activeTab === "All" || activeTab === group)
    .map((group) => ({
      group,
      sources: sources
        .filter((source) => sourceGroup(source) === group)
        .sort((left, right) => compareText(left.source_label, right.source_label)),
    }))
    .filter((entry) => entry.sources.length > 0);
  const visible = visibleGroups.flatMap((entry) => entry.sources);
  const selected =
    visible.find((source) => source.source_name === selectedName) ||
    visible[0] ||
    null;
  const summaryTruth = [
    ["Employer sources", overview.employer_origin_count],
    ["Delivering jobs", overview.active_last_run_loaded_count],
    ["Active · no current jobs", overview.active_last_run_zero_count],
    ["Discovery sources", overview.sensor_count],
    ["Needs attention", overview.attention_count],
  ] as Array<[string, number]>;

  return <div className="ow-stack">
    <header className="ow-page-header"><div><span>Where jobs come from</span><h1>Sources</h1><p>See which employer sources currently deliver jobs, which discovery channels expand coverage and where attention is needed.</p></div><strong className="ow-big-count">{sources.length}</strong></header>
    <section className="ow-source-summary-strip">
      {summaryTruth.map(([name, value]) => <div key={name}><span>{name}</span><b>{value}</b></div>)}
    </section>
    <nav className="ow-source-tabs" aria-label="Source groups">
      {sourceTabs.map((tab) => <button
        type="button"
        key={tab.id}
        className={activeTab === tab.id ? "active" : ""}
        aria-pressed={activeTab === tab.id}
        onClick={() => setActiveTab(tab.id)}
      ><span>{tab.label}</span><b>{tab.count}</b></button>)}
    </nav>
    <section className="ow-source-workspace">
      <div className="ow-source-list">{visibleGroups.map(({ group, sources: groupedSources }) => <div key={group}><div className="ow-source-group-title"><span>{sourceGroupDisplay(group)}</span><b>{groupedSources.length}</b></div>{groupedSources.map((source) => <button type="button" key={source.source_name} className={selected?.source_name === source.source_name ? "selected" : ""} onClick={() => setSelectedName(source.source_name)}><span><b>{source.source_label}</b><small>{sourcePurpose(source)} · {source.last_ingestion.total_loaded} jobs on last check</small></span><b className="ow-source-row-state">{sourceGroupDisplay(sourceGroup(source))}</b></button>)}</div>)}</div>
      {selected && <article className="ow-card ow-source-detail"><span className="ow-kicker">{sourceGroupDisplay(sourceGroup(selected))}</span><h2>{selected.source_label}</h2><div className="ow-source-facts"><div><span>Purpose</span><b>{sourcePurpose(selected)}</b></div><div><span>Connection</span><b>{label(selected.connector.implementation_status)}</b></div><div><span>Verified</span><b>{label(selected.gates.connector_validation_gate.status)}</b></div><div><span>Ready for use</span><b>{label(selected.gates.final_approval_gate.status)}</b></div><div><span>Status</span><b>{label(selected.activation.status)}</b></div><div><span>Last check</span><b>{label(selected.last_ingestion.status)}</b></div><div><span>Jobs found</span><b>{selected.last_ingestion.total_loaded} found · {selected.last_ingestion.inserted_count} new</b></div><div><span>Search profiles</span><b>{selected.search_profiles.active_profile_count}/{selected.search_profiles.profile_count} active</b></div><div><span>Data coverage</span><b>Raw {selected.layers.bronze_count} · normalized {selected.layers.silver_count}</b></div></div>{selected.current_blocker ? <div className="ow-callout warn"><b>Needs attention</b><span>{selected.next_action}</span></div> : <div className="ow-callout good"><b>No action needed</b><span>This source is currently usable within its approved role.</span></div>}</article>}
    </section>
  </div>;
}

function Operations({ payload }: { payload: ProductPayload }) {
  const overview = payload.source_connector_overview.summary;
  const stages: Array<[string, number]> = [["Known", overview.source_count], ["Implemented", overview.implemented_count], ["Validated", overview.validated_count], ["Approved", overview.final_approved_count], ["Registered", overview.registered_count], ["Active", overview.active_count], ["Ingested", overview.ingested_count]];
  return <div className="ow-stack"><header className="ow-page-header"><div><span>Runtime truth</span><h1>Operations</h1><p>Observability and lifecycle health, separated from daily job review.</p></div></header><section className="ow-card"><h2>Source lifecycle</h2><div className="ow-pipeline">{stages.map(([name, value]) => <div key={name}><span>{name}</span><strong>{value}</strong></div>)}</div></section><section className="ow-metrics"><Metric labelText="Current active" value={payload.summary.current_active_job_count} helper="all persisted vacancies" /><Metric labelText="Review scope current" value={payload.summary.review_scope_current_active_job_count ?? payload.job_readiness.filter(isCurrent).length} helper="current employer-origin vacancies" /><Metric labelText="Stale" value={payload.summary.stale_job_count} helper="historical refresh required" /><Metric labelText="Attention sources" value={overview.attention_count} helper="need action" /></section></div>;
}

const navItems: Array<{ id: View; label: string; glyph: string }> = [
  { id: "overview", label: "Overall", glyph: "◉" },
  { id: "jobs", label: "All Jobs", glyph: "≡" },
  { id: "top5", label: "Top 5", glyph: "★" },
  { id: "application", label: "Application Builder", glyph: "↗" },
  { id: "applications", label: "Application Tracker", glyph: "◎" },
  { id: "sources", label: "Sources", glyph: "⌁" },
  { id: "operations", label: "Operations", glyph: "⌘" },
];

export default function OperatorWorkspace() {
  const { payload, error, refreshing, refreshWarning, refreshProductTruth } = useProductTruth<ProductPayload>();
  const [view, setView] = useState<View>("overview");
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [selectedApplicationId, setSelectedApplicationId] = useState<number | null>(null);

  const refresh = refreshProductTruth;
  const openApplication = (applicationId: number | null) => {
    setSelectedApplicationId(applicationId);
    setView("applications");
  };
  const openJob = (silverJobId: number) => {
    setSelectedJobId(silverJobId);
    setView("jobs");
  };

  if (error) return <main className="ow-fatal"><div><span>Fail closed</span><h1>Control Center unavailable</h1><pre>{error}</pre></div></main>;
  if (!payload) return <main className="ow-loading"><div /><p>Loading current job data…</p></main>;

  const navBadges: Partial<Record<View, number>> = {
    jobs: payload.job_readiness.length,
    top5: payload.summary.top_job_count,
    sources: payload.source_connector_overview.summary.attention_count,
  };

  return <div className="ow-shell">
    <aside className="ow-sidebar">
      <div className="ow-brand"><div>DO</div><span><b>Deep Ocean</b><small>Intelligence</small></span></div>
      <nav aria-label="Primary navigation">{navItems.map((item, index) => <div key={item.id} className={index === 5 ? "ow-nav-break" : undefined}><button type="button" className={view === item.id ? "active" : ""} onClick={() => setView(item.id)}><i>{item.glyph}</i><span>{item.label}</span>{navBadges[item.id] != null && <b>{navBadges[item.id]}</b>}</button></div>)}</nav>
      <footer><span><i /> Live data</span><small>Review-first · no automatic applications</small></footer>
    </aside>
    <div className="ow-content-shell">
      <header className="ow-topline">
        <div><b>{navItems.find((item) => item.id === view)?.label}</b><span>Live job data</span></div>
        <div className="ow-topline-actions">
          {refreshWarning && <span className="ow-refresh-warning" role="status" title={refreshWarning}>Mailbox sync needs attention</span>}
          <button type="button" disabled={refreshing} onClick={() => void refresh()}>{refreshing ? "Refreshing…" : "↻ Refresh"}</button>
        </div>
      </header>
      <main className="ow-main">{view === "overview" && <Overview payload={payload} onNavigate={setView} />}{view === "jobs" && <Jobs payload={payload} refresh={refresh} selectedJobId={selectedJobId} onSelectJob={setSelectedJobId} onOpenApplication={openApplication} />}{view === "top5" && <TopFive payload={payload} refresh={refresh} />}{view === "application" && <Application payload={payload} refresh={refresh} />}{view === "applications" && <Applications payload={payload} focusApplicationId={selectedApplicationId} onOpenJob={openJob} onSelectApplication={setSelectedApplicationId} refresh={refresh} />}{view === "sources" && <Sources payload={payload} />}{view === "operations" && <Operations payload={payload} />}</main>
    </div>
  </div>;
}
