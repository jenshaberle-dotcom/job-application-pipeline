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
  prepared_at?: string | null;
  submitted_at?: string | null;
  submission_channel?: string | null;
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
  prepared: "Erkannt",
  applied: "Beworben",
  reply: "Antwort",
  interview: "Interview",
  offer: "Angebot",
  closed: "Geschlossen",
};
const channelLabel: Record<string, string> = {
  employer_portal: "Arbeitgeber-Portal",
  email: "E-Mail",
  external_platform: "Externe Plattform",
  manual_other: "Anderer manueller Weg",
};

function localDateTimeNow() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 16);
}

function formatDate(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("de-DE", { dateStyle: "medium", timeStyle: "short" });
}

function attentionMessage(application: TrackedApplication) {
  const count = application.attention_candidate_count;
  const total = application.evidence_candidates.length;
  if (count <= 0) return null;
  const plural = count === 1 ? "Mail-Signal benötigt" : "Mail-Signale benötigen";
  if (application.observed_stage) {
    return `${count} von ${total || count} ${plural} Prüfung. Der angezeigte Status „${stageLabel[application.effective_stage]}“ stammt aus separat qualifizierter Evidence.`;
  }
  return `${count} von ${total || count} ${plural} Prüfung. Bis zur Klärung bleibt der Status auf der vorhandenen autoritativen Wahrheit.`;
}

function StageStrip({ stage }: { stage: Stage }) {
  const current = STAGES.indexOf(stage);
  return <div className="f5-stage-strip" aria-label={`Aktueller Bewerbungsstatus ${stageLabel[stage]}`}>
    {STAGES.map((item, index) => <span key={item} className={index <= current ? "reached" : "future"}>
      <i aria-hidden="true" />{stageLabel[item]}
    </span>)}
  </div>;
}

function RecordSubmission({ jobs, trackedIds }: { jobs: F5TrackingJob[]; trackedIds: Set<number> }) {
  const available = jobs.filter((job) => !trackedIds.has(job.silver_job_id));
  const [jobId, setJobId] = useState(available[0]?.silver_job_id ? String(available[0].silver_job_id) : "");
  const [submittedAt, setSubmittedAt] = useState(localDateTimeNow());
  const [channel, setChannel] = useState("employer_portal");
  const [reference, setReference] = useState("");
  const [state, setState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [message, setMessage] = useState("");

  async function record() {
    if (!jobId || !submittedAt || !reference.trim()) {
      setState("error");
      setMessage("Job, Zeitpunkt und eigene Referenz sind erforderlich.");
      return;
    }
    setState("saving");
    setMessage("");
    try {
      const response = await fetch("/api/v1/product-v1/application-submission-record", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "record_operator_confirmed_submission",
          silver_job_id: Number(jobId),
          submitted_at: new Date(submittedAt).toISOString(),
          submission_channel: channel,
          authority_reference: reference.trim(),
        }),
      });
      const payload = await response.json() as { status?: string; reason?: string };
      if (!response.ok) throw new Error(payload.reason || `HTTP ${response.status}`);
      setState("saved");
      setMessage(payload.status === "already_recorded" ? "War bereits identisch erfasst." : "Als bereits versendet erfasst.");
      window.setTimeout(() => window.location.reload(), 450);
    } catch (error) {
      setState("error");
      setMessage(error instanceof Error ? error.message : "Erfassung fehlgeschlagen.");
    }
  }

  return <details className="f5-record-submission">
    <summary>Manuell ergänzen · Fallback</summary>
    <div className="f5-record-boundary"><b>Nur falls die Mailbox etwas nicht erkennt.</b> JAP sendet hier keine Bewerbung und keine E-Mail.</div>
    {available.length === 0 ? <p>Kein aktuell sichtbarer JAP-Job ist für eine manuelle Ergänzung übrig.</p> : <div className="f5-record-grid">
      <label>Job<select value={jobId} onChange={(event) => setJobId(event.target.value)}>{available.map((job) => <option key={job.silver_job_id} value={job.silver_job_id}>{job.company_name || "Unbekannt"} · {job.title || `Job ${job.silver_job_id}`}</option>)}</select></label>
      <label>Versendet am<input type="datetime-local" value={submittedAt} onChange={(event) => setSubmittedAt(event.target.value)} /></label>
      <label>Weg<select value={channel} onChange={(event) => setChannel(event.target.value)}>{Object.entries(channelLabel).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>Eigene Referenz<input value={reference} maxLength={240} onChange={(event) => setReference(event.target.value)} placeholder="z. B. Portal-Bestätigung / Notiz" /></label>
      <button type="button" disabled={state === "saving"} onClick={() => void record()}>{state === "saving" ? "Erfasse …" : "Manuell erfassen"}</button>
      {message && <p className={`f5-record-message ${state}`}>{message}</p>}
    </div>}
  </details>;
}

export default function F5ApplicationTracking({
  payload,
  focusApplicationId = null,
  onOpenJob,
}: {
  payload: F5ProductPayload;
  focusApplicationId?: number | null;
  onOpenJob?: (silverJobId: number) => void;
}) {
  const tracking = payload.application_tracking;
  const [filter, setFilter] = useState<Filter>("all");
  const [expandedIds, setExpandedIds] = useState<Set<number>>(() => new Set());
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
    setExpandedIds((current) => {
      const next = new Set(current);
      if (next.has(applicationId)) next.delete(applicationId);
      else next.add(applicationId);
      return next;
    });
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

  if (!tracking?.available) return <section className="f5-tracking-shell"><div className="f5-empty"><h2>Application Tracking noch nicht verfügbar</h2><p>Die F5-Datenstruktur ist in diesem Runtime-Zustand nicht verfügbar.</p></div></section>;

  return <section className="f5-tracking-shell" aria-label="Mailbox-first application tracking">
    <header className="f5-tracking-head">
      <div><span>F5 · Mailbox Application Tracking</span><h2>Bewerbungen</h2><p>Die Mailbox entdeckt und verfolgt Bewerbungen. Unsichere Signale landen in Prüfen; autoritative Korrekturen bleiben separat.</p></div>
      <div className="f5-summary-pills"><b>{tracking.summary.application_count}<small>gesamt</small></b><b>{tracking.summary.mailbox_discovered_count || 0}<small>aus Mailbox</small></b><b className={tracking.summary.attention_count ? "attention" : ""}>{tracking.summary.attention_count}<small>prüfen</small></b></div>
    </header>

    <div className="f5-application-toolbar">
      <nav className="f5-status-tabs" aria-label="Application status filter">
        {(["all", "attention", "active", "closed"] as Filter[]).map((item) => <button key={item} type="button" className={filter === item ? "active" : ""} onClick={() => setFilter(item)}>{item === "all" ? "Alle" : item === "attention" ? "Prüfen" : item === "active" ? "Aktiv" : "Geschlossen"}</button>)}
      </nav>
      <button type="button" className="f5-density-toggle" onClick={toggleAllFiltered} disabled={filtered.length === 0}>
        {allFilteredExpanded ? "Alle einklappen" : "Alle aufklappen"}
      </button>
    </div>

    {applications.length === 0 ? <div className="f5-empty"><h3>Noch keine Bewerbungen aus der Mailbox erkannt</h3><p>Nach dem Mailbox-Sync erscheinen hier auch Bewerbungen auf Stellen, die JAP vorher nie gesehen hat.</p></div> : filtered.length === 0 ? <div className="f5-empty"><h3>Keine Bewerbungen in diesem Filter</h3><p>Für den gewählten Statusfilter gibt es aktuell keine Treffer.</p></div> : <div className="f5-status-groups">{grouped.map((group) => <section key={group.stage} className={`f5-status-group ${group.stage}`} aria-labelledby={`f5-group-${group.stage}`}>
      <header className="f5-status-group-head"><div><span>Status</span><h3 id={`f5-group-${group.stage}`}>{stageLabel[group.stage]}</h3></div><b>{group.applications.length}</b></header>
      <div className="f5-application-list">{group.applications.map((application) => {
        const warning = attentionMessage(application);
        const totalEvidence = application.evidence_candidates.length;
        const expanded = expandedIds.has(application.application_id);
        const employer = application.display_company_name || application.company_name || "Arbeitgeber noch nicht ableitbar";
        const linkedJobId = application.silver_job_id ?? projectedJobByApplicationId.get(application.application_id) ?? null;
        const projectedLink = application.silver_job_id == null && linkedJobId != null;
        const jobTitle = application.title || (linkedJobId ? `Job ${linkedJobId}` : "Jobtitel noch nicht ableitbar");
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
            <div className="f5-card-head"><div><span>{employer}</span><h3>{jobTitle}</h3><small>{application.silver_job_id != null ? "Mit JAP-Job verknüpft" : projectedLink ? "Exakt read-only einem JAP-Job zugeordnet" : "Außerhalb JAP entdeckt"}</small></div><b className={`f5-stage-badge ${application.effective_stage}`}>{stageLabel[application.effective_stage]}</b></div>
            <StageStrip stage={application.effective_stage} />
            <div className="f5-card-meta"><span><small>Zuletzt beobachtet</small>{formatDate(application.observed_at || application.discovered_at)}</span><span><small>Signal</small>{application.observed_event_class || "—"}</span><span><small>Evidence</small>{application.attention_candidate_count ? `${application.attention_candidate_count} prüfen · ${totalEvidence} gesamt` : totalEvidence ? `${totalEvidence} qualifiziert` : "keine"}</span></div>
            <div className="f5-job-meta">
              <span><small>Entdeckt</small>{formatDate(application.discovered_at)}</span>
              <span><small>Arbeitgeber-Hinweis</small>{application.employer_evidence_source || "—"}</span>
              <span><small>Kommunikations-Domain</small>{application.counterparty_domain || application.sender_domain || "—"}</span>
              {application.source_url ? <a href={application.source_url} target="_blank" rel="noreferrer"><small>Job-/Bewerbungsquelle</small>Öffnen ↗</a> : <span><small>Job-/Bewerbungsquelle</small>—</span>}
            </div>
            {linkedJobId != null && onOpenJob && <button type="button" className="f5-open-linked-job" onClick={() => onOpenJob(linkedJobId)}>In All jobs öffnen ↔</button>}
            {warning && <div className="f5-attention-note">{warning}</div>}
            <details className="f5-evidence-details"><summary>Details & Evidence</summary><div><p><b>Beobachteter Status:</b> {stageLabel[application.effective_stage]} · {application.effective_stage_basis || "—"}</p><p><b>Autoritative Korrektur:</b> {stageLabel[application.authoritative_stage]}</p><p><b>Autoritative Events:</b> {application.authoritative_event_count}</p>{application.evidence_candidates.length === 0 ? <p>Keine Kommunikations-Evidence hinterlegt.</p> : application.evidence_candidates.map((candidate) => <p key={candidate.candidate_id || `${candidate.candidate_class}-${candidate.created_at}`} className={candidate.requires_review ? "review-required" : "qualified-evidence"}><b>{candidate.candidate_class || "ambiguous"}</b> · {candidate.requires_review ? "Prüfung nötig" : "qualifiziert"}{candidate.confidence != null ? ` · ${Math.round(candidate.confidence * 100)} %` : ""} · {formatDate(candidate.observed_at)}</p>)}</div></details>
          </div>}
        </article>;
      })}</div>
    </section>)}</div>}

    {tracking.summary.unmatched_candidate_count > 0 && <div className="f5-unmatched-warning">{tracking.summary.unmatched_candidate_count} Mail-Signale können noch keiner Bewerbung eindeutig zugeordnet werden und landen in Prüfen.</div>}
    <RecordSubmission jobs={payload.job_readiness || []} trackedIds={trackedIds} />
    <footer className="f5-truth-boundary">Mailbox read-only · keine E-Mail-Aktion · keine automatische Bewerbung · beobachteter Status mit separater Korrektur-/Audit-Wahrheit</footer>
  </section>;
}
