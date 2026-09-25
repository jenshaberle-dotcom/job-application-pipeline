import { useEffect, useMemo, useState } from "react";
import { useProductTruth } from "./ProductTruthContext";
import F6TemplateReviewEditor from "./F6TemplateReviewEditor";
import "./demo-application-workspace.css";

type TopJob = {
  silver_job_id: number;
  product_rank?: number;
  title?: string | null;
  company_name?: string | null;
  city?: string | null;
  overall_quality_score?: number | null;
  product_readiness_status?: string | null;
  lifecycle_status?: string | null;
  origin_validation_status?: string | null;
  hard_filter_status?: string | null;
  demo_live_verified?: boolean;
  demo_live_reason?: string | null;
};

type ApplicationStage = "prepared" | "applied" | "reply" | "interview" | "offer" | "closed";

type ProductTruth = {
  top_jobs?: TopJob[];
  job_readiness?: TopJob[];
  application_sources_ready?: {
    base_cv?: boolean;
    base_application_letter?: boolean;
  };
  application_tracking?: {
    applications?: Array<{
      silver_job_id?: number | null;
      effective_stage?: ApplicationStage;
    }>;
    job_linkage?: {
      exact_matches?: Array<{
        silver_job_id?: number | null;
        effective_stage?: ApplicationStage;
      }>;
    };
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

type VacancyRevalidationPayload = {
  status?: "active" | "closed" | "unverifiable" | "blocked";
  outcome?: string;
  reason?: string;
  silver_job_id?: number;
  vacancy_revalidation_http_gets?: number;
  database_writes?: number;
  lifecycle_health_observation_writes?: number;
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
      employer_origin_authorized?: boolean;
      origin_validation_status?: string;
      canonical_source_type?: string;
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
  | "deterministic_evidence_first"
  | "codex_embedded_v1";

type CodexStatusPayload = {
  status?: "ready" | "auth_required" | "not_installed";
  installed?: boolean;
  chatgpt_authenticated?: boolean;
  auth_mode?: string;
  executable?: string | null;
  version?: string | null;
  model?: string;
  billing_authority?: string;
  api_key_fallback?: boolean;
  automatic_credit_purchase?: boolean;
};

type CodexLoginPayload = {
  status?: "idle" | "starting" | "awaiting_user" | "completed" | "failed" | "blocked";
  verification_url?: string | null;
  user_code?: string | null;
  started_at?: string;
  expires_at?: string;
  detail?: string | null;
  reason?: string;
};

type DraftPayload = {
  status?: string;
  reason?: string;
  reason_code?: string;
  retryable?: boolean;
  blocked_reasons?: string[];
  draft_mode?: DraftMode;
  fallback_reason?: string | null;
  base_document_text_shared_with_provider?: boolean;
  base_cv_text_shared_with_codex?: boolean;
  codex_model?: string;
  codex_version?: string | null;
  codex_requests?: number;
  package?: {
    status?: string;
    fragments?: DraftFragment[];
    rationale?: string;
    candidate_fact_keys_used?: string[];
    source_manifest_sha256?: string;
    preview?: {
      cv_short_profile?: string;
      cv_competency_profile?: string;
      application_letter?: string;
    };
    zone_replacements?: Record<string, Record<string, string>>;
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
    const detail = payload as {
      reason?: string;
      blocked_reasons?: string[];
      message?: string;
      error_type?: string;
    };
    const reason = detail.reason
      || detail.blocked_reasons?.join(", ")
      || (detail.message
        ? `${detail.error_type ? `${detail.error_type}: ` : ""}${detail.message}`
        : null)
      || `API returned ${response.status}`;
    throw new Error(reason);
  }
  return payload;
}

function fragmentGroup(kind: string | undefined) {
  return kind?.startsWith("cv_") ? "CV" : "Application letter";
}

function draftModeLabel(mode: DraftMode | undefined) {
  if (mode === "codex_embedded_v1") return "CODEX-ADAPTED";
  if (mode === "provider_validated_quality_v3") return "BASE-DOCUMENT ADAPTED";
  if (mode === "provider_validated_quality_v2" || mode === "provider_validated") return "PROVIDER-VALIDATED";
  if (mode === "deterministic_evidence_first") return "EVIDENCE-FIRST · PROVIDER-FREE";
  return "SOURCE-GROUNDED";
}

function readinessTone(ready: boolean) {
  return ready ? "ready" : "blocked";
}

function applicationStageByJobId(productTruth: ProductTruth | null | undefined) {
  const stages = new Map<number, ApplicationStage>();
  for (const application of productTruth?.application_tracking?.applications || []) {
    if (
      typeof application.silver_job_id === "number" &&
      application.effective_stage
    ) {
      stages.set(application.silver_job_id, application.effective_stage);
    }
  }
  for (const application of productTruth?.application_tracking?.job_linkage?.exact_matches || []) {
    if (
      typeof application.silver_job_id === "number" &&
      application.effective_stage &&
      !stages.has(application.silver_job_id)
    ) {
      stages.set(application.silver_job_id, application.effective_stage);
    }
  }
  return stages;
}

function canPrepareApplication(stage: ApplicationStage | undefined) {
  return stage == null || stage === "prepared";
}

export default function ApplicationWorkspace() {
  const { payload: productTruth, refreshProductTruth } = useProductTruth<ProductTruth>();
  const [open, setOpen] = useState(false);
  const topJobs = useMemo(
    () => Array.isArray(productTruth?.top_jobs) ? productTruth.top_jobs.slice(0, 5) : [],
    [productTruth?.top_jobs],
  );
  const applicationStages = useMemo(
    () => applicationStageByJobId(productTruth),
    [
      productTruth?.application_tracking?.applications,
      productTruth?.application_tracking?.job_linkage?.exact_matches,
    ],
  );
  const applicationJobs = useMemo(() => {
    const allCurrent = Array.isArray(productTruth?.job_readiness)
      ? productTruth.job_readiness.filter((job) =>
          job.lifecycle_status === "active_confirmed" &&
          job.hard_filter_status !== "failed"
        )
      : [];
    const byId = new Map<number, TopJob>();
    [...topJobs, ...allCurrent].forEach((job) => byId.set(job.silver_job_id, job));
    return [...byId.values()]
      .filter((job) =>
        canPrepareApplication(applicationStages.get(job.silver_job_id))
      )
      .sort((left, right) => (
        Number(right.overall_quality_score ?? -1) - Number(left.overall_quality_score ?? -1)
      ));
  }, [applicationStages, productTruth?.job_readiness, topJobs]);
  const sourceReadiness = productTruth?.application_sources_ready || {};
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [workspace, setWorkspace] = useState<ApplicationWorkspacePayload | null>(null);
  const [draft, setDraft] = useState<DraftPayload | null>(null);
  const [codexStatus, setCodexStatus] = useState<CodexStatusPayload | null>(null);
  const [codexLogin, setCodexLogin] = useState<CodexLoginPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chooserOpen, setChooserOpen] = useState(false);
  const [jobQuery, setJobQuery] = useState("");

  useEffect(() => {
    const openRequestedTarget = (event: Event) => {
      const detail = (event as CustomEvent<{ silverJobId?: number }>).detail;
      const requestedId = Number(detail?.silverJobId || 0);
      const requestedJob = requestedId > 0
        ? applicationJobs.find((job) => job.silver_job_id === requestedId)
        : applicationJobs[0];

      if (!requestedJob) {
        setError(
          requestedId > 0
            ? `Selected job #${requestedId} is not currently eligible for application preparation.`
            : "No current job is eligible for application preparation.",
        );
        return;
      }

      setSelectedId(requestedJob.silver_job_id);
      setChooserOpen(false);
      setJobQuery("");
      setOpen(true);
    };
    window.addEventListener("product-v1:open-application-workspace", openRequestedTarget);
    return () => window.removeEventListener(
      "product-v1:open-application-workspace",
      openRequestedTarget,
    );
  }, [applicationJobs]);

  useEffect(() => {
    if (!open) return;
    let active = true;
    void readJson<CodexStatusPayload>("/api/v1/product-v1/codex-status")
      .then((payload) => {
        if (active) setCodexStatus(payload);
      })
      .catch(() => {
        if (active) {
          setCodexStatus({
            status: "not_installed",
            installed: false,
            chatgpt_authenticated: false,
          });
        }
      });
    return () => { active = false; };
  }, [open]);

  useEffect(() => {
    if (!open || codexStatus?.chatgpt_authenticated) return;
    if (!codexLogin || !["starting", "awaiting_user"].includes(codexLogin.status || "")) return;
    let active = true;
    const timer = window.setInterval(() => {
      void readJson<CodexLoginPayload>("/api/v1/product-v1/codex-login")
        .then((payload) => {
          if (!active) return;
          setCodexLogin(payload);
          return undefined;
        })
        .catch(() => undefined);
    }, 1500);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [open, codexLogin?.status, codexStatus?.chatgpt_authenticated]);

  useEffect(() => {
    if (!open || codexStatus?.chatgpt_authenticated) return;
    if (codexLogin?.status !== "completed") return;
    let active = true;
    void readJson<CodexStatusPayload>("/api/v1/product-v1/codex-status")
      .then((status) => {
        if (active) setCodexStatus(status);
      })
      .catch(() => undefined);
    return () => { active = false; };
  }, [open, codexLogin?.status, codexStatus?.chatgpt_authenticated]);

  useEffect(() => {
    if (!open || selectedId == null) return;
    let active = true;
    setLoading(true);
    setDraft(null);
    setWorkspace(null);
    setError(null);

    const loadVerifiedWorkspace = async () => {
      const revalidation = await readJson<VacancyRevalidationPayload>(
        "/api/v1/product-v1/application-workspace/revalidate",
        {
          method: "POST",
          body: JSON.stringify({
            action: "revalidate_selected_vacancy",
            silver_job_id: selectedId,
          }),
        },
      );
      if (!active) return;

      if (revalidation.status === "closed") {
        setError(
          `Current vacancy is no longer available: ${revalidation.reason || "explicit closure evidence"}`,
        );
        await refreshProductTruth().catch(() => undefined);
        return;
      }
      if (revalidation.status !== "active") {
        setError(
          `Current vacancy could not be verified: ${revalidation.reason || revalidation.status || "unknown reason"}`,
        );
        return;
      }

      const payload = await readJson<ApplicationWorkspacePayload>(
        `/api/v1/product-v1/application-workspace?silver_job_id=${selectedId}`,
      );
      if (active) setWorkspace(payload);
    };

    void loadVerifiedWorkspace()
      .catch((reason: unknown) => {
        if (!active) return;
        setWorkspace(null);
        setError(String(reason));
      })
      .finally(() => { if (active) setLoading(false); });

    return () => { active = false; };
  }, [open, selectedId, refreshProductTruth]);

  const selectedJob = useMemo(
    () => applicationJobs.find((job) => job.silver_job_id === selectedId) || null,
    [applicationJobs, selectedId],
  );

  const chooserJobs = useMemo(() => {
    const query = jobQuery.trim().toLocaleLowerCase();
    const filtered = query
      ? applicationJobs.filter((job) =>
          [job.title, job.company_name, job.city]
            .filter(Boolean)
            .some((value) => String(value).toLocaleLowerCase().includes(query))
        )
      : applicationJobs;
    return filtered.slice(0, 10);
  }, [applicationJobs, jobQuery]);

  const chooseJob = (job: TopJob) => {
    setSelectedId(job.silver_job_id);
    setChooserOpen(false);
    setJobQuery("");
  };

  const claimPlan = workspace?.workspace?.claim_plan || [];
  const documents = workspace?.workspace?.source_manifest?.documents || [];
  const workspaceBlockers = workspace?.workspace?.blocked_reasons || workspace?.blocked_reasons || [];
  const draftFragments = draft?.package?.fragments || [];
  const cvFragments = draftFragments.filter((item) => fragmentGroup(item.kind) === "CV");
  const letterFragments = draftFragments.filter((item) => fragmentGroup(item.kind) === "Application letter");
  const draftPreview = draft?.package?.preview;
  const zoneReplacements = draft?.package?.zone_replacements || {};
  const templateAuthority = workspace?.template_authority;
  const generationReady = workspace?.status === "ready" && workspace.workspace?.generation_ready === true && claimPlan.length > 0;
  const codexReady = codexStatus?.status === "ready" && codexStatus.chatgpt_authenticated === true;
  const vacancyReady = Boolean(workspace?.live_job_evidence?.fetched_title || workspace?.live_job_evidence?.final_url);
  const originAuthorized = workspace?.workspace?.target?.employer_origin_authorized === true;
  const candidateFactsReady = claimPlan.length > 0;
  const documentsReady = documents.length >= 2 && sourceReadiness?.base_cv === true && sourceReadiness?.base_application_letter === true;

  const startCodexLogin = async () => {
    setError(null);
    try {
      const payload = await readJson<CodexLoginPayload>("/api/v1/product-v1/codex-login", {
        method: "POST",
        body: JSON.stringify({ action: "start_chatgpt_device_login" }),
      });
      setCodexLogin(payload);
      if (payload.verification_url) {
        window.open(payload.verification_url, "_blank", "noopener,noreferrer");
      }
    } catch (reason) {
      setError(String(reason));
    }
  };

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

  if (!open) return null;

  return <div className="demo-application-backdrop" role="presentation" onMouseDown={(event) => {
    if (event.currentTarget === event.target) setOpen(false);
  }}>
    <section className="demo-application-workspace" role="dialog" aria-modal="true" aria-label="Application Workspace">
      <header className="demo-application-header">
        <div>
          <span className="demo-eyebrow">PRODUCT V1 · APPLICATION</span>
          <h1>Application Workspace</h1>
          <p>The job you selected stays the application target. Change it only explicitly.</p>
        </div>
        <button type="button" className="demo-close" onClick={() => { setChooserOpen(false); setOpen(false); }}>×</button>
      </header>

      <div className="demo-journey" aria-label="Application preparation journey">
        <span className="done"><b>1</b>Discover</span>
        <i />
        <span className="done"><b>2</b>Verify</span>
        <i />
        <span className={selectedJob?.product_rank ? "done" : "active"}><b>3</b>{selectedJob?.product_rank ? "Rank" : "Select"}</span>
        <i />
        <span className="active"><b>4</b>Prepare</span>
      </div>

      <div className="demo-safety-banner">
        <strong>REVIEW REQUIRED</strong>
        <span>Nothing is submitted or sent automatically.</span>
      </div>

      <div className="demo-application-shell demo-application-shell-direct">
        <main className="demo-application-main">
          {selectedJob && <section className="demo-selected-job">
            <div className="demo-selected-copy">
              <span className="demo-eyebrow">{selectedJob.product_rank ? "Selected Top-5 recommendation" : "Operator-selected current job"}</span>
              <h2>{selectedJob.title}</h2>
              <p>{selectedJob.company_name} · {selectedJob.city || "Location unconfirmed"}</p>
            </div>
            <div className="demo-selected-actions">
              <button
                type="button"
                className="demo-change-job"
                onClick={() => setChooserOpen((value) => !value)}
              >
                Change job
              </button>
              <div className="demo-score-ring" aria-label={`${percent(selectedJob.overall_quality_score)} ${selectedJob.product_rank ? "Product score" : "Affinity"}`}>
                <strong>{percent(selectedJob.overall_quality_score)}</strong>
                <span>{selectedJob.product_rank ? "Product score" : "Affinity"}</span>
              </div>
            </div>
          </section>}

          {chooserOpen && <section className="demo-job-chooser" aria-label="Change application target">
            <header>
              <div>
                <span className="demo-eyebrow">Change application target</span>
                <h3>Find another current job</h3>
                <small>{applicationJobs.length} jobs can still enter the review-only preparation flow.</small>
              </div>
              <button type="button" onClick={() => setChooserOpen(false)}>×</button>
            </header>
            <input
              autoFocus
              type="search"
              value={jobQuery}
              onChange={(event) => setJobQuery(event.target.value)}
              placeholder="Search title, employer or location…"
              aria-label="Search application target jobs"
            />
            <div className="demo-job-chooser-results">
              {chooserJobs.map((job) => <button
                type="button"
                key={job.silver_job_id}
                className={job.silver_job_id === selectedId ? "active" : ""}
                onClick={() => chooseJob(job)}
              >
                <span>
                  <b>{job.title || "Untitled job"}</b>
                  <small>{job.company_name || "Unknown employer"} · {job.city || "Location unconfirmed"}</small>
                </span>
                <strong>{percent(job.overall_quality_score)}<small>{job.product_rank ? "Product" : "Affinity"}</small></strong>
              </button>)}
              {chooserJobs.length === 0 && <p>No matching current job.</p>}
            </div>
            {applicationJobs.length > chooserJobs.length && !jobQuery.trim() && <footer>Showing the 10 highest-Affinity selectable jobs. Search to reach the rest.</footer>}
          </section>}

          {!selectedJob && <div className="demo-error"><b>Exact target unavailable</b><span>The requested job is no longer selectable. Close this workspace and choose another job from All jobs.</span></div>}

          {loading && <div className="demo-loading">Binding live vacancy evidence, Candidate Facts and approved source documents…</div>}
          {error && <div className="demo-error"><b>Fail closed</b><span>{error}</span></div>}

          {!loading && workspace && <div className="demo-application-grid">
            <article className="demo-workspace-card demo-context-card">
              <header>
                <span className="demo-eyebrow">Verified context</span>
                <h3>{generationReady ? "Ready for drafting" : "Context blocked"}</h3>
              </header>

              <div className="demo-readiness-list">
                <div className={readinessTone(vacancyReady)}><i /><span>Vacancy</span><b>{vacancyReady ? "Live vacancy verified" : "Evidence required"}</b></div>
                <div className={readinessTone(originAuthorized)}><i /><span>Employer-Origin authority</span><b>{originAuthorized ? "Verified" : "Authority required"}</b></div>
                <div className={readinessTone(candidateFactsReady)}><i /><span>Candidate facts</span><b>{candidateFactsReady ? `${claimPlan.length} matched claims` : "Matches required"}</b></div>
                <div className={readinessTone(documentsReady)}><i /><span>F6 templates</span><b>{documentsReady ? "2/2 exact authority" : `${documents.length}/2 exact`}</b></div>
                <div className={readinessTone(codexReady)}><i /><span>Embedded Codex</span><b>{codexReady
                  ? `ChatGPT connected · ${codexStatus?.version || "version verified"}`
                  : codexStatus?.installed
                    ? "ChatGPT sign-in required"
                    : "Bundled runtime unavailable"}</b></div>
                <div className="ready"><i /><span>Submission boundary</span><b>Review only · no auto-submit</b></div>
              </div>

              {workspaceBlockers.length > 0 && <div className="demo-blockers"><b>What still blocks this application?</b>{workspaceBlockers.map((item) => <span key={item}>{normalized(item)}</span>)}</div>}
              {!codexReady && <div className="demo-blockers">
                <b>What still blocks automatic CV + letter adaptation?</b>
                <span>{codexStatus?.installed
                  ? `Bundled Codex ${codexStatus.version || ""} is present, but this WSL runtime is not signed in with ChatGPT.`
                  : "The bundled Codex runtime could not be verified."}</span>
                <span>JAP will not switch to API-key billing and will not generate deterministic filler text.</span>
                {codexStatus?.installed && <button type="button" onClick={() => void startCodexLogin()}>
                  {codexLogin?.status === "starting" || codexLogin?.status === "awaiting_user"
                    ? "ChatGPT sign-in in progress"
                    : "Connect ChatGPT"}
                </button>}
                {codexLogin?.verification_url && <span>
                  Open <a href={codexLogin.verification_url} target="_blank" rel="noreferrer">ChatGPT device sign-in</a>
                  {codexLogin.user_code ? <> and enter code <strong>{codexLogin.user_code}</strong></> : null}.
                </span>}
                {codexLogin?.status === "failed" && <span>{codexLogin.detail || "ChatGPT sign-in did not complete."}</span>}
              </div>}

              <details className="demo-evidence-details">
                <summary>Evidence details</summary>
                <div className="demo-evidence-meta">
                  <span>Current vacancy</span><b>{workspace.live_job_evidence?.fetched_title || "Validated source"}</b>
                  <span>Detail fingerprint</span><code>{workspace.live_job_evidence?.detail_sha256?.slice(0, 12) || "—"}</code>
                </div>
                {claimPlan.length > 0 && <div className="demo-claim-plan">{claimPlan.slice(0, 5).map((entry) => <div key={entry.fact_key}><b>{entry.statement || entry.fact_key}</b><small>{entry.job_references?.map((reference) => reference.evidence).filter(Boolean).join(" · ") || "No exact vacancy match"}</small></div>)}</div>}
              </details>

              <button type="button" className="demo-generate-button" disabled={!generationReady || !codexReady || drafting} onClick={() => void generateDraft()}>
                {drafting
                  ? "Preparing review text…"
                  : !codexReady
                    ? "ChatGPT Codex connection required"
                    : draft?.status === "draft_for_review"
                      ? "Regenerate review text"
                      : "Generate review text"}
              </button>
            </article>

            <article className="demo-workspace-card demo-draft-card">
              <header>
                <span className="demo-eyebrow">Prepared application</span>
                <h3>{draft?.status === "draft_for_review"
                  ? "Grounded text ready for review"
                  : draft?.status === "draft_unavailable"
                    ? "Codex drafting unavailable"
                    : "Waiting for your action"}</h3>
              </header>

              {draft?.status === "draft_unavailable" && <div className="demo-error">
                <b>{["codex_auth_required", "codex_chatgpt_auth_required"].includes(draft.reason_code || "")
                  ? "One-time ChatGPT sign-in required"
                  : draft.reason_code === "codex_capacity_unavailable"
                    ? "Codex allowance / credits unavailable"
                    : "Codex could not create the draft"}</b>
                <span>{draft.reason || "No application text was generated."}</span>
                <small>No deterministic filler is substituted. The selected job, template authority and review-only boundary remain unchanged.</small>
              </div>}

              {draft?.status === "draft_for_review" && draft.package ? <>
                <div className="demo-draft-badge">{draftModeLabel(draft.draft_mode)} · REVIEW REQUIRED</div>
                {draft.base_cv_text_shared_with_codex && <p className="demo-provider-context-note">Embedded Codex used the approved CV plus the exact vacancy for this adaptation. The previous application-letter text was deliberately not supplied, so stale employer/contact text cannot become drafting context. No submission or send action occurred.</p>}
                {draft.base_document_text_shared_with_provider && <p className="demo-provider-context-note">The extracted text of your two approved base documents was used for this explicit generation request as style and structure context. No submission or send action occurred.</p>}
                {draft.package.rationale && <p className="demo-boundary-note">{draft.package.rationale}</p>}
                {draft.draft_mode === "deterministic_evidence_first" && draft.fallback_reason && <p className="demo-boundary-note">Fallback: {normalized(draft.fallback_reason)}. Claims remain bound to approved Candidate Facts and exact vacancy evidence.</p>}

                <section className="demo-application-downloads">
                  <header><strong>F6 template authority</strong><span>{templateAuthority?.status === "ready" ? "2/2 exact private PDFs verified" : "exact templates required"}</span></header>
                  <p className="demo-boundary-note">Legacy generic DOCX/A4 export has been removed. F6-C renders only into declared text zones of the two hash-bound PDFs and verifies every pixel outside those zones.</p>
                </section>

                <section className="demo-document">
                  <header><span>CV adaptation</span><small>complete review copy</small></header>
                  {draftPreview?.cv_short_profile && <div className="demo-draft-fragment"><p>{draftPreview.cv_short_profile}</p></div>}
                  {draftPreview?.cv_competency_profile && <div className="demo-draft-fragment"><p>{draftPreview.cv_competency_profile}</p></div>}
                  {!draftPreview && cvFragments.map((fragment, index) => <div className="demo-draft-fragment" key={`${fragment.kind}-${index}`}><p>{fragment.text}</p></div>)}
                </section>

                <section className="demo-document">
                  <header><span>Application letter</span><small>complete review copy</small></header>
                  {draftPreview?.application_letter
                    ? draftPreview.application_letter.split("\n\n").filter(Boolean).map((paragraph, index) => <div className="demo-draft-fragment" key={`codex-letter-${index}`}><p>{paragraph}</p></div>)
                    : letterFragments.map((fragment, index) => <div className="demo-draft-fragment" key={`${fragment.kind}-${index}`}><p>{fragment.text}</p></div>)}
                </section>

                {selectedId != null && draft.package.source_manifest_sha256 && <F6TemplateReviewEditor
                  silverJobId={selectedId}
                  sourceManifestSha256={draft.package.source_manifest_sha256}
                  zoneReplacements={zoneReplacements}
                />}

                <details className="demo-evidence-details demo-audit-details">
                  <summary>Audit details</summary>
                  {draft.draft_mode === "codex_embedded_v1"
                    ? <div className="demo-claim-plan"><div><b>Embedded Codex</b><small>{draft.codex_model || "configured model"} · {draft.codex_version || "version unavailable"} · CV + letter adaptation only</small></div></div>
                    : <div className="demo-claim-plan">{draftFragments.map((fragment, index) => <div key={`${fragment.kind}-${index}`}><b>{fragment.kind}</b><small>{fragment.candidate_fact_keys?.join(", ") || "no candidate claim"}{fragment.job_evidence?.length ? ` · ${fragment.job_evidence.map((item) => item.evidence).filter(Boolean).join(" · ")}` : ""}</small></div>)}</div>}
                  <footer><span>Codex/provider requests: {draft.codex_requests ?? draft.provider_requests ?? 0}</span><span>DB writes: {draft.database_writes ?? 0}</span><span>Submission writes: {draft.submission_writes ?? 0}</span><span>Send actions: {draft.send_actions ?? 0}</span></footer>
                </details>
              </> : <div className="demo-empty-draft">
                <strong>F6 is review-first and template-authoritative.</strong>
                <p>When factual context and both exact templates are ready, the system may draft text for review. The qualified template-bound renderer then enables explicit local PDF review/export without changing submission authority.</p>
              </div>}
            </article>
          </div>}
        </main>
      </div>
    </section>
  </div>;
}
