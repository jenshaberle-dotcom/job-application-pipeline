import { useEffect, useState } from "react";
import { readProductTruth } from "./productPayloadRuntimeAdapter";
import "./review-labels.css";

export const JOB_REVIEW_LABEL_ACTION_PATH = "/api/v1/product-v1/job-review-label";

export type JobReviewLabelValue = "interesting" | "not_relevant" | "unsure";

export type JobReviewLabelState = {
  label_event_id: number;
  label: JobReviewLabelValue;
  reviewed_by: string;
  reviewed_at: string;
  evidence_cutoff: string;
  job_evidence_fingerprint: string;
  selection_reason: string;
  capture_surface: string;
  deterministic_signal_visible: boolean;
  ml_signal_visible: boolean;
  llm_signal_visible: boolean;
  supervised_target: number | null;
  training_eligible: boolean;
};

type ProfileFitFactor = { status?: string; reason?: string };

type JobRequirementTruth = {
  silver_job_id: number;
  title?: string | null;
  city?: string | null;
  country?: string | null;
  work_model?: string | null;
  commute_minutes?: number | null;
  product_readiness_status?: string | null;
  overall_quality_score?: number | null;
  product_overall_quality_score?: number | null;
  profile_direction_score?: number | null;
  data_focus_score?: number | null;
  reliability_focus_score?: number | null;
  evidence_quality_score?: number | null;
  profile_fit_coverage_status?: string | null;
  profile_fit_decision?: string | null;
  profile_fit_factors?: Record<string, ProfileFitFactor>;
  requirement_evidence_status?: string;
  employment_type?: string;
  employment_evidence_status?: string;
  source_employment_types?: string[];
  employment_scope?: string;
  employment_scope_status?: string;
  structured_work_hours?: string | null;
  structured_work_hours_status?: string;
  required_languages?: string[];
  language_evidence_status?: string;
  posting_language?: string;
  posting_language_basis?: string;
  weekly_hours_min?: number | null;
  weekly_hours_max?: number | null;
  weekly_hours_evidence_status?: string;
  work_model_resolution?: string;
  requirements_seniority?: string;
  seniority_evidence_status?: string;
  experience_requirement?: string | null;
  experience_months?: number | null;
  experience_requirement_status?: string;
  title_seniority_signal?: string;
  title_seniority_basis?: string;
  job_skills?: string[];
  requirement_conflicted_fields?: string[];
  requirement_unresolved_fields?: string[];
};

type ProductRequirementPayload = {
  job_readiness?: JobRequirementTruth[];
  top_jobs?: JobRequirementTruth[];
};

type Props = {
  silverJobId: number;
  currentLabel?: JobReviewLabelState | null;
  captureAvailable: boolean;
  refreshProductTruth: () => Promise<void>;
};

const choices: Array<{ value: JobReviewLabelValue; label: string; icon: string }> = [
  { value: "interesting", label: "Interesting", icon: "↑" },
  { value: "not_relevant", label: "Not relevant", icon: "↓" },
  { value: "unsure", label: "Unsure", icon: "?" },
];

const friendly = (value: JobReviewLabelValue | undefined) =>
  choices.find((choice) => choice.value === value)?.label || "Not reviewed";

const normalized = (value: string | undefined | null) => (value || "").trim().toLowerCase();
const humanize = (value: string | undefined | null) =>
  (value || "not available").replaceAll("_", " ");
const known = (value: string | undefined | null) => {
  const text = normalized(value);
  return Boolean(text && text !== "unknown" && text !== "source_absent");
};

const scopeLabel = (value: string | undefined) => {
  if (value === "full_time") return "Full-time";
  if (value === "part_time") return "Part-time";
  if (value === "full_or_part_time") return "Full-time or part-time";
  return null;
};

const hoursLabel = (
  minimum: number | null | undefined,
  maximum: number | null | undefined,
) => {
  if (minimum == null && maximum == null) return null;
  if (minimum != null && maximum != null && minimum === maximum) return `${minimum} h/week`;
  return `${minimum ?? "?"}–${maximum ?? "?"} h/week`;
};

const languageName = (value: string | undefined) => {
  if (value === "de") return "German";
  if (value === "en") return "English";
  if (value === "mixed") return "German / English";
  return null;
};

const explicitLanguages = (values: string[] | undefined) =>
  values?.length ? values.map((value) => value.toUpperCase()).join(", ") : null;

const fitLabel = (value: string | undefined) => {
  const status = normalized(value);
  if (status === "passed") return "match";
  if (status === "failed") return "conflict";
  return "fit evidence missing";
};

const fitDecisionLabel = (value: string | undefined | null) => {
  const status = normalized(value);
  if (status === "passed") return "fit confirmed";
  if (status === "failed") return "fit conflict";
  return "fit evidence missing";
};

const fitTone = (value: string | undefined) => {
  const status = normalized(value);
  if (status === "passed") return "good";
  if (status === "failed") return "bad";
  return "warn";
};

function EvidenceRow({
  label,
  primary,
  secondary,
  fit,
}: {
  label: string;
  primary: string;
  secondary?: string | null;
  fit?: string;
}) {
  return (
    <div className="r4-evidence-row">
      <span>{label}</span>
      <div><b>{primary}</b>{secondary && <small>{secondary}</small>}</div>
      <em className={`r4-fit-state ${fitTone(fit)}`}>{fitLabel(fit)}</em>
    </div>
  );
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  const bounded = Math.max(0, Math.min(100, value));
  return (
    <div>
      <span>{label}</span>
      <i><b style={{ width: `${bounded}%` }} /></i>
      <strong>{Math.round(value)}%</strong>
    </div>
  );
}

export default function JobReviewLabelControls({
  silverJobId,
  currentLabel,
  captureAvailable,
  refreshProductTruth,
}: Props) {
  const [submitting, setSubmitting] = useState<JobReviewLabelValue | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [job, setJob] = useState<JobRequirementTruth | null>(null);
  const [requirementsError, setRequirementsError] = useState<string | null>(null);

  useEffect(() => {
    setSubmitting(null);
    setMessage(null);
    setJob(null);
    setRequirementsError(null);
    let cancelled = false;
    readProductTruth<ProductRequirementPayload>()
      .then((payload) => {
        if (cancelled) return;
        const jobs = [...(payload.job_readiness || []), ...(payload.top_jobs || [])];
        const match = jobs.find((item) => item.silver_job_id === silverJobId) || null;
        setJob(match);
        if (!match) setRequirementsError("Job evidence is not present in Product truth.");
      })
      .catch((reason: unknown) => {
        if (!cancelled) setRequirementsError(String(reason));
      });
    return () => {
      cancelled = true;
    };
  }, [silverJobId]);

  const submit = async (label: JobReviewLabelValue) => {
    if (!captureAvailable || submitting !== null) return;
    setSubmitting(label);
    setMessage(null);

    try {
      const response = await fetch(JOB_REVIEW_LABEL_ACTION_PATH, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ silver_job_id: silverJobId, label }),
      });
      const result = (await response.json().catch(() => null)) as
        | { status?: string; reason?: string }
        | null;
      if (!response.ok) {
        throw new Error(result?.reason || `Review-label API returned ${response.status}`);
      }
      await refreshProductTruth();
      setMessage(result?.status === "unchanged" ? "Already recorded for this evidence." : "Review feedback recorded.");
    } catch (reason: unknown) {
      setMessage(`Feedback was not recorded: ${String(reason)}`);
    } finally {
      setSubmitting(null);
    }
  };

  const factors = job?.profile_fit_factors || {};
  const location = [job?.city, job?.country].filter(Boolean).join(" · ") || "Location not stated";
  const workModel = known(job?.work_model) ? humanize(job?.work_model) : null;
  const commute = job?.commute_minutes == null ? null : `${job.commute_minutes} min commute`;
  const locationDetail = [workModel, commute].filter(Boolean).join(" · ") || "Work model not stated";

  const scope = scopeLabel(job?.employment_scope);
  const contract = known(job?.employment_type) ? humanize(job?.employment_type) : null;
  const numericHours = hoursLabel(job?.weekly_hours_min, job?.weekly_hours_max);
  const structuredHours = job?.structured_work_hours || null;
  const hours = numericHours || structuredHours;
  const employmentParts = [scope, contract, hours].filter(Boolean);
  const employmentPrimary = employmentParts.join(" · ") || "Not stated by employer";
  const employmentSecondary = !contract && scope
    ? "Contract duration not stated"
    : !hours && scope
      ? "Weekly hours not stated"
      : null;

  const explicit = explicitLanguages(job?.required_languages);
  const posting = languageName(job?.posting_language);
  const languagePrimary = explicit
    ? `${explicit} explicitly required`
    : posting
      ? `${posting} posting`
      : "No explicit language requirement detected";
  const languageSecondary = !explicit && posting
    ? "Posting language is context, not an explicit employer requirement"
    : null;

  const requirementLevel = known(job?.requirements_seniority)
    ? humanize(job?.requirements_seniority)
    : null;
  const titleLevel = known(job?.title_seniority_signal)
    ? humanize(job?.title_seniority_signal)
    : null;
  const experienceMonths = typeof job?.experience_months === "number" ? job.experience_months : null;
  const experienceText = job?.experience_requirement || null;
  const experienceLabel = experienceMonths != null
    ? `${experienceMonths / 12 === Math.floor(experienceMonths / 12) ? `${experienceMonths / 12} years` : `${experienceMonths} months`} experience`
    : experienceText;
  const levelPrimary = requirementLevel
    ? `${requirementLevel} requirement`
    : experienceLabel
      ? experienceLabel
      : titleLevel
        ? `${titleLevel} title signal`
        : "No explicit level or experience requirement detected";
  const levelSecondary = !requirementLevel && !experienceLabel && titleLevel
    ? "Title signal only; not promoted to a hard requirement"
    : null;

  const skills = job?.job_skills || [];
  const skillsPrimary = skills.length ? skills.join(", ") : "No explicit skills list detected";

  const scoreCandidates: Array<[string, number | null | undefined]> = [
    [job?.product_readiness_status === "rankable" ? "Overall" : "Role affinity", job?.overall_quality_score],
    ["Profile direction", job?.profile_direction_score],
    ["Data focus", job?.data_focus_score],
    ["Reliability", job?.reliability_focus_score],
    ["Evidence quality", job?.evidence_quality_score],
  ];
  const scores = scoreCandidates.filter((item): item is [string, number] => typeof item[1] === "number");

  return (
    <div className="r4-review-stack">
      <section className="review-label-panel" aria-labelledby={`review-label-title-${silverJobId}`}>
        <header>
          <div>
            <span className="eyebrow">Operator feedback · ML ground truth</span>
            <h3 id={`review-label-title-${silverJobId}`}>Worth reviewing?</h3>
          </div>
          <span className={`review-label-current ${currentLabel?.label || "unreviewed"}`}>
            {friendly(currentLabel?.label)}
          </span>
        </header>
        <p>One click records append-only review evidence. It does not change ranking, Top 5 or application state.</p>
        <div className="review-label-actions" role="group" aria-label="Job review relevance">
          {choices.map((choice) => (
            <button
              key={choice.value}
              type="button"
              className={currentLabel?.label === choice.value ? `active ${choice.value}` : choice.value}
              aria-pressed={currentLabel?.label === choice.value}
              disabled={!captureAvailable || submitting !== null}
              onClick={() => void submit(choice.value)}
            >
              <span>{choice.icon}</span>
              {submitting === choice.value ? "Recording…" : choice.label}
            </button>
          ))}
        </div>
        {!captureAvailable && <p className="review-label-message warn" role="status">Label capture is unavailable until the append-only DB contract is migrated locally.</p>}
        {currentLabel && <small className="review-label-meta">Event #{currentLabel.label_event_id} · {currentLabel.training_eligible ? "training-eligible later" : "evidence only"} · {currentLabel.selection_reason.replaceAll("_", " ")}</small>}
        {message && <p className="review-label-message" role="status">{message}</p>}
      </section>

      <section className="r4-requirement-fit" aria-label="Consolidated job requirements and fit">
        <header>
          <div><span className="eyebrow">Origin truth + Candidate fit</span><h3>Job requirements & fit</h3></div>
          <div className="r4-fit-summary">
            <em className={`r4-fit-state ${fitTone(job?.profile_fit_decision || undefined)}`}>{fitDecisionLabel(job?.profile_fit_decision)}</em>
          </div>
        </header>
        {job ? <>
          <EvidenceRow
            label="Location & work model"
            primary={location}
            secondary={locationDetail}
            fit={factors.geography_work_model_commute?.status}
          />
          <EvidenceRow
            label="Skills & capabilities"
            primary={skillsPrimary}
            secondary={skills.length ? "Employer-origin job skills" : "No skill value invented"}
            fit={factors.skills_capabilities?.status}
          />
          <EvidenceRow
            label="Level & experience"
            primary={levelPrimary}
            secondary={levelSecondary}
            fit={factors.seniority?.status}
          />
          <EvidenceRow
            label="Employment & language"
            primary={employmentPrimary}
            secondary={[employmentSecondary, languagePrimary, languageSecondary].filter(Boolean).join(" · ")}
            fit={factors.hard_requirements?.status}
          />
          <p className="r4-authority-note">Posting language, workload, structured experience and title-level signals are operator context only unless the employer explicitly states a requirement. Candidate Fit remains a separate authority.</p>
        </> : <p className="review-requirement-warning">{requirementsError || "Loading persisted job evidence…"}</p>}
      </section>

      {scores.length > 0 && <section className="ow-score-card r4-score-card">
        <h3>{job?.product_readiness_status === "rankable" ? "Product score" : "Review signals"}</h3>
        {scores.map(([name, value]) => <ScoreBar key={name} label={name} value={value} />)}
        {job?.product_readiness_status !== "rankable" && <p className="ow-score-note">Review signals are orientation only until Profile Fit and hard requirements are evidence-backed.</p>}
      </section>}
    </div>
  );
}
