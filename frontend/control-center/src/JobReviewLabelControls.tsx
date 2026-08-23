import { useEffect, useState } from "react";
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

export default function JobReviewLabelControls({
  silverJobId,
  currentLabel,
  captureAvailable,
  refreshProductTruth,
}: Props) {
  const [submitting, setSubmitting] = useState<JobReviewLabelValue | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    setSubmitting(null);
    setMessage(null);
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

  return (
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
  );
}
