import { useEffect, useMemo, useState } from "react";
import { useProductTruth } from "./ProductTruthContext";
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
  template_authority?: {
    status?: string;
    layout_policy?: string;
    legacy_template_authority?: boolean;
    templates?: Array<{
      document_type?: string;
      canonical_filename?: string;
      sha256?: string;
      exact_authority_match?: boolean;
      editable_text_zone_count?: number;
    }>;
  };
  boundaries?: Record<string, boolean | number>;
};

type DraftFragment = {
  kind?: string;
  text?: string;
  candidate_fact_keys?: string[];
  job_evidence?: Array<{ evidence?: string }>;
};

type DraftMode =
  | "provider_validated"
  | "provider_validated_quality_v2"
  | "provider_validated_quality_v3"
  | "deterministic_evidence_first";

type DraftPayload = {
  status?: string;
  reason?: string;
  blocked_reasons?: string[];
  draft_mode?: DraftMode;
  fallback_reason?: string | null;
  base_document_text_shared_with_provider?: boolean;
  package?: {
    status?: string;
    fragments?: DraftFragment[];
    rationale?: string;
    candidate_fact_keys_used?: string[];
  } | null;
  render_status?: string;
  legacy_generic_document_export?: boolean;
  provider_requests?: number;
  database_writes?: number;
  submission_writes?: number;
  send_actions?: number;
};

const normalized = (value: string | undefined | null) => (value || "").replaceAll("_", " ");
const percent = (value: number | undefined | null) => value == null ? "—" : `${Math.round(value)}`;

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
  if (mode === "provider_validated_quality_v3") return "BASE-DOCUMENT ADAPTED";
  if (mode === "provider_validated_quality_v2" || mode === "provider_validated") return "PROVIDER-VALIDATED";
  if (mode === "deterministic_evidence_first") return "EVIDENCE-FIRST · PROVIDER-FREE";
  return "SOURCE-GROUNDED";
}

function readinessTone(ready: boolean) {
  return ready ? "ready" : "blocked";
}

export default function DemoApplicationWorkspace() {
  const { payload: productTruth } = useProductTruth<ProductTruth>();
  const [open, setOpen] = useState(false);
  const topJobs = useMemo(
    () => Array.isArray(productTruth?.top_jobs) ? productTruth.top_jobs.slice(0, 5) : [],
    [productTruth?.top_jobs],
  );
  const sourceReadiness = productTruth?.application_sources_ready || {};
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [workspace, setWorkspace] = useState<ApplicationWorkspacePayload | null>(null);
  const [draft, setDraft] = useState<DraftPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (topJobs.length === 0) {
      setSelectedId(null);
      return;
    }
    if (selectedId == null || !topJobs.some((job) => job.silver_job_id === selectedId)) {
      setSelectedId(topJobs[0].silver_job_id);
    }
  }, [selectedId, topJobs]);

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
  const templateAuthority = workspace?.template_authority;
  const generationReady = workspace?.status === "ready" && workspace.workspace?.generation_ready === true && claimPlan.length > 0;
  const vacancyReady = Boolean(workspace?.live_job_evidence?.fetched_title || workspace?.live_job_evidence?.final_url);
  const candidateFactsReady = claimPlan.length > 0;
  const documentsReady = documents.length >= 2 && sourceReadiness?.base_cv === true && sourceReadiness?.base_application_letter === true;

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
      title={topJobs.length ? "Prepare an application from authoritative Top-5 truth" : "No authoritative Top-5 job available"}
    >
      <span>Prepare application</span>
      <strong>{topJobs.length ? `${topJobs.length} authoritative Top-5 job${topJobs.length === 1 ? "" : "s"}` : "No Top-5 job"}</strong>
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
          <p>One current job, verified evidence, exact F6 templates, one reviewable text draft.</p>
        </div>
        <button type="button" className="demo-close" onClick={() => setOpen(false)}>×</button>
      </header>

      <div className="demo-journey" aria-label="Demo product journey">
        <span className="done"><b>1</b>Discover</span>
        <i />
        <span className="done"><b>2</b>Verify</span>
        <i />
        <span className="done"><b>3</b>Rank</span>
        <i />
        <span className="active"><b>4</b>Prepare</span>
      </div>

      <div className="demo-safety-banner">
        <strong>REVIEW REQUIRED</strong>
        <span>Nothing is submitted or sent automatically.</span>
      </div>

      <div className="demo-application-shell">
        <aside className="demo-job-sidebar">
          <div className="demo-sidebar-heading">
            <span className="demo-eyebrow">Authoritative shortlist</span>
            <h2>Top 5</h2>
            <small>{topJobs.length}/5 current recommendations</small>
          </div>
          <nav className="demo-job-picker" aria-label="Top jobs">
            {topJobs.map((job) => <button
              type="button"
              key={job.silver_job_id}
              className={job.silver_job_id === selectedId ? "active" : ""}
              onClick={() => setSelectedId(job.silver_job_id)}
            >
              <b>#{job.product_rank || "–"}</b>
              <span>{job.title || "Untitled job"}</span>
              <small>{job.company_name || "Unknown employer"} · {job.city || "Location unconfirmed"}</small>
            </button>)}
          </nav>
        </aside>

        <main className="demo-application-main">
          {selectedJob && <section className="demo-selected-job">
            <div className="demo-selected-copy">
              <span className="demo-eyebrow">Selected authoritative job</span>
              <h2>{selectedJob.title}</h2>
              <p>{selectedJob.company_name} · {selectedJob.city || "Location unconfirmed"}</p>
            </div>
            <div className="demo-score-ring" aria-label={`${percent(selectedJob.overall_quality_score)} profile fit`}>
              <strong>{percent(selectedJob.overall_quality_score)}</strong>
              <span>profile fit</span>
            </div>
          </section>}

          {loading && <div className="demo-loading">Binding live vacancy evidence, Candidate Facts and approved source documents…</div>}
          {error && <div className="demo-error"><b>Fail closed</b><span>{error}</span></div>}

          {!loading && workspace && <div className="demo-application-grid">
            <article className="demo-workspace-card demo-context-card">
              <header>
                <span className="demo-eyebrow">Verified context</span>
                <h3>{generationReady ? "Ready for drafting" : "Context blocked"}</h3>
              </header>

              <div className="demo-readiness-list">
                <div className={readinessTone(vacancyReady)}><i /><span>Vacancy</span><b>{vacancyReady ? "Employer-origin verified" : "Evidence required"}</b></div>
                <div className={readinessTone(candidateFactsReady)}><i /><span>Candidate facts</span><b>{candidateFactsReady ? `${claimPlan.length} matched claims` : "Matches required"}</b></div>
                <div className={readinessTone(documentsReady)}><i /><span>F6 templates</span><b>{documentsReady ? "2/2 exact authority" : `${documents.length}/2 exact`}</b></div>
                <div className="ready"><i /><span>Submission boundary</span><b>Review only · no auto-submit</b></div>
              </div>

              {workspaceBlockers.length > 0 && <div className="demo-blockers"><b>What still blocks this application?</b>{workspaceBlockers.map((item) => <span key={item}>{normalized(item)}</span>)}</div>}

              <details className="demo-evidence-details">
                <summary>Evidence details</summary>
                <div className="demo-evidence-meta">
                  <span>Current vacancy</span><b>{workspace.live_job_evidence?.fetched_title || "Validated source"}</b>
                  <span>Detail fingerprint</span><code>{workspace.live_job_evidence?.detail_sha256?.slice(0, 12) || "—"}</code>
                </div>
                {claimPlan.length > 0 && <div className="demo-claim-plan">{claimPlan.slice(0, 5).map((entry) => <div key={entry.fact_key}><b>{entry.statement || entry.fact_key}</b><small>{entry.job_references?.map((reference) => reference.evidence).filter(Boolean).join(" · ") || "No exact vacancy match"}</small></div>)}</div>}
              </details>

              <button type="button" className="demo-generate-button" disabled={!generationReady || drafting} onClick={() => void generateDraft()}>
                {drafting ? "Preparing review text…" : draft?.status === "draft_for_review" ? "Regenerate review text" : "Generate review text"}
              </button>
            </article>

            <article className="demo-workspace-card demo-draft-card">
              <header>
                <span className="demo-eyebrow">Prepared application</span>
                <h3>{draft?.status === "draft_for_review" ? "Grounded text ready for review" : "Waiting for your action"}</h3>
              </header>

              {draft?.status === "draft_for_review" && draft.package ? <>
                <div className="demo-draft-badge">{draftModeLabel(draft.draft_mode)} · REVIEW REQUIRED</div>
                {draft.base_document_text_shared_with_provider && <p className="demo-provider-context-note">The extracted text of your two approved base documents was used for this explicit generation request as style and structure context. No submission or send action occurred.</p>}
                {draft.package.rationale && <p className="demo-boundary-note">{draft.package.rationale}</p>}
                {draft.draft_mode === "deterministic_evidence_first" && draft.fallback_reason && <p className="demo-boundary-note">Fallback: {normalized(draft.fallback_reason)}. Claims remain bound to approved Candidate Facts and exact vacancy evidence.</p>}

                <section className="demo-application-downloads">
                  <header><strong>F6 template authority</strong><span>{templateAuthority?.status === "ready" ? "2/2 exact private PDFs verified" : "exact templates required"}</span></header>
                  <p className="demo-boundary-note">Legacy generic DOCX/A4 export has been removed. The next F6 slice may render only into declared text zones of the two hash-bound PDFs.</p>
                </section>

                <section className="demo-document">
                  <header><span>CV adaptation</span><small>complete review copy</small></header>
                  {cvFragments.map((fragment, index) => <div className="demo-draft-fragment" key={`${fragment.kind}-${index}`}><p>{fragment.text}</p></div>)}
                </section>

                <section className="demo-document">
                  <header><span>Application letter</span><small>complete review copy</small></header>
                  {letterFragments.map((fragment, index) => <div className="demo-draft-fragment" key={`${fragment.kind}-${index}`}><p>{fragment.text}</p></div>)}
                </section>

                <details className="demo-evidence-details demo-audit-details">
                  <summary>Audit details</summary>
                  <div className="demo-claim-plan">{draftFragments.map((fragment, index) => <div key={`${fragment.kind}-${index}`}><b>{fragment.kind}</b><small>{fragment.candidate_fact_keys?.join(", ") || "no candidate claim"}{fragment.job_evidence?.length ? ` · ${fragment.job_evidence.map((item) => item.evidence).filter(Boolean).join(" · ")}` : ""}</small></div>)}</div>
                  <footer><span>Provider requests: {draft.provider_requests ?? 0}</span><span>DB writes: {draft.database_writes ?? 0}</span><span>Submission writes: {draft.submission_writes ?? 0}</span><span>Send actions: {draft.send_actions ?? 0}</span></footer>
                </details>
              </> : <div className="demo-empty-draft">
                <strong>F6 is review-first and template-authoritative.</strong>
                <p>When factual context and both exact templates are ready, the system may draft text for review. Rendering into the frozen layouts remains fail-closed until the template-bound renderer is qualified.</p>
              </div>}
            </article>
          </div>}
        </main>
      </div>
    </section>
  </div>;
}
