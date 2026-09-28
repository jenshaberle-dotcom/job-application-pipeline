import { useEffect, useMemo, useState } from "react";
import "./f5-application-tracking.css";

export type F5TrackingJob = {
  silver_job_id: number;
  title?: string | null;
  company_name?: string | null;
  source_url?: string | null;
};

type Stage = "prepared" | "applied" | "reply" | "interview" | "offer" | "closed";

type EvidenceCandidate = {
  candidate_id?: number | null;
  candidate_class?: string | null;
  match_status?: string | null;
  confidence?: number | null;
  ambiguity_reason?: string | null;
  review_status?: string | null;
  observed_at?: string | null;
  created_at?: string | null;
  evidence?: Record<string, unknown>;
  authority?: string;
  requires_review?: boolean;
  review_reason?: string | null;
};

type TrackedApplication = {
  application_id: number;
  silver_job_id?: number | null;
  job_link_status?: "linked" | "external" | string;
  discovery_kind?: string | null;
  discovered_at?: string | null;
  title?: string | null;
  company_name?: string | null;
  display_company_name?: string | null;
  source_url?: string | null;
  sender_domain?: string | null;
  counterparty_domain?: string | null;
  employer_evidence_source?: string | null;
  identity_source?: string | null;
  application_kind?: string | null;
  prepared_at?: string | null;
  prepared_by?: string | null;
  submitted_at?: string | null;
  submission_channel?: string | null;
  submission_authority_kind?: string | null;
  authoritative_stage: Stage;
  observed_stage?: Stage | null;
  observed_event_class?: string | null;
  observed_at?: string | null;
  observed_confidence?: number | null;
  effective_stage: Stage;
  effective_stage_basis?: string | null;
  authoritative_event_count: number;
  attention_candidate_count: number;
  storage_attention_candidate_count?: number;
  attention_status?: string | null;
  evidence_candidates: EvidenceCandidate[];
  stage_authority: string;
};

export type F5ProductPayload = {
  job_readiness: F5TrackingJob[];
  application_tracking?: {
    available: boolean;
    summary: {
      application_count: number;
      submitted_count: number;
      mailbox_discovered_count?: number;
      observed_status_count?: number;
      attention_count: number;
      unmatched_candidate_count: number;
      stage_counts: Record<string, number>;
    };
    applications: TrackedApplication[];
    job_linkage?: {
      read_only: boolean;
      exact_matches: Array<{
        application_id?: number;
        silver_job_id?: number | null;
        effective_stage?: Stage;
        linkage_status?: string;
        linkage_basis?: string;
      }>;
      exact_match_count: number;
      unresolved_count: number;
      database_writes: number;
      authoritative_lifecycle_mutations: number;
    };
    unmatched_evidence_candidates: EvidenceCandidate[];
    boundaries: Record<string, boolean>;
  };
};

type Filter = "all" | "attention" | "active" | "closed";
const STAGES: Stage[] = ["prepared", "applied", "reply", "interview", "offer", "closed"];
const GROUP_ORDER: Stage[] = ["prepared", "applied", "reply", "interview", "offer", "closed"];
const stageLabel: Record<Stage, string> = {
  prepared: "Detected",
  applied: "Applied",
  reply: "Reply",
  interview: "Interview",
  offer: "Offer",
  closed: "Closed",
};
const channelLabel: Record<string, string> = {
  employer_portal: "Employer portal",
  email: "E-Mail",
  external_platform: "External platform",
  manual_other: "Other manual source",
};

function localDateToday() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

function formatDate(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
}

function attentionMessage(application: TrackedApplication) {
  const count = application.attention_candidate_count;
  const total = application.evidence_candidates.length;
  if (count <= 0) return null;
  const plural = count === 1 ? "mail signal requires" : "mail signals require";
  if (application.observed_stage) {
    return `${count} of ${total || count} ${plural} review. The displayed status “${stageLabel[application.effective_stage]}” comes from separately qualified evidence.`;
  }
  return `${count} of ${total || count} ${plural} review. Until resolved, the status remains on the existing authoritative truth.`;
}

function StageStrip({ stage }: { stage: Stage }) {
  const current = STAGES.indexOf(stage);
  return <div className="f5-stage-strip" aria-label={`Current application status ${stageLabel[stage]}`}>
    {STAGES.map((item, index) => <span key={item} className={index <= current ? "reached" : "future"}>
      <i aria-hidden="true" />{stageLabel[item]}
    </span>)}
  </div>;
}

function RecordSubmission({ jobs, trackedIds, onRecorded }: { jobs: F5TrackingJob[]; trackedIds: Set<number>; onRecorded: () => Promise<void> }) {
  const available = useMemo(
    () => jobs.filter((job) => !trackedIds.has(job.silver_job_id)),
    [jobs, trackedIds],
  );
  const employers = useMemo(() => Array.from(new Set(
    available
      .map((job) => (job.company_name || "").trim())
      .filter(Boolean),
  )).sort((left, right) => left.localeCompare(right, "en")), [available]);

  const [mode, setMode] = useState<"jap" | "external">("jap");
  const [employer, setEmployer] = useState("");
  const [jobId, setJobId] = useState("");
  const [externalEmployer, setExternalEmployer] = useState("");
  const [externalTitle, setExternalTitle] = useState("");
  const [externalUrl, setExternalUrl] = useState("");
  const [submittedOn, setSubmittedOn] = useState(localDateToday());
  const [channel, setChannel] = useState("employer_portal");
  const [reference, setReference] = useState("");
  const [state, setState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [message, setMessage] = useState("");

  const employerJobs = useMemo(
    () => employer
      ? available
          .filter((job) => (job.company_name || "").trim() === employer)
          .sort((left, right) => (left.title || "").localeCompare(right.title || "", "en"))
      : [],
    [available, employer],
  );

  useEffect(() => {
    setJobId("");
  }, [employer]);

  useEffect(() => {
    if (mode === "jap") {
      setExternalEmployer("");
      setExternalTitle("");
      setExternalUrl("");
    } else {
      setEmployer("");
      setJobId("");
    }
    setState("idle");
    setMessage("");
  }, [mode]);

  async function record() {
    const external = mode === "external";
    if (
      !submittedOn ||
      (!external && (!employer || !jobId)) ||
      (external && (!externalEmployer.trim() || !externalTitle.trim()))
    ) {
      setState("error");
      setMessage(
        external
          ? "Employer, job title and application date are required."
          : "Employer, job and application date are required.",
      );
      return;
    }

    setState("saving");
    setMessage("");
    try {
      const requestBody = external
        ? {
            action: "record_operator_confirmed_submission",
            submitted_on: submittedOn,
            submission_channel: channel,
            authority_reference: reference.trim() || undefined,
            employer_name: externalEmployer.trim(),
            job_title: externalTitle.trim(),
            source_url: externalUrl.trim() || undefined,
          }
        : {
            action: "record_operator_confirmed_submission",
            silver_job_id: Number(jobId),
            submitted_on: submittedOn,
            submission_channel: channel,
            authority_reference: reference.trim() || undefined,
          };

      const response = await fetch("/api/v1/product-v1/application-submission-record", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      });
      const payload = await response.json() as { status?: string; reason?: string; message?: string; error_type?: string };
      if (!response.ok) {
        const detail = payload.reason || payload.message;
        throw new Error(detail ? `${payload.error_type ? payload.error_type + ": " : ""}${detail}` : `HTTP ${response.status}`);
      }
      setState("saved");
      setMessage(
        payload.status === "already_recorded"
          ? "Already recorded with identical details."
          : external
            ? "External application was added to JAP."
            : "Recorded as already applied.",
      );
      await onRecorded();
    } catch (error) {
      setState("error");
      setMessage(error instanceof Error ? error.message : "Could not record the application.");
    }
  }

  return <details className="f5-record-submission">
    <summary>Add manually · fallback</summary>
    <div className="f5-record-boundary"><b>Record existing truth only.</b> JAP does not submit an application or send email here. Later mailbox evidence should converge with this entry.</div>

    <div className="f5-record-mode" role="group" aria-label="Source of the manual application entry">
      <button type="button" className={mode === "jap" ? "active" : ""} onClick={() => setMode("jap")}>JAP job</button>
      <button type="button" className={mode === "external" ? "active" : ""} onClick={() => setMode("external")}>Job not in JAP</button>
    </div>

    <div className="f5-record-grid">
      {mode === "jap" ? <>
        <label>Employer
          <select value={employer} onChange={(event) => setEmployer(event.target.value)}>
            <option value="">Select employer …</option>
            {employers.map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
        </label>
        <label>Job
          <select value={jobId} disabled={!employer} onChange={(event) => setJobId(event.target.value)}>
            <option value="">{employer ? "Select job …" : "Select employer first"}</option>
            {employerJobs.map((job) => <option key={job.silver_job_id} value={job.silver_job_id}>{job.title || `Job ${job.silver_job_id}`}</option>)}
          </select>
        </label>
      </> : <>
        <label>Employer
          <input value={externalEmployer} maxLength={300} onChange={(event) => setExternalEmployer(event.target.value)} placeholder="e.g. CARIAD" />
        </label>
        <label>Job title
          <input value={externalTitle} maxLength={500} onChange={(event) => setExternalTitle(event.target.value)} placeholder="e.g. A.I. Reporting Specialist" />
        </label>
        <label>Job link · optional
          <input type="url" value={externalUrl} maxLength={1200} onChange={(event) => setExternalUrl(event.target.value)} placeholder="https://…" />
        </label>
      </>}

      <label>Applied on
        <input type="date" value={submittedOn} max={localDateToday()} onChange={(event) => setSubmittedOn(event.target.value)} />
      </label>
      <label>Submission channel
        <select value={channel} onChange={(event) => setChannel(event.target.value)}>
          {Object.entries(channelLabel).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </label>
      <label>Note / reference · optional
        <input value={reference} maxLength={240} onChange={(event) => setReference(event.target.value)} placeholder="e.g. portal confirmation or your own note" />
      </label>
      <button type="button" disabled={state === "saving"} onClick={() => void record()}>{state === "saving" ? "Saving …" : "Add manually"}</button>
      {message && <p className={`f5-record-message ${state}`}>{message}</p>}
    </div>
  </details>;
}
export default function F5ApplicationTracking({
  payload,
  focusApplicationId = null,
  onOpenJob,
  onSelectApplication,
  refreshProductTruth,
}: {
  payload: F5ProductPayload;
  focusApplicationId?: number | null;
  onOpenJob?: (silverJobId: number) => void;
  onSelectApplication?: (applicationId: number) => void;
  refreshProductTruth: () => Promise<void>;
}) {
  const tracking = payload.application_tracking;
  const [filter, setFilter] = useState<Filter>("all");
  const [expandedIds, setExpandedIds] = useState<Set<number>>(() => new Set());
  const [correctionState, setCorrectionState] = useState<{
    applicationId: number | null;
    status: "idle" | "saving" | "saved" | "error";
    message: string;
  }>({ applicationId: null, status: "idle", message: "" });
  const [titleDrafts, setTitleDrafts] = useState<Record<number, string>>({});
  const [titleCorrectionState, setTitleCorrectionState] = useState<{
    applicationId: number | null;
    status: "idle" | "saving" | "saved" | "error";
    message: string;
  }>({ applicationId: null, status: "idle", message: "" });
  const applications = tracking?.applications || [];
  const projectedJobByApplicationId = useMemo(() => {
    const projected = new Map<number, number>();
    for (const match of tracking?.job_linkage?.exact_matches || []) {
      if (typeof match.application_id === "number" && typeof match.silver_job_id === "number") {
        projected.set(match.application_id, match.silver_job_id);
      }
    }
    return projected;
  }, [tracking?.job_linkage?.exact_matches]);
  const trackedIds = useMemo(() => {
    const ids = new Set<number>();
    for (const application of applications) {
      if (typeof application.silver_job_id === "number") ids.add(application.silver_job_id);
      const projectedJobId = projectedJobByApplicationId.get(application.application_id);
      if (typeof projectedJobId === "number") ids.add(projectedJobId);
    }
    return ids;
  }, [applications, projectedJobByApplicationId]);
  const visibleJobIds = useMemo(
    () => new Set((payload.job_readiness || []).map((job) => job.silver_job_id)),
    [payload.job_readiness],
  );
  const filtered = useMemo(() => applications.filter((item) => {
    if (filter === "attention") return item.attention_candidate_count > 0;
    if (filter === "closed") return item.effective_stage === "closed";
    if (filter === "active") return item.effective_stage !== "closed";
    return true;
  }), [applications, filter]);
  const grouped = useMemo(() => GROUP_ORDER.map((stage) => ({
    stage,
    applications: filtered.filter((item) => item.effective_stage === stage),
  })).filter((group) => group.applications.length > 0), [filtered]);
  const allFilteredExpanded = filtered.length > 0 && filtered.every((item) => expandedIds.has(item.application_id));

  useEffect(() => {
    if (typeof focusApplicationId !== "number") return;
    if (!applications.some((item) => item.application_id === focusApplicationId)) return;

    setFilter("all");
    setExpandedIds((current) => {
      if (current.has(focusApplicationId)) return current;
      const next = new Set(current);
      next.add(focusApplicationId);
      return next;
    });

    const timer = window.setTimeout(() => {
      document.getElementById(`f5-application-${focusApplicationId}`)?.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [applications, focusApplicationId]);

  function toggleExpanded(applicationId: number) {
    onSelectApplication?.(applicationId);
    setExpandedIds((current) => {
      const next = new Set(current);
      if (next.has(applicationId)) next.delete(applicationId);
      else next.add(applicationId);
      return next;
    });
  }

  async function correctMissingJobTitle(
    applicationId: number,
    employerName: string,
  ) {
    const jobTitle = (titleDrafts[applicationId] || "").trim();
    if (!jobTitle) {
      setTitleCorrectionState({
        applicationId,
        status: "error",
        message: "Enter a job title.",
      });
      return;
    }

    setTitleCorrectionState({ applicationId, status: "saving", message: "" });
    try {
      const response = await fetch("/api/v1/product-v1/application-submission-record", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "correct_application_job_title",
          application_id: applicationId,
          job_title: jobTitle,
          expected_employer_name: employerName,
        }),
      });
      const payload = await response.json() as {
        status?: string;
        reason?: string;
        message?: string;
        error_type?: string;
      };
      if (!response.ok) {
        const detail = payload.reason || payload.message;
        throw new Error(
          detail
            ? `${payload.error_type ? payload.error_type + ": " : ""}${detail}`
            : `HTTP ${response.status}`,
        );
      }
      setTitleCorrectionState({
        applicationId,
        status: "saved",
        message: "Job title saved.",
      });
      await refreshProductTruth();
    } catch (error) {
      setTitleCorrectionState({
        applicationId,
        status: "error",
        message: error instanceof Error ? error.message : "Could not save the job title.",
      });
    }
  }

  async function removeMistakenManualSubmission(applicationId: number) {
    const confirmed = window.confirm(
      "Remove this manual application entry? Mailbox or lifecycle evidence will never be deleted.",
    );
    if (!confirmed) return;

    setCorrectionState({ applicationId, status: "saving", message: "" });
    try {
      const response = await fetch("/api/v1/product-v1/application-submission-record", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "remove_operator_submission_confirmation",
          application_id: applicationId,
        }),
      });
      const payload = await response.json() as {
        status?: string;
        reason?: string;
        message?: string;
        error_type?: string;
        application_deleted?: boolean;
        candidate_evidence_retained?: number;
      };
      if (!response.ok) {
        const detail = payload.reason || payload.message;
        throw new Error(
          detail
            ? `${payload.error_type ? payload.error_type + ": " : ""}${detail}`
            : `HTTP ${response.status}`,
        );
      }
      setCorrectionState({
        applicationId,
        status: "saved",
        message: payload.application_deleted
          ? "Incorrect entry removed."
          : payload.candidate_evidence_retained
            ? "Manual confirmation removed; existing mailbox evidence remains."
            : "Manual confirmation removed.",
      });
      setExpandedIds((current) => {
        const next = new Set(current);
        next.delete(applicationId);
        return next;
      });
      await refreshProductTruth();
    } catch (error) {
      setCorrectionState({
        applicationId,
        status: "error",
        message: error instanceof Error ? error.message : "Correction failed.",
      });
    }
  }

  function toggleAllFiltered() {
    setExpandedIds((current) => {
      const next = new Set(current);
      if (allFilteredExpanded) {
        filtered.forEach((item) => next.delete(item.application_id));
      } else {
        filtered.forEach((item) => next.add(item.application_id));
      }
      return next;
    });
  }

  if (!tracking?.available) return <section className="f5-tracking-shell"><div className="f5-empty"><h2>Application Tracker is not available yet</h2><p>Application tracking data is not available in the current runtime state.</p></div></section>;

  return <section className="f5-tracking-shell" aria-label="Mailbox-first application tracking">
    <header className="f5-tracking-head">
      <div><span>Application lifecycle · mailbox-assisted</span><h2>Application Tracker</h2><p>Mailbox evidence helps discover and update applications. Uncertain signals stay in Review; authoritative corrections remain separate.</p></div>
      <div className="f5-summary-pills"><b>{tracking.summary.application_count}<small>total</small></b><b>{tracking.summary.mailbox_discovered_count || 0}<small>from mailbox</small></b><b className={tracking.summary.attention_count ? "attention" : ""}>{tracking.summary.attention_count}<small>review</small></b></div>
    </header>

    <div className="f5-application-toolbar">
      <nav className="f5-status-tabs" aria-label="Application status filter">
        {(["all", "attention", "active", "closed"] as Filter[]).map((item) => <button key={item} type="button" className={filter === item ? "active" : ""} onClick={() => setFilter(item)}>{item === "all" ? "All" : item === "attention" ? "Review" : item === "active" ? "Active" : "Closed"}</button>)}
      </nav>
      <button type="button" className="f5-density-toggle" onClick={toggleAllFiltered} disabled={filtered.length === 0}>
        {allFilteredExpanded ? "Collapse all" : "Expand all"}
      </button>
    </div>

    {applications.length === 0 ? <div className="f5-empty"><h3>No applications discovered from the mailbox yet</h3><p>After mailbox sync, applications can appear here even when JAP did not know the job beforehand.</p></div> : filtered.length === 0 ? <div className="f5-empty"><h3>No applications in this filter</h3><p>There are currently no entries for the selected status filter.</p></div> : <div className="f5-status-groups">{grouped.map((group) => <section key={group.stage} className={`f5-status-group ${group.stage}`} aria-labelledby={`f5-group-${group.stage}`}>
      <header className="f5-status-group-head"><div><span>Status</span><h3 id={`f5-group-${group.stage}`}>{stageLabel[group.stage]}</h3></div><b>{group.applications.length}</b></header>
      <div className="f5-application-list">{group.applications.map((application) => {
        const warning = attentionMessage(application);
        const totalEvidence = application.evidence_candidates.length;
        const expanded = expandedIds.has(application.application_id);
        const employer = application.display_company_name || application.company_name || "Employer not yet resolved";
        const linkedJobId = application.silver_job_id ?? projectedJobByApplicationId.get(application.application_id) ?? null;
        const projectedLink = application.silver_job_id == null && linkedJobId != null;
        const linkedJobVisible = linkedJobId != null && visibleJobIds.has(linkedJobId);
        const applicationKindLabel = application.application_kind === "unsolicited" ? "Unsolicited application" : null;
        const missingJobTitle = !application.title && !applicationKindLabel;
        const jobTitle = application.title || applicationKindLabel || (linkedJobId ? `Job ${linkedJobId}` : "Job title missing");
        const canUndoManualSubmission =
          application.submission_authority_kind === "operator_confirmation" &&
          application.authoritative_event_count === 0 &&
          (
            application.discovery_kind === "manual_external" ||
            application.prepared_by === "local_operator"
          );
        const correction = correctionState.applicationId === application.application_id
          ? correctionState
          : null;
        const titleCorrection = titleCorrectionState.applicationId === application.application_id
          ? titleCorrectionState
          : null;
        return <article
          key={application.application_id}
          id={`f5-application-${application.application_id}`}
          className={`${application.attention_candidate_count ? "needs-attention " : ""}${expanded ? "expanded" : "compact"}${focusApplicationId === application.application_id ? " focused" : ""}`}
        >
          <button
            type="button"
            className="f5-compact-row"
            aria-expanded={expanded}
            onClick={() => toggleExpanded(application.application_id)}
          >
            <b className={`f5-stage-badge ${application.effective_stage}`}>{stageLabel[application.effective_stage]}</b>
            <span className="f5-compact-job"><strong>{jobTitle}</strong><small>{employer}</small></span>
            <span className="f5-expand-indicator" aria-hidden="true">{expanded ? "⌃" : "⌄"}</span>
          </button>
          {expanded && <div className="f5-expanded-body">
            <div className="f5-card-head"><div><span>{employer}</span><h3>{jobTitle}</h3><small>{application.silver_job_id != null ? "Linked to a JAP job" : projectedLink ? "Read-only match to a JAP job" : "Discovered outside JAP"}</small></div></div>
            <StageStrip stage={application.effective_stage} />
            <div className="f5-card-meta"><span><small>Last observed</small>{formatDate(application.observed_at || application.discovered_at)}</span><span><small>Signal</small>{application.observed_event_class || "—"}</span><span><small>Evidence</small>{application.attention_candidate_count ? `${application.attention_candidate_count} review · ${totalEvidence} total` : totalEvidence ? `${totalEvidence} qualified` : "none"}</span></div>
            <div className="f5-job-meta">
              <span><small>Discovered</small>{formatDate(application.discovered_at)}</span>
              {applicationKindLabel ? <span><small>Application type</small>{applicationKindLabel}</span> : null}
              <span><small>Employer evidence</small>{application.employer_evidence_source || "—"}</span>
              <span><small>Communication domain</small>{application.counterparty_domain || application.sender_domain || "—"}</span>
              {application.source_url ? <a href={application.source_url} target="_blank" rel="noreferrer"><small>Job / application source</small>Open ↗</a> : <span><small>Job / application source</small>—</span>}
            </div>
            {linkedJobVisible && linkedJobId != null && onOpenJob
              ? <button type="button" className="f5-open-linked-job" onClick={() => onOpenJob(linkedJobId)}>Open in All jobs ↔</button>
              : linkedJobId != null
                ? <div className="f5-linked-job-outside-view">Silver #{linkedJobId} is linked but outside the current All jobs view.</div>
                : null}
            {warning && <div className="f5-attention-note">{warning}</div>}
            {missingJobTitle && application.discovery_kind === "mailbox_observed" && <div className="f5-title-correction">
              <div>
                <b>Job title missing</b>
                <small>The mailbox confirmation contains no title. Add only the job title you actually applied for.</small>
              </div>
              <input
                value={titleDrafts[application.application_id] || ""}
                maxLength={500}
                onChange={(event) => setTitleDrafts((current) => ({
                  ...current,
                  [application.application_id]: event.target.value,
                }))}
                placeholder="Job title"
              />
              <button
                type="button"
                disabled={titleCorrection?.status === "saving"}
                onClick={() => void correctMissingJobTitle(application.application_id, employer)}
              >
                {titleCorrection?.status === "saving" ? "Saving …" : "Save title"}
              </button>
            </div>}
            {titleCorrection?.message && <p className={`f5-title-correction-message ${titleCorrection.status}`}>{titleCorrection.message}</p>}
            {canUndoManualSubmission && <div className="f5-manual-correction">
              <div>
                <b>Correct manual entry</b>
                <small>Removes your manual application confirmation. Mailbox evidence and later lifecycle truth are preserved.</small>
              </div>
              <button
                type="button"
                disabled={correction?.status === "saving"}
                onClick={() => void removeMistakenManualSubmission(application.application_id)}
              >
                {correction?.status === "saving" ? "Removing …" : "Remove incorrect entry"}
              </button>
            </div>}
            {correction?.message && <p className={`f5-correction-message ${correction.status}`}>{correction.message}</p>}
          </div>}
        </article>;
      })}</div>
    </section>)}</div>}

    {tracking.summary.unmatched_candidate_count > 0 && <div className="f5-unmatched-warning">{tracking.summary.unmatched_candidate_count} mailbox signals cannot yet be matched to one application with confidence and remain in Review.</div>}
    <RecordSubmission jobs={payload.job_readiness || []} trackedIds={trackedIds} onRecorded={refreshProductTruth} />
    <footer className="f5-truth-boundary">Mailbox read-only · no email actions · no automatic application · observed status with separate correction and audit truth</footer>
  </section>;
}
