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

type View = "overview" | "jobs" | "top5" | "application" | "applications" | "sources" | "approvals" | "operations";
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
  prepared: "Erkannt",
  applied: "Beworben",
  reply: "Antwort",
  interview: "Interview",
  offer: "Angebot",
  closed: "Geschlossen",
};
const isAppliedStage = (stage: ApplicationStage) => stage !== "prepared";
const canPrepareApplication = (stage: ApplicationStage | null | undefined) =>
  stage == null || stage === "prepared";

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
      <div><span>Overall</span><h1>What matters now</h1><p>Current Product V1 truth, reduced to the next useful decisions.</p></div>
    </header>

    <section className="ow-metrics">
      <Metric labelText="Current jobs" value={currentJobs.length} helper="confirmed active employer-origin vacancies" />
      <Metric labelText="Profile Fit complete" value={payload.summary.profile_fit_complete_count ?? 0} helper="conclusive evidence-backed fit decisions" />
      <Metric labelText="Needs fit evidence" value={payload.summary.profile_fit_insufficient_evidence_count ?? 0} helper="missing evidence, never negative fit" />
      <Metric labelText="Rankable" value={payload.summary.rankable_job_count} helper="existing Product gate; F4B remains separate" />
      <Metric labelText="Top 5" value={`${payload.summary.top_job_count}/5`} helper="authoritative shortlist" />
      <Metric labelText="Top-5 draft ready" value={payload.summary.application_ready_count} helper="strict recommendation-path eligibility; explicit operator selection is separate" />
    </section>

    <section className="ow-overview-grid">
      <article className="ow-card ow-now-card">
        <div className="ow-card-title"><div><span>Best current option</span><h2>{top ? top.title : "No rankable job yet"}</h2></div>{top && <strong>#{top.product_rank || 1}</strong>}</div>
        {top ? <>
          <p className="ow-job-meta">{employerName(top)} · {locationText(top)}</p>
          <div className="ow-fit-line"><b>{scoreText(top.overall_quality_score)}</b><span>authoritative Product score</span></div>
          <div className="ow-actions"><button type="button" onClick={() => onNavigate("top5")}>Open Top 5</button>{topUrl && <a href={topUrl} target="_blank" rel="noreferrer">Original job ↗</a>}</div>
        </> : <p className="ow-muted">The UI will not manufacture a recommendation.</p>}
      </article>

      <article className="ow-card">
        <div className="ow-card-title"><div><span>Your feedback</span><h2>Relevance labels</h2></div><strong>{reviewed.length}</strong></div>
        <div className="ow-feedback-summary"><div><span>Interesting</span><b>{interesting}</b></div><div><span>Not relevant</span><b>{rejected}</b></div><div><span>Unreviewed</span><b>{payload.job_readiness.length - reviewed.length}</b></div></div>
        <p className="ow-muted">These labels build personal relevance evidence; they do not directly rewrite ranking.</p>
        <button type="button" className="ow-text-action" onClick={() => onNavigate("jobs")}>Review jobs →</button>
      </article>

      <article className="ow-card">
        <div className="ow-card-title"><div><span>F6 Application</span><h2>{docsReady ? "Template authority ready" : "Exact templates required"}</h2></div></div>
        <div className="ow-readiness"><div className={payload.application_sources_ready.base_cv ? "ready" : "blocked"}><i /><span>Canonical CV</span><b>{payload.application_sources_ready.base_cv ? "Exact hash" : "Required"}</b></div><div className={payload.application_sources_ready.base_application_letter ? "ready" : "blocked"}><i /><span>Canonical letter</span><b>{payload.application_sources_ready.base_application_letter ? "Exact hash" : "Required"}</b></div></div>
        <button type="button" className="ow-text-action" onClick={() => onNavigate("application")}>Open application step →</button>
      </article>

      <article className="ow-card">
        <div className="ow-card-title"><div><span>Discovery health</span><h2>Origin review scope</h2></div></div>
        <p>{currentJobs.length} current employer-origin vacancies are in the visible review scope. Market sensors and historical lifecycle memory stay separate.</p>
        <div className="ow-actions"><button type="button" onClick={() => onNavigate("sources")}>Sources</button><button type="button" onClick={() => onNavigate("applications")}>Applications</button></div>
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
    <div className="ow-detail-head"><span>Silver #{job.silver_job_id}</span><h2>{job.title || "Untitled job"}</h2><p>{employerName(job)} · {locationText(job)}</p>{job.legal_entity_name && normalize(job.legal_entity_name) !== normalize(employerName(job)) && <small>Legal entity: {job.legal_entity_name}</small>}</div>
    <div className="ow-actions">{sourceUrl && <a className="ow-primary-link" href={sourceUrl} target="_blank" rel="noreferrer">Open original ↗</a>}{hasPersistedActiveLifecycle(job) && job.hard_filter_status !== "failed" && canPrepareApplication(applicationStage) && <OpenApplicationButton silverJobId={job.silver_job_id} disabled={liveCheck.status === "checking"} />}{applicationStage && onOpenApplications && <button type="button" onClick={onOpenApplications}>Open Applications</button>}</div>
    <JobReviewLabelControls silverJobId={job.silver_job_id} currentLabel={job.review_label} captureAvailable={payload.review_label_capture?.available === true} refreshProductTruth={refresh} />
    <section className="ow-facts"><div><span>Profile Fit coverage</span><Status value={job.profile_fit_coverage_status || "insufficient_evidence"} /></div><div><span>Profile Fit decision</span><Status value={job.profile_fit_decision || "unknown"} /></div>{profileFitFactorRows.map(([name, value]) => <div key={name}><span>{name}</span><Status value={value || "unknown"} /></div>)}</section>
    <section className="ow-score-card"><h3>{rankable ? "Product score" : "Role affinity · preliminary"}</h3>{scoreRows.map(([name, value]) => <div key={name}><span>{name}</span><i><b style={{ width: `${Math.max(0, Math.min(100, value || 0))}%` }} /></i><strong>{scoreText(value)}</strong></div>)}{!rankable && <p className="ow-score-note">Detail check required. This preliminary signal uses review-scope evidence and is not capability-fit or Product V1 ranking authority.</p>}</section>
    <section className="ow-facts"><div><span>Lifecycle</span><Status value={job.lifecycle_status} /></div><div><span>Live availability</span><Status value={liveCheck.status === "checking" ? "checking" : liveCheck.status === "idle" ? "not checked" : liveCheck.status} /></div><div><span>Product gate</span><Status value={job.product_readiness_status} /></div><div><span>Application</span>{applicationStage ? <b className={`ow-application-status ${applicationStage}`}>{applicationStageLabel[applicationStage]}</b> : <b>—</b>}</div><div><span>Work model</span><b>{label(job.work_model)}</b></div><div><span>Commute</span><b>{job.commute_minutes == null ? "—" : `${job.commute_minutes} min`}</b></div><div><span>Published</span><b>{displayDate(job.publication_date)}</b></div><div><span>First JAP observed</span><b>{displayDate(job.first_jap_observed_at)}</b></div></section>
    <section className="ow-evidence"><div><span>Verified</span>{job.explanations?.length ? <ul>{job.explanations.map((item) => <li key={item}>{item}</li>)}</ul> : <p>No projected explanation evidence.</p>}</div><div><span>Unknown / review</span>{job.uncertainties?.length ? <ul>{job.uncertainties.map((item) => <li key={item}>{item}</li>)}</ul> : <p>No projected uncertainty.</p>}</div></section>
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
        <h1>All jobs</h1>
        <p>
          Current employer-origin vacancies only. Market sensors and historical jobs remain auditable outside this review list.
          A real Profile Fit exists only after detail evidence, capability fit and hard gates.
        </p>
      </div>
    </header>

    <section className="ow-job-toolbar">
      <div className="ow-filter-row">
        {([
          ["all", "All jobs"],
          ["unreviewed", "Unreviewed"],
          ["interesting", "Interesting"],
          ["not_relevant", "Not relevant"],
          ["rankable", "Rankable"],
          ["applied", "Beworben"],
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
            <option value="gate_asc">Gate A → Z</option>
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
          {sortHeader("gate", "Gate")}
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
            <strong title={isRankable(job) ? "Authoritative Product score" : "Preliminary role affinity · detail check required"}>{scoreText(job.overall_quality_score)}</strong>
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

            <span className="ow-gate-state"><Status value={job.profile_fit_coverage_status || "insufficient_evidence"} /><Status value={job.product_readiness_status} /></span>

            {linkedApplication
              ? <span
                  className={`ow-application-status linked ${linkedApplication.effective_stage}`}
                  onClick={(event) => {
                    event.stopPropagation();
                    onOpenApplication(linkedApplication.application_id ?? null);
                  }}
                  title={linkedApplication.linkage_status === "exact_projected"
                    ? "Exakt aus Mailbox-Evidence zu diesem JAP-Job zugeordnet; DB-Link noch nicht persistiert. Klicken, um die Bewerbung zu öffnen."
                    : "Persistierte Application-Verknüpfung. Klicken, um die Bewerbung zu öffnen."}
                >
                  {applicationStageLabel[linkedApplication.effective_stage]}
                </span>
              : <span
                  className="ow-application-status none"
                  title="Keine sichere Zuordnung zwischen diesem JAP-Job und einer bekannten Bewerbung. Das ist nicht gleichbedeutend mit 'nicht beworben'."
                >Ungeklärt</span>}
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
  return <div className="ow-stack">
    <header className="ow-page-header"><div><span>F6 · Template-authoritative drafting</span><h1>Application</h1><p>Verified vacancy + Candidate Facts + the two frozen private PDFs. Layout is immutable; only explicitly approved text zones may change. Never auto-submit.</p></div></header>
    <section className="ow-application-grid">
      <article className="ow-card"><span className="ow-kicker">Application target</span><h2>{target?.title || "No current selectable job"}</h2>{target && <p>{employerName(target)} · {locationText(target)} · {top ? `${scoreText(top.overall_quality_score)} authoritative Product score` : `${scoreText(target.overall_quality_score)} Affinity · operator selected`}</p>}<div className="ow-readiness"><div className={target ? "ready" : "blocked"}><i /><span>{top ? "Top-5 recommendation" : "Explicit current-job selection"}</span><b>{target ? "Ready for review drafting" : "Required"}</b></div><div className={payload.application_sources_ready.base_cv ? "ready" : "blocked"}><i /><span>Canonical CV</span><b>{payload.application_sources_ready.base_cv ? "Exact authority" : "Required"}</b></div><div className={payload.application_sources_ready.base_application_letter ? "ready" : "blocked"}><i /><span>Canonical letter</span><b>{payload.application_sources_ready.base_application_letter ? "Exact authority" : "Required"}</b></div></div><OpenApplicationButton silverJobId={target?.silver_job_id} disabled={!target || !docsReady} /></article>
      <article className="ow-card ow-boundary-card"><span className="ow-kicker">F6 layout boundary</span><h2>{docsReady ? "Pixel-bound template authority active" : "Install the two exact F6 PDFs"}</h2><p>The PDF binaries remain private, but their SHA-256 hashes, page geometry and editable text zones are frozen in repo truth. Arbitrary replacement layouts are no longer accepted.</p><ul><li>Layout and graphics are immutable</li><li>Only declared text zones may change</li><li>Candidate Facts and exact Origin evidence are content authority</li><li>No legacy renderer, hidden auto-apply, submit or send</li></ul></article>
    </section>
    <article className="ow-card">
      <span className="ow-kicker">F6 template authority</span>
      <h2>Exactly two layouts. No fallback.</h2>
      <p>These are the only application templates allowed in the freeze campaign. A visually similar or older PDF is rejected by exact hash before it can become active.</p>
      <div className="ow-document-grid">
        <ApplicationSourceUpload
          documentType="base_cv"
          title="Canonical CV"
          ready={payload.application_sources_ready.base_cv}
          canonicalFilename={cvTemplate?.canonical_filename || "Hornetsecurity_Jens_Haberle_Lebenslauf.pdf"}
          canonicalSha256={cvTemplate?.sha256 || ""}
          onUploaded={refresh}
        />
        <ApplicationSourceUpload
          documentType="base_application_letter"
          title="Canonical letter"
          ready={payload.application_sources_ready.base_application_letter}
          canonicalFilename={letterTemplate?.canonical_filename || "Hornetsecurity_Jens_Haberle_Anschreiben.pdf"}
          canonicalSha256={letterTemplate?.sha256 || ""}
          onUploaded={refresh}
        />
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
        <span>After preparation</span>
        <h1>Applications</h1>
        <p>One shared Product truth snapshot connects mailbox application history and the All jobs review surface in both directions.</p>
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
    { id: "All", label: "All", count: sources.length },
    { id: "Needs attention", label: "Attention", count: groupCounts["Needs attention"] },
    { id: "Delivering now", label: "Delivering", count: groupCounts["Delivering now"] },
    { id: "Active, 0 current jobs", label: "Active · 0 jobs", count: groupCounts["Active, 0 current jobs"] },
    { id: "Market sensors", label: "Sensors", count: groupCounts["Market sensors"] },
    { id: "Pending", label: "Pending", count: groupCounts.Pending },
    { id: "Not implemented", label: "Not implemented", count: groupCounts["Not implemented"] },
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
    ["Employer origins", overview.employer_origin_count],
    ["Delivering now", overview.active_last_run_loaded_count],
    ["Active, 0 current jobs", overview.active_last_run_zero_count],
    ["Market sensors", overview.sensor_count],
    ["Needs attention", overview.attention_count],
  ] as Array<[string, number]>;

  return <div className="ow-stack">
    <header className="ow-page-header"><div><span>Source control</span><h1>Sources</h1><p>Employer-origin delivery, zero-yield activation, market sensors and real blockers are separate truths. Use the tabs to keep the source inventory compact.</p></div><strong className="ow-big-count">{sources.length}</strong></header>
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
      <div className="ow-source-list">{visibleGroups.map(({ group, sources: groupedSources }) => <div key={group}><div className="ow-source-group-title"><span>{group}</span><b>{groupedSources.length}</b></div>{groupedSources.map((source) => <button type="button" key={source.source_name} className={selected?.source_name === source.source_name ? "selected" : ""} onClick={() => setSelectedName(source.source_name)}><span><b>{source.source_label}</b><small>{source.source_name}</small></span><Status value={source.current_blocker || source.activation.status} /></button>)}</div>)}</div>
      {selected && <article className="ow-card ow-source-detail"><span className="ow-kicker">{sourceGroup(selected)} · {selected.source_type}</span><h2>{selected.source_label}</h2><code>{selected.source_name}</code><div className="ow-source-facts"><div><span>Role</span><b>{label(selected.source_role)}</b></div><div><span>Implementation</span><b>{label(selected.connector.implementation_status)}</b></div><div><span>Validation</span><b>{label(selected.gates.connector_validation_gate.status)}</b></div><div><span>Approval</span><b>{label(selected.gates.final_approval_gate.status)}</b></div><div><span>Activation</span><b>{label(selected.activation.status)}</b></div><div><span>Latest run</span><b>{label(selected.last_ingestion.status)}</b></div><div><span>Latest load</span><b>{selected.last_ingestion.total_loaded} loaded · {selected.last_ingestion.inserted_count} inserted</b></div><div><span>Profiles</span><b>{selected.search_profiles.active_profile_count}/{selected.search_profiles.profile_count} active</b></div><div><span>Layers</span><b>Bronze {selected.layers.bronze_count} · Silver {selected.layers.silver_count}</b></div></div>{selected.current_blocker ? <div className="ow-callout warn"><b>{label(selected.current_blocker)}</b><span>{selected.next_action}</span></div> : <div className="ow-callout good"><b>No current blocker</b><span>{selected.next_action}</span></div>}</article>}
    </section>
  </div>;
}

function Approvals({ payload }: { payload: ProductPayload }) {
  const waiting = payload.source_connector_overview.sources.filter((source) => source.current_blocker === "final_approval_incomplete");
  return <div className="ow-stack"><header className="ow-page-header"><div><span>Human authority</span><h1>Approvals</h1><p>Only real authority decisions belong here. Technical work stays in Sources.</p></div><strong className="ow-big-count">{waiting.length}</strong></header><section className="ow-approval-grid"><article className="ow-card"><h2>{waiting.length ? "Final source approvals" : "Nothing waiting"}</h2>{waiting.length ? waiting.map((source) => <div className="ow-approval-row" key={source.source_name}><span><b>{source.source_label}</b><small>{source.next_action}</small></span><Status value="approval_required" /></div>) : <p className="ow-muted">No source approval decision is currently waiting.</p>}</article><article className="ow-card"><h2>Product-level gates</h2>{payload.operator_blockers.length ? payload.operator_blockers.map((blocker) => <div className="ow-approval-row" key={blocker.code}><span><b>{blocker.title}</b><small>{blocker.detail}</small></span></div>) : <p className="ow-muted">No product-level approval blocker.</p>}</article></section></div>;
}

function Operations({ payload }: { payload: ProductPayload }) {
  const overview = payload.source_connector_overview.summary;
  const stages: Array<[string, number]> = [["Known", overview.source_count], ["Implemented", overview.implemented_count], ["Validated", overview.validated_count], ["Approved", overview.final_approved_count], ["Registered", overview.registered_count], ["Active", overview.active_count], ["Ingested", overview.ingested_count]];
  return <div className="ow-stack"><header className="ow-page-header"><div><span>Runtime truth</span><h1>Operations</h1><p>Observability and lifecycle health, separated from daily job review.</p></div></header><section className="ow-card"><h2>Source lifecycle</h2><div className="ow-pipeline">{stages.map(([name, value]) => <div key={name}><span>{name}</span><strong>{value}</strong></div>)}</div></section><section className="ow-metrics"><Metric labelText="Current active" value={payload.summary.current_active_job_count} helper="all persisted vacancies" /><Metric labelText="Review scope current" value={payload.summary.review_scope_current_active_job_count ?? payload.job_readiness.filter(isCurrent).length} helper="current employer-origin vacancies" /><Metric labelText="Stale" value={payload.summary.stale_job_count} helper="historical refresh required" /><Metric labelText="Attention sources" value={overview.attention_count} helper="need action" /></section></div>;
}

const navItems: Array<{ id: View; label: string; glyph: string }> = [
  { id: "overview", label: "Overall", glyph: "◉" },
  { id: "jobs", label: "All jobs", glyph: "≡" },
  { id: "top5", label: "Top 5", glyph: "★" },
  { id: "application", label: "Application", glyph: "↗" },
  { id: "applications", label: "Applications", glyph: "◎" },
  { id: "sources", label: "Sources", glyph: "⌁" },
  { id: "approvals", label: "Approvals", glyph: "✓" },
  { id: "operations", label: "Operations", glyph: "⌘" },
];

export default function OperatorWorkspace() {
  const { payload, error, refreshing, refreshProductTruth } = useProductTruth<ProductPayload>();
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
  if (!payload) return <main className="ow-loading"><div /><p>Reading Product V1 truth…</p></main>;

  const navBadges: Partial<Record<View, number>> = {
    jobs: payload.job_readiness.length,
    top5: payload.summary.top_job_count,
    approvals: payload.source_connector_overview.sources.filter((source) => source.current_blocker === "final_approval_incomplete").length,
    sources: payload.source_connector_overview.summary.attention_count,
  };

  return <div className="ow-shell">
    <aside className="ow-sidebar">
      <div className="ow-brand"><div>DO</div><span><b>Deep Ocean</b><small>Intelligence</small></span></div>
      <nav aria-label="Primary navigation">{navItems.map((item, index) => <div key={item.id} className={index === 5 ? "ow-nav-break" : undefined}><button type="button" className={view === item.id ? "active" : ""} onClick={() => setView(item.id)}><i>{item.glyph}</i><span>{item.label}</span>{navBadges[item.id] != null && <b>{navBadges[item.id]}</b>}</button></div>)}</nav>
      <footer><span><i /> DB truth</span><small>Product V1 · review-first</small></footer>
    </aside>
    <div className="ow-content-shell">
      <header className="ow-topline"><div><b>{navItems.find((item) => item.id === view)?.label}</b><span>Product V1 · live pipeline</span></div><button type="button" disabled={refreshing} onClick={() => void refresh()}>{refreshing ? "Refreshing…" : "↻ Refresh"}</button></header>
      <main className="ow-main">{view === "overview" && <Overview payload={payload} onNavigate={setView} />}{view === "jobs" && <Jobs payload={payload} refresh={refresh} selectedJobId={selectedJobId} onSelectJob={setSelectedJobId} onOpenApplication={openApplication} />}{view === "top5" && <TopFive payload={payload} refresh={refresh} />}{view === "application" && <Application payload={payload} refresh={refresh} />}{view === "applications" && <Applications payload={payload} focusApplicationId={selectedApplicationId} onOpenJob={openJob} onSelectApplication={setSelectedApplicationId} refresh={refresh} />}{view === "sources" && <Sources payload={payload} />}{view === "approvals" && <Approvals payload={payload} />}{view === "operations" && <Operations payload={payload} />}</main>
    </div>
  </div>;
}
