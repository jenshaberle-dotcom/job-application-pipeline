import { useEffect, useMemo, useState } from "react";
import "./demo-application-workspace.css";

type TopJob = {
  silver_job_id: number;
  product_rank?: number;
  title?: string | null;
  company_name?: string | null;
  city?: string | null;
  overall_quality_score?: number | null;
};

type ProductTruth = {
  top_jobs?: TopJob[];
  application_sources_ready?: {
    base_cv?: boolean;
    base_application_letter?: boolean;
  };
};

type ClaimReference = {
  capability_tag?: string;
  evidence?: string;
};

type ClaimPlanEntry = {
  fact_key?: string;
  statement?: string;
  matched_capability_tags?: string[];
  job_references?: ClaimReference[];
};

type ApplicationWorkspacePayload = {
  status?: string;
  reason?: string;
  blocked_reasons?: string[];
  workspace?: {
    target?: {
      silver_job_id?: number;
      product_rank?: number;
      title?: string;
      company_name?: string;
      source_url?: string;
    };
    generation_ready?: boolean;
    blocked_reasons?: string[];
    claim_plan?: ClaimPlanEntry[];
    source_manifest?: {
      candidate_fact_keys?: string[];
      documents?: Array<{
        document_type?: string;
        source_label?: string;
        status?: string;
      }>;
    };
  };
  live_job_evidence?: {
    final_url?: string;
    fetched_title?: string;
    detail_sha256?: string;
  };
  boundaries?: Record<string, boolean | number>;
};

type DraftFragment = {
  kind?: string;
  text?: string;
  candidate_fact_keys?: string[];
  job_evidence?: Array<{ evidence?: string }>;
};

type DraftMode = "provider_validated" | "deterministic_evidence_first";

type DraftPayload = {
  status?: string;
  reason?: string;
  blocked_reasons?: string[];
  draft_mode?: DraftMode;
  fallback_reason?: string | null;
  package?: {
    status?: string;
    fragments?: DraftFragment[];
    rationale?: string;
    candidate_fact_keys_used?: string[];
  } | null;
  provider_requests?: number;
  database_writes?: number;
  submission_writes?: number;
  send_actions?: number;
};

const normalized = (value: string | undefined | null) => (value || "").replaceAll("_", " ");
const percent = (value: number | undefined | null) => value == null ? "—" : `${Math.round(value)}%`;

async function readJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers || {}),
    },
  });
  const payload = await response.json() as T;
  if (!response.ok) {
    const reason = (payload as { reason?: string; blocked_reasons?: string[] }).reason
      || (payload as { blocked_reasons?: string[] }).blocked_reasons?.join(", ")
      || `API returned ${response.status}`;
    throw new Error(reason);
  }
  return payload;
}

function fragmentGroup(kind: string | undefined) {
  return kind?.startsWith("cv_") ? "CV" : "Application letter";
}

function draftModeLabel(mode: DraftMode | undefined) {
  if (mode === "provider_validated") return "PROVIDER-VALIDATED";
  if (mode === "deterministic_evidence_first") return "EVIDENCE-FIRST · PROVIDER-FREE";
  return "SOURCE-GROUNDED";
}

export default function DemoApplicationWorkspace() {
  const [open, setOpen] = useState(false);
  const [topJobs, setTopJobs] = useState<TopJob[]>([]);
  const [sourceReadiness, setSourceReadiness] = useState<ProductTruth["application_sources_ready"]>({});
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [workspace, setWorkspace] = useState<ApplicationWorkspacePayload | null>(null);
  const [draft, setDraft] = useState<DraftPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    readJson<ProductTruth>("/api/v1/product-v1")
      .then((payload) => {
        if (!active) return;
        const jobs = Array.isArray(payload.top_jobs) ? payload.top_jobs.slice(0, 5) : [];
        setTopJobs(jobs);
        setSourceReadiness(payload.application_sources_ready || {});
        setSelectedId(jobs[0]?.silver_job_id ?? null);
      })
      .catch((reason: unknown) => {
        if (active) setError(String(reason));
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!open || selectedId == null) return;
    let active = true;
    setLoading(true);
    setDraft(null);
    setError(null);
    readJson<ApplicationWorkspacePayload>(`/api/v1/product-v1/application-workspace?silver_job_id=${selectedId}`)
      .then((payload) => { if (active) setWorkspace(payload); })
      .catch((reason: unknown) => { if (active) { setWorkspace(null); setError(String(reason)); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [open, selectedId]);

  const selectedJob = useMemo(
    () => topJobs.find((job) => job.silver_job_id === selectedId) || topJobs[0] || null,
    [selectedId, topJobs],
  );

  const claimPlan = workspace?.workspace?.claim_plan || [];
  const documents = workspace?.workspace?.source_manifest?.documents || [];
  const workspaceBlockers = workspace?.workspace?.blocked_reasons || workspace?.blocked_reasons || [];
  const draftFragments = draft?.package?.fragments || [];
  const cvFragments = draftFragments.filter((item) => fragmentGroup(item.kind) === "CV");
  const letterFragments = draftFragments.filter((item) => fragmentGroup(item.kind) === "Application letter");
  const generationReady = workspace?.status === "ready" && workspace.workspace?.generation_ready === true && claimPlan.length > 0;

  const generateDraft = async () => {
    if (selectedId == null || !generationReady) return;
    setDrafting(true);
    setError(null);
    try {
      const payload = await readJson<DraftPayload>("/api/v1/product-v1/application-draft", {
        method: "POST",
        body: JSON.stringify({ action: "generate_review_draft", silver_job_id: selectedId }),
      });
      setDraft(payload);
    } catch (reason) {
      setError(String(reason));
    } finally {
      setDrafting(false);
    }
  };

  if (!open) {
    return <button
      type="button"
      className="demo-application-launcher"
      disabled={topJobs.length === 0}
      onClick={() => setOpen(true)}
      title={topJobs.length ? "Open source-grounded application preparation" : "No authoritative Top-5 job available"}
    >
      <span>Ready to apply</span>
      <strong>{topJobs.length ? `${topJobs.length} Top-5 job${topJobs.length === 1 ? "" : "s"}` : "No Top-5 job"}</strong>
    </button>;
  }

  return <div className="demo-application-backdrop" role="presentation" onMouseDown={(event) => {
    if (event.currentTarget === event.target) setOpen(false);
  }}>
    <section className="demo-application-workspace" role="dialog" aria-modal="true" aria-label="Application Workspace">
      <header className="demo-application-header">
        <div>
          <span className="demo-eyebrow">DEMO-001 · final product step</span>
          <h1>Application Workspace</h1>
          <p>From authoritative Top 5 to a source-grounded application draft.</p>
        </div>
        <button type="button" className="demo-close" onClick={() => setOpen(false)}>×</button>
      </header>

      <div className="demo-application-truth-strip">
        <span><i className="ok" /> Top-5 authority</span>
        <span><i className={sourceReadiness?.base_cv ? "ok" : ""} /> Base CV {sourceReadiness?.base_cv ? "approved" : "required"}</span>
        <span><i className={sourceReadiness?.base_application_letter ? "ok" : ""} /> Base letter {sourceReadiness?.base_application_letter ? "approved" : "required"}</span>
        <span><i /> REVIEW REQUIRED</span>
        <span><i /> NO AUTO-SUBMIT</span>
      </div>

      {topJobs.length > 1 && <nav className="demo-job-picker" aria-label="Top jobs">
        {topJobs.map((job) => <button
          type="button"
          key={job.silver_job_id}
          className={job.silver_job_id === selectedId ? "active" : ""}
          onClick={() => setSelectedId(job.silver_job_id)}
        >
          <b>#{job.product_rank || "–"}</b>
          <span>{job.company_name || "Unknown employer"}</span>
          <small>{job.title || "Untitled job"}</small>
        </button>)}
      </nav>}

      {selectedJob && <section className="demo-selected-job">
        <span className="rank">#{selectedJob.product_rank || "–"}</span>
        <div><span className="demo-eyebrow">Selected authoritative job</span><h2>{selectedJob.title}</h2><p>{selectedJob.company_name} · {selectedJob.city || "Location unconfirmed"}</p></div>
        <strong>{percent(selectedJob.overall_quality_score)}<small>profile fit</small></strong>
      </section>}

      {loading && <div className="demo-loading">Binding live vacancy evidence, Candidate Facts and approved source documents…</div>}
      {error && <div className="demo-error"><b>Fail closed</b><span>{error}</span></div>}

      {!loading && workspace && <div className="demo-application-grid">
        <article className="demo-workspace-card">
          <header><span className="demo-eyebrow">1 · Source-grounded context</span><h3>{generationReady ? "Ready for drafting" : "Context blocked"}</h3></header>
          <div className="demo-readiness-list">
            <div><span>Employer-origin vacancy</span><b>{workspace.live_job_evidence?.fetched_title || "validated source"}</b></div>
            <div><span>Candidate Fact matches</span><b>{claimPlan.length}</b></div>
            <div><span>Approved source documents</span><b>{documents.length}/2</b></div>
            <div><span>Detail fingerprint</span><code>{workspace.live_job_evidence?.detail_sha256?.slice(0, 12) || "—"}</code></div>
          </div>
          {workspaceBlockers.length > 0 && <div className="demo-blockers"><b>Generation blockers</b>{workspaceBlockers.map((item) => <span key={item}>{normalized(item)}</span>)}</div>}
          {claimPlan.length > 0 && <div className="demo-claim-plan"><span className="demo-eyebrow">Matched evidence</span>{claimPlan.slice(0, 5).map((entry) => <div key={entry.fact_key}><b>{entry.fact_key}</b><p>{entry.statement}</p><small>{entry.job_references?.map((reference) => reference.evidence).filter(Boolean).join(" · ") || "No exact vacancy match"}</small></div>)}</div>}
          <button type="button" className="demo-generate-button" disabled={!generationReady || drafting} onClick={() => void generateDraft()}>
            {drafting ? "Preparing review draft…" : draft?.status === "draft_for_review" ? "Regenerate review draft" : "Prepare application draft"}
          </button>
          <p className="demo-boundary-note">Drafting starts only after this context is ready. A bounded provider may polish the draft; if unavailable, a provider-free evidence-first version remains reviewable. Nothing is submitted automatically.</p>
        </article>

        <article className="demo-workspace-card demo-draft-card">
          <header><span className="demo-eyebrow">2 · Prepared application</span><h3>{draft?.status === "draft_for_review" ? "Draft ready for your review" : "Waiting for operator action"}</h3></header>
          {draft?.status === "draft_for_review" && draft.package ? <>
            <div className="demo-draft-badge">{draftModeLabel(draft.draft_mode)} · REVIEW REQUIRED · NO SUBMISSION AUTHORITY</div>
            {draft.package.rationale && <p className="demo-boundary-note">{draft.package.rationale}</p>}
            {draft.draft_mode === "deterministic_evidence_first" && draft.fallback_reason && <p className="demo-boundary-note">Fallback reason: {normalized(draft.fallback_reason)}. Candidate claims remain copied from approved Candidate Facts; vacancy claims remain tied to exact current evidence.</p>}
            <section><h4>CV adaptation</h4>{cvFragments.map((fragment, index) => <div className="demo-draft-fragment" key={`${fragment.kind}-${index}`}><span>{normalized(fragment.kind)}</span><p>{fragment.text}</p><small>Facts: {fragment.candidate_fact_keys?.join(", ") || "—"}</small></div>)}</section>
            <section><h4>Application letter</h4>{letterFragments.map((fragment, index) => <div className="demo-draft-fragment" key={`${fragment.kind}-${index}`}><span>{normalized(fragment.kind)}</span><p>{fragment.text}</p>{fragment.job_evidence?.length ? <small>Vacancy evidence: “{fragment.job_evidence.map((item) => item.evidence).filter(Boolean).join(" · ")}”</small> : null}</div>)}</section>
            <footer><span>Provider requests: {draft.provider_requests ?? 0}</span><span>DB writes: {draft.database_writes ?? 0}</span><span>Submission writes: {draft.submission_writes ?? 0}</span><span>Send actions: {draft.send_actions ?? 0}</span></footer>
          </> : <div className="demo-empty-draft"><strong>Here ends the demo journey.</strong><p>Once all factual gates pass, one explicit click produces a reviewable CV and letter draft. Provider provenance is shown explicitly and nothing is sent.</p></div>}
        </article>
      </div>}
    </section>
  </div>;
}