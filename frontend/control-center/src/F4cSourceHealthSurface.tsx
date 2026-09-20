import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useProductTruth } from "./ProductTruthContext";
import "./f4c-source-health-surface.css";

type SourceScan = {
  status?: string;
  reason?: string;
  result?: string;
  finished_at?: string | null;
};

type SourceScheduling = {
  status?: string;
  recurring_ingestion_eligible?: boolean | null;
};

type SourceReachability = {
  status?: string;
  measured_at?: string | null;
  reason?: string;
};

type SourceDelivery = {
  latest_run_loaded?: number;
  latest_run_inserted?: number;
  latest_success_zero_yield?: boolean;
  current_job_count?: number;
  last_job_delivery_at?: string | null;
  latest_job_observed_at?: string | null;
  source_data_age_hours?: number | null;
  disappeared_comparison_available?: boolean;
  disappeared_since_previous_success?: number | null;
  previous_successful_execution_at?: string | null;
  current_successful_execution_at?: string | null;
};

type SourceRow = {
  source_name: string;
  source_scan?: SourceScan;
  scheduling?: SourceScheduling;
  reachability?: SourceReachability;
  delivery?: SourceDelivery;
};

type SourceSummary = {
  latest_scan_ok_count?: number;
  latest_scan_failed_count?: number;
  latest_scan_running_count?: number;
  reachability_not_checked_count?: number;
};

type ProductPayload = {
  source_connector_overview: {
    summary: SourceSummary;
    sources: SourceRow[];
  };
};

const human = (value: string | null | undefined) =>
  (value || "unknown").replaceAll("_", " ");

const dateTime = (value: string | null | undefined) => {
  if (!value) return "No evidence";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) return value;
  return parsed.toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
};

function scanTone(value: string | null | undefined) {
  const normalized = (value || "").toLowerCase();
  if (normalized === "ok") return "good";
  if (normalized === "failed") return "bad";
  return "warn";
}

function scanLabel(value: string | null | undefined) {
  switch ((value || "").toLowerCase()) {
    case "ok":
      return "SCAN OK";
    case "failed":
      return "SCAN FAILED";
    case "running":
      return "SCANNING";
    case "not_scanned":
      return "NOT SCANNED";
    default:
      return "SCAN UNKNOWN";
  }
}

function scanExplanation(scan?: SourceScan, delivery?: SourceDelivery) {
  switch (scan?.status) {
    case "ok":
      return delivery?.latest_run_loaded === 0
        ? "The latest source scan completed successfully and returned 0 jobs. Zero yield is not a technical failure."
        : "The latest source scan completed successfully. Live reachability is reported separately and is not inferred from run history.";
    case "failed":
      return "The latest source scan failed. This is execution evidence; it does not by itself prove that the external source is permanently offline.";
    case "running":
      return "A source scan is currently running.";
    case "not_scanned":
      return "No source scan has been recorded yet.";
    default:
      return "The latest source-scan result is not available.";
  }
}

function scheduleText(scheduling?: SourceScheduling) {
  if (scheduling?.recurring_ingestion_eligible === true) return "Enabled";
  if (scheduling?.recurring_ingestion_eligible === false) return "Not enabled";
  return "Not known";
}

function reachabilityText(reachability?: SourceReachability) {
  if (
    reachability?.status === "not_checked" ||
    reachability?.reason === "no_live_source_check_recorded"
  ) {
    return "Not checked";
  }
  return human(reachability?.status);
}

function dataAgeText(delivery?: SourceDelivery) {
  if (delivery?.source_data_age_hours == null) return "No job observation";
  const age = delivery.source_data_age_hours;
  if (age < 1) return `${Math.max(1, Math.round(age * 60))} min`;
  return `${age.toFixed(age < 10 ? 1 : 0)} h`;
}

function disappearedText(delivery?: SourceDelivery) {
  if (!delivery?.disappeared_comparison_available) return "Not comparable yet";
  return `${delivery.disappeared_since_previous_success ?? 0}`;
}

export default function F4cSourceHealthSurface() {
  const { payload } = useProductTruth<ProductPayload>();
  const [selectedName, setSelectedName] = useState("");
  const [detailRoot, setDetailRoot] = useState<HTMLElement | null>(null);
  const [summaryRoot, setSummaryRoot] = useState<HTMLElement | null>(null);

  useEffect(() => {
    let cancelled = false;

    const reconcileDom = () => {
      if (cancelled) return;

      document
        .querySelectorAll<HTMLButtonElement>(".ow-sidebar nav button")
        .forEach((button) => {
          const wrapper = button.parentElement;
          if (!wrapper) return;
          if ((button.textContent || "").includes("Operations")) {
            wrapper.dataset.f4cHidden = "true";
          }
        });

      const title = document.querySelector<HTMLElement>(".ow-page-header h1");
      if ((title?.textContent || "").trim() !== "Sources") {
        setDetailRoot(null);
        setSummaryRoot(null);
        return;
      }

      const detail = document.querySelector<HTMLElement>(".ow-source-detail");
      const code = detail?.querySelector<HTMLElement>("code");
      const summary = document.querySelector<HTMLElement>(".ow-source-summary-strip");
      setDetailRoot(detail || null);
      setSummaryRoot(summary || null);
      setSelectedName((code?.textContent || "").trim());
    };

    reconcileDom();
    const observer = new MutationObserver(reconcileDom);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
    });
    return () => {
      cancelled = true;
      observer.disconnect();
    };
  }, []);

  const summary = payload?.source_connector_overview.summary;
  const source = payload?.source_connector_overview.sources.find(
    (row) => row.source_name === selectedName
  );

  const summaryPortal = summaryRoot && summary
    ? createPortal(
        <>
          <div className="f4c-health-summary"><span>Latest scan failed</span><b>{summary.latest_scan_failed_count ?? 0}</b></div>
          <div className="f4c-health-summary"><span>Live check not measured</span><b>{summary.reachability_not_checked_count ?? 0}</b></div>
        </>,
        summaryRoot,
      )
    : null;

  const scan = source?.source_scan;
  const scheduling = source?.scheduling;
  const reachability = source?.reachability;
  const delivery = source?.delivery;

  const detailPortal = detailRoot && source
    ? createPortal(
        <section className="f4c-health-card" aria-label="Source activity and job delivery">
          <div className="f4c-health-card-head">
            <div>
              <span>F4C · SOURCE ACTIVITY</span>
              <h3>Source status & job delivery</h3>
            </div>
            <span className={`f4c-health-status ${scanTone(scan?.status)}`}>
              {scanLabel(scan?.status)}
            </span>
          </div>
          <p className="f4c-health-reason">{scanExplanation(scan, delivery)}</p>
          <div className="f4c-health-grid">
            <div>
              <span>Latest source scan</span>
              <b>{human(scan?.result)} · {dateTime(scan?.finished_at)}</b>
            </div>
            <div>
              <span>Current jobs</span>
              <b>{(delivery?.current_job_count ?? 0).toLocaleString()}</b>
            </div>
            <div>
              <span>Last job delivery</span>
              <b>{dateTime(delivery?.last_job_delivery_at)}</b>
            </div>
            <div>
              <span>Source data age</span>
              <b>{dataAgeText(delivery)}</b>
              <small>latest job observation {dateTime(delivery?.latest_job_observed_at)}</small>
            </div>
            <div>
              <span>Gone since previous successful scan</span>
              <b>{disappearedText(delivery)}</b>
              <small>shown only when two correlated successful scans are comparable</small>
            </div>
          </div>
          <div className="f4c-health-grid f4c-health-grid-secondary">
            <div><span>Live now</span><b>{reachabilityText(reachability)}</b></div>
            <div><span>Latest scan yield</span><b>{delivery?.latest_run_loaded ?? 0} loaded · {delivery?.latest_run_inserted ?? 0} inserted</b></div>
            <div><span>Recurring ingestion</span><b>{scheduleText(scheduling)}</b></div>
          </div>
          <p className="f4c-health-boundary">
            A successful scan proves that the last execution worked; it is not a live ping. “Live now” stays Not checked until JAP has an actual reachability measurement. Job age and disappearance are derived only from persisted source observations.
          </p>
        </section>,
        detailRoot,
      )
    : null;

  return <>{summaryPortal}{detailPortal}</>;
}
