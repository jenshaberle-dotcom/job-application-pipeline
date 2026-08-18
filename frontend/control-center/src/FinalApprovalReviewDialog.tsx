import { useEffect, useState } from "react";
import "./final-approval.css";

export const FINAL_APPROVAL_ACTION_PATH = "/api/v1/source-connectors/final-approval";
export const FINAL_APPROVAL_CONFIRMATION = "approve_final_registration_gate";

export type FinalApprovalReviewSource = {
  candidate_id: number | null;
  source_name: string;
  source_label: string;
  source_type: string;
  candidate_status: string;
  current_blocker?: string | null;
  gates: {
    connector_validation_gate: {
      status: string;
      decision?: string | null;
      passed: boolean;
      truth_source: string;
    };
    final_approval_gate: {
      status: string;
      decision?: string | null;
      passed: boolean;
      truth_source: string;
    };
  };
};

type Props = {
  source: FinalApprovalReviewSource | null;
  refreshProductTruth: () => Promise<void>;
  onClose: () => void;
};

const label = (value: string | null | undefined) =>
  (value || "unknown").replaceAll("_", " ");

export default function FinalApprovalReviewDialog({
  source,
  refreshProductTruth,
  onClose,
}: Props) {
  const [confirmed, setConfirmed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    setConfirmed(false);
    setSubmitting(false);
    setMessage(null);
  }, [source?.candidate_id]);

  if (
    source === null ||
    source.current_blocker !== "final_approval_incomplete" ||
    source.candidate_id === null ||
    !Number.isInteger(source.candidate_id) ||
    source.candidate_id <= 0
  ) {
    return null;
  }

  const candidateId = source.candidate_id;

  const submitFinalApproval = async () => {
    if (!confirmed || submitting) return;

    setSubmitting(true);
    setMessage(null);
    let actionSucceeded = false;
    let actionMessage = "Final approval action completed.";

    try {
      const response = await fetch(FINAL_APPROVAL_ACTION_PATH, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          candidate_id: candidateId,
          confirmation: FINAL_APPROVAL_CONFIRMATION,
        }),
      });
      const result = (await response.json().catch(() => null)) as
        | { status?: string; reason?: string }
        | null;
      if (!response.ok) {
        throw new Error(result?.reason || `Final approval API returned ${response.status}`);
      }
      actionSucceeded = true;
      actionMessage = result?.status
        ? `Final approval result: ${label(result.status)}.`
        : actionMessage;
    } catch (reason: unknown) {
      actionMessage = `Final approval was not confirmed: ${String(reason)}`;
    }

    try {
      await refreshProductTruth();
    } catch (reason: unknown) {
      actionSucceeded = false;
      actionMessage = `${actionMessage} Product/DB truth reload failed: ${String(reason)}`;
    } finally {
      setSubmitting(false);
      setConfirmed(false);
    }

    if (actionSucceeded) {
      onClose();
      return;
    }
    setMessage(actionMessage);
  };

  return (
    <div className="approval-dialog-backdrop" role="presentation">
      <section
        aria-labelledby="final-approval-title"
        aria-modal="true"
        className="approval-dialog"
        role="dialog"
      >
        <header>
          <div>
            <span className="eyebrow">Reviewed 3A action · exact candidate target</span>
            <h3 id="final-approval-title">Final approval review</h3>
            <p>{source.source_label} · <code>{source.source_name}</code></p>
          </div>
          <button className="dialog-close" type="button" onClick={onClose} disabled={submitting}>
            Close
          </button>
        </header>

        <div className="approval-review-grid">
          <section>
            <span className="eyebrow">Evidence</span>
            <dl>
              <div><dt>Candidate ID</dt><dd>{candidateId}</dd></div>
              <div><dt>Candidate status</dt><dd>{label(source.candidate_status)}</dd></div>
              <div><dt>Validation gate</dt><dd>{label(source.gates.connector_validation_gate.status)}</dd></div>
              <div><dt>Validation decision</dt><dd>{label(source.gates.connector_validation_gate.decision)}</dd></div>
              <div><dt>Final approval gate</dt><dd>{label(source.gates.final_approval_gate.status)}</dd></div>
            </dl>
          </section>

          <section>
            <span className="eyebrow">Boundary</span>
            <p>This action records only the existing employer-origin final approval gate through the reviewed 3A A1 authorization path.</p>
            <ul>
              <li>No connector registration or source activation.</li>
              <li>No ingestion, scheduler, ranking or application action.</li>
              <li>No provider, LLM or Tavily request.</li>
              <li>Product/DB truth is reloaded after the POST result.</li>
            </ul>
          </section>

          <section>
            <span className="eyebrow">Confirmation</span>
            <label className="approval-confirmation">
              <input
                type="checkbox"
                checked={confirmed}
                disabled={submitting}
                onChange={(event) => setConfirmed(event.target.checked)}
              />
              <span>I confirm the final registration gate for candidate #{candidateId}.</span>
            </label>
            <div className="approval-dialog-actions">
              <button type="button" className="secondary-action" onClick={onClose} disabled={submitting}>
                Cancel
              </button>
              <button
                type="button"
                className="approval-action"
                disabled={!confirmed || submitting}
                onClick={submitFinalApproval}
              >
                {submitting ? "Recording gate…" : "Confirm final approval"}
              </button>
            </div>
            {message && <p className="approval-message" role="status">{message}</p>}
          </section>
        </div>
      </section>
    </div>
  );
}
