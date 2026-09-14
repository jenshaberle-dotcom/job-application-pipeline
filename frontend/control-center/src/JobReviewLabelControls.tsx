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

type JobRequirementTruth = {
  silver_job_id: number;
  requirement_evidence_status?: string;
  employment_type?: string;
  employment_evidence_status?: string;
  required_languages?: string[];
  language_evidence_status?: string;
  weekly_hours_min?: number | null;
  weekly_hours_max?: number | null;
  weekly_hours_evidence_status?: string;
  work_model?: string;
  work_model_resolution?: string;
  requirements_seniority?: string;
  seniority_evidence_status?: string;
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

const humanize = (value: string | undefined | null) =>
  (value || "unknown").replaceAll("_", " ");

const hoursLabel = (
  minimum: number | null | undefined,
  maximum: number | null | undefined,
) => {
  if (minimum == null && maximum == null) return "unknown";
  if (minimum != null && maximum != null && minimum === maximum) return `${minimum} h/week`;
  return `${minimum ?? "?"}–${maximum ?? "?"} h/week`;
};

const languageLabel = (values: string[] | undefined) =>
  values?.length ? values.map((value) => value.toUpperCase()).join(", ") : "unknown";

function RequirementFact({
  label,
  value,
  status,
}: {
  label: string;
  value: string;
  status?: string;
}) {
  const normalized = (status || "unknown").toLowerCase();
  const tone = normalized.includes("observed") || normalized.includes("contextual")
    ? "observed"
    : normalized.includes("conflict")
      ? "conflict"
      : "unknown";
  return (
    <div className={`review-requirement-fact ${tone}`}>
      <span>{label}</span>
      <b>{value}</b>
      <small>{humanize(status)}</small>
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
  const [requirements, setRequirements] = useState<JobRequirementTruth | null>(null);
  const [requirementsError, setRequirementsError] = useState<string | null>(null);

  useEffect(() => {
    setSubmitting(null);
    setMessage(null);
    setRequirements(null);
    setRequirementsError(null);
    let cancelled = false;
    readProductTruth<ProductRequirementPayload>()
      .then((payload) => {
        if (cancelled) return;
        const jobs = [...(payload.job_readiness || []), ...(payload.top_jobs || [])];
        const match = jobs.find((job) => job.silver_job_id === silverJobId) || null;
        setRequirements(match);
        if (!match) setRequirementsError("Requirement metadata is not present in Product truth for this job.");
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

  const conflicts = requirements?.requirement_conflicted_fields || [];
  const skills = requirements?.job_skills || [];

  return (
    <>
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
        <p>
          One click records append-only review evidence. It does not change ranking, Top 5 or application state.
        </p>
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
        {!captureAvailable && (
          <p className="review-label-message warn" role="status">
            Label capture is unavailable until the append-only DB contract is migrated locally.
          </p>
        )}
        {currentLabel && (
          <small className="review-label-meta">
            Event #{currentLabel.label_event_id} · {currentLabel.training_eligible ? "training-eligible later" : "evidence only"} · {currentLabel.selection_reason.replaceAll("_", " ")}
          </small>
        )}
        {message && <p className="review-label-message" role="status">{message}</p>}
      </section>

      <section className="review-requirement-panel" aria-label="Job requirements from employer origin">
        <header>
          <div>
            <span className="eyebrow">Job requirements · Origin truth</span>
            <h3>Vacancy metadata</h3>
          </div>
          <span className={`review-requirement-state ${requirements?.requirement_evidence_status || "not_yet_assessed"}`}>
            {humanize(requirements?.requirement_evidence_status || "not_yet_assessed")}
          </span>
        </header>
        {requirements ? (
          <>
            <div className="review-requirement-grid">
              <RequirementFact
                label="Employment type"
                value={humanize(requirements.employment_type)}
                status={requirements.employment_evidence_status}
              />
              <RequirementFact
                label="Required languages"
                value={languageLabel(requirements.required_languages)}
                status={requirements.language_evidence_status}
              />
              <RequirementFact
                label="Weekly hours"
                value={hoursLabel(requirements.weekly_hours_min, requirements.weekly_hours_max)}
                status={requirements.weekly_hours_evidence_status}
              />
              <RequirementFact
                label="Work model"
                value={humanize(requirements.work_model)}
                status={conflicts.includes("work_model") ? "conflict_unknown" : requirements.work_model_resolution}
              />
              <RequirementFact
                label="Requirement seniority"
                value={humanize(requirements.requirements_seniority)}
                status={requirements.seniority_evidence_status}
              />
              <RequirementFact
                label="Job skills"
                value={skills.length ? skills.join(", ") : "unknown"}
                status={skills.length ? "observed" : "unknown"}
              />
            </div>
            {conflicts.length > 0 && (
              <p className="review-requirement-warning">
                Conflicting Origin evidence kept unknown: {conflicts.join(", ")}.
              </p>
            )}
            <p className="review-requirement-boundary">
              Job-side evidence only. Candidate capability fit and Profile Fit remain separate authorities.
            </p>
          </>
        ) : (
          <p className="review-requirement-warning">
            {requirementsError || "Loading persisted requirement evidence…"}
          </p>
        )}
      </section>
    </>
  );
}
