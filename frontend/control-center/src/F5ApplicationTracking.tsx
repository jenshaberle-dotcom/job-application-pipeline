import { useMemo, useState } from "react";
import "./f5-application-tracking.css";

export type F5TrackingJob = {
  silver_job_id: number;
  title?: string | null;
  company_name?: string | null;
  source_url?: string | null;
};

type EvidenceCandidate = {
  candidate_id?: number | null;
  candidate_class?: string | null;
  match_status?: string | null;
  confidence?: number | null;
  ambiguity_reason?: string | null;
  review_status?: string | null;
  created_at?: string | null;
  evidence?: Record<string, unknown>;
  authority?: string;
};

type TrackedApplication = {
  application_id: number;
  silver_job_id: number;
  title?: string | null;
  company_name?: string | null;
  display_company_name?: string | null;
  source_url?: string | null;
  prepared_at?: string | null;
  submitted_at?: string | null;
  submission_channel?: string | null;
  authoritative_stage: "prepared" | "applied" | "reply" | "interview" | "offer" | "closed";
  authoritative_event_count: number;
  attention_candidate_count: number;
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
      attention_count: number;
      unmatched_candidate_count: number;
      stage_counts: Record<string, number>;
    };
    applications: TrackedApplication[];
    unmatched_evidence_candidates: EvidenceCandidate[];
    boundaries: Record<string, boolean>;
  };
};

type Filter = "all" | "attention" | "active" | "closed";
const STAGES = ["prepared", "applied", "reply", "interview", "offer", "closed"] as const;
const stageLabel: Record<(typeof STAGES)[number], string> = {
  prepared: "Prepared",
  applied: "Applied",
  reply: "Reply",
  interview: "Interview",
  offer: "Offer",
  closed: "Closed",
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

function StageStrip({ stage }: { stage: TrackedApplication["authoritative_stage"] }) {
  const current = STAGES.indexOf(stage);
  return <div className="f5-stage-strip" aria-label={`Autoritativer Status ${stageLabel[stage]}`}>
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
    <summary>Bereits versendete Bewerbung erfassen</summary>
    <div className="f5-record-boundary"><b>Nur protokollieren.</b> JAP sendet hier keine Bewerbung und keine E-Mail.</div>
    {available.length === 0 ? <p>Alle aktuell sichtbaren Jobs sind bereits einem Application-Record zugeordnet.</p> : <div className="f5-record-grid">
      <label>Job<select value={jobId} onChange={(event) => setJobId(event.target.value)}>{available.map((job) => <option key={job.silver_job_id} value={job.silver_job_id}>{job.company_name || "Unbekannt"} · {job.title || `Job ${job.silver_job_id}`}</option>)}</select></label>
      <label>Versendet am<input type="datetime-local" value={submittedAt} onChange={(event) => setSubmittedAt(event.target.value)} /></label>
      <label>Weg<select value={channel} onChange={(event) => setChannel(event.target.value)}>{Object.entries(channelLabel).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>Eigene Referenz<input value={reference} maxLength={240} onChange={(event) => setReference(event.target.value)} placeholder="z. B. Portal-Bestätigung / Notiz" /></label>
      <button type="button" disabled={state === "saving"} onClick={() => void record()}>{state === "saving" ? "Erfasse …" : "Als bereits versendet erfassen"}</button>
      {message && <p className={`f5-record-message ${state}`}>{message}</p>}
    </div>}
  </details>;
}

export default function F5ApplicationTracking({ payload }: { payload: F5ProductPayload }) {
  const tracking = payload.application_tracking;
  const [filter, setFilter] = useState<Filter>("all");
  const applications = tracking?.applications || [];
  const trackedIds = useMemo(() => new Set(applications.map((item) => item.silver_job_id)), [applications]);
  const filtered = useMemo(() => applications.filter((item) => {
    if (filter === "attention") return item.attention_candidate_count > 0;
    if (filter === "closed") return item.authoritative_stage === "closed";
    if (filter === "active") return item.authoritative_stage !== "closed";
    return true;
  }), [applications, filter]);

  if (!tracking?.available) return <section className="f5-tracking-shell"><div className="f5-empty"><h2>Application Tracking noch nicht verfügbar</h2><p>Die autoritative F5-Datenstruktur ist in diesem Runtime-Zustand nicht verfügbar.</p></div></section>;

  return <section className="f5-tracking-shell" aria-label="Evidence-first application tracking">
    <header className="f5-tracking-head">
      <div><span>F5 · Application Lifecycle</span><h2>Bewerbungen</h2><p>Autoritativer Status und Kommunikations-Evidence bleiben getrennt.</p></div>
      <div className="f5-summary-pills"><b>{tracking.summary.application_count}<small>gesamt</small></b><b>{tracking.summary.submitted_count}<small>versendet</small></b><b className={tracking.summary.attention_count ? "attention" : ""}>{tracking.summary.attention_count}<small>prüfen</small></b></div>
    </header>

    <nav className="f5-status-tabs" aria-label="Application status filter">
      {(["all", "attention", "active", "closed"] as Filter[]).map((item) => <button key={item} type="button" className={filter === item ? "active" : ""} onClick={() => setFilter(item)}>{item === "all" ? "Alle" : item === "attention" ? "Prüfen" : item === "active" ? "Aktiv" : "Geschlossen"}</button>)}
    </nav>

    {applications.length === 0 ? <div className="f5-empty"><h3>Noch keine erfassten Bewerbungen</h3><p>JAP erfindet keinen Applied-Status. Eine Bewerbung erscheint hier erst, wenn ihre Einreichung ausdrücklich als bereits erfolgt bestätigt wurde.</p></div> : <div className="f5-application-list">{filtered.map((application) => <article key={application.application_id} className={application.attention_candidate_count ? "needs-attention" : ""}>
      <div className="f5-card-head"><div><span>{application.display_company_name || application.company_name || "Unbekannter Arbeitgeber"}</span><h3>{application.title || `Job ${application.silver_job_id}`}</h3></div><b className={`f5-stage-badge ${application.authoritative_stage}`}>{stageLabel[application.authoritative_stage]}</b></div>
      <StageStrip stage={application.authoritative_stage} />
      <div className="f5-card-meta"><span><small>Versendet</small>{formatDate(application.submitted_at)}</span><span><small>Weg</small>{application.submission_channel ? channelLabel[application.submission_channel] || application.submission_channel : "—"}</span><span><small>Evidence</small>{application.attention_candidate_count ? `${application.attention_candidate_count} zu prüfen` : "keine offene"}</span></div>
      {application.attention_candidate_count > 0 && <div className="f5-attention-note">Kommunikations-Evidence wartet auf Prüfung. Der Status wurde dadurch nicht verändert.</div>}
      <details className="f5-evidence-details"><summary>Details & Evidence</summary><div><p><b>Status-Authority:</b> {application.stage_authority}</p><p><b>Autoritative Events:</b> {application.authoritative_event_count}</p>{application.evidence_candidates.length === 0 ? <p>Keine Kommunikations-Evidence hinterlegt.</p> : application.evidence_candidates.map((candidate) => <p key={candidate.candidate_id || `${candidate.candidate_class}-${candidate.created_at}`}><b>{candidate.candidate_class || "ambiguous"}</b> · {candidate.review_status || "unreviewed"} · Evidence only{candidate.confidence != null ? ` · ${Math.round(candidate.confidence * 100)} %` : ""}</p>)}</div></details>
    </article>)}</div>}

    {tracking.summary.unmatched_candidate_count > 0 && <div className="f5-unmatched-warning">{tracking.summary.unmatched_candidate_count} Kommunikations-Evidence kann keiner Bewerbung eindeutig zugeordnet werden und erzeugt keinen Status.</div>}
    <RecordSubmission jobs={payload.job_readiness || []} trackedIds={trackedIds} />
    <footer className="f5-truth-boundary">Keine automatische Bewerbung · keine E-Mail-Aktion · Communication Evidence ≠ Status-Authority</footer>
  </section>;
}
