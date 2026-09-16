import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { readProductTruth } from "./productPayloadRuntimeAdapter";
import "./f4c-source-health-surface.css";

type SourceHealth = {
  status?: string;
  reason?: string;
  latest_run_status?: string;
  last_run_at?: string | null;
  last_run_age_hours?: number | null;
  freshness_status?: string;
  cadence_authority?: boolean;
};

type SourceScheduling = {
  status?: string;
  recurring_ingestion_eligible?: boolean | null;
  expected_cadence_minutes?: number | null;
  next_expected_run_at?: string | null;
  cadence_authority?: boolean;
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
};

type SourceRow = {
  source_name: string;
  operational_health?: SourceHealth;
  scheduling?: SourceScheduling;
  reachability?: SourceReachability;
  delivery?: SourceDelivery;
};

type SourceSummary = {
  current_health_healthy_count?: number;
  current_health_degraded_count?: number;
  current_health_stale_count?: number;
  current_health_unknown_count?: number;
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
  if (!value) return "Unknown";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) return value;
  return parsed.toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
};

function healthTone(value: string | null | undefined) {
  const normalized = (value || "").toLowerCase();
  if (normalized === "healthy") return "good";
  if (normalized === "degraded" || normalized === "stale") return "bad";
  return "warn";
}

export default function F4cSourceHealthSurface() {
  const [payload, setPayload] = useState<ProductPayload | null>(null);
  const [selectedName, setSelectedName] = useState("");
  const [detailRoot, setDetailRoot] = useState<HTMLElement | null>(null);
  const [summaryRoot, setSummaryRoot] = useState<HTMLElement | null>(null);

  const load = useCallback(async () => {
    try {
      setPayload(await readProductTruth<ProductPayload>({ fresh: true }));
    } catch {
      setPayload(null);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

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

  useEffect(() => {
    const listener = (event: MouseEvent) => {
      const target = event.target as Element | null;
      const button = target?.closest<HTMLButtonElement>(".ow-topline button");
      if (!button) return;
      window.setTimeout(() => void load(), 100);
    };
    document.addEventListener("click", listener);
    return () => document.removeEventListener("click", listener);
  }, [load]);

  const summary = payload?.source_connector_overview.summary;
  const source = payload?.source_connector_overview.sources.find(
    (row) => row.source_name === selectedName
  );

  const summaryPortal = summaryRoot && summary
    ? createPortal(
        <>
          <div className="f4c-health-summary"><span>Health unknown</span><b>{summary.current_health_unknown_count ?? 0}</b></div>
          <div className="f4c-health-summary"><span>Degraded / stale</span><b>{(summary.current_health_degraded_count ?? 0) + (summary.current_health_stale_count ?? 0)}</b></div>
        </>,
        summaryRoot,
      )
    : null;

  const health = source?.operational_health;
  const scheduling = source?.scheduling;
  const reachability = source?.reachability;
  const delivery = source?.delivery;

  const detailPortal = detailRoot && source
    ? createPortal(
        <section className="f4c-health-card" aria-label="Current source health">
          <div className="f4c-health-card-head">
            <div>
              <span>F4C · CURRENT SOURCE HEALTH</span>
              <h3>Current health & scheduling</h3>
            </div>
            <span className={`f4c-health-status ${healthTone(health?.status)}`}>
              {human(health?.status)}
            </span>
          </div>
          <p className="f4c-health-reason">{human(health?.reason)}</p>
          <div className="f4c-health-grid">
            <div><span>Latest run</span><b>{human(health?.latest_run_status)}</b></div>
            <div><span>Run age</span><b>{health?.last_run_age_hours == null ? "Unknown" : `${health.last_run_age_hours.toFixed(1)} h`}</b></div>
            <div><span>Scheduling</span><b>{human(scheduling?.status)}</b></div>
            <div><span>Cadence</span><b>{scheduling?.expected_cadence_minutes == null ? "No authority" : `${scheduling.expected_cadence_minutes} min`}</b></div>
            <div><span>Next expected run</span><b>{dateTime(scheduling?.next_expected_run_at)}</b></div>
            <div><span>Reachability now</span><b>{human(reachability?.status)}</b></div>
            <div><span>Last yield</span><b>{delivery?.latest_run_loaded ?? 0} loaded · {delivery?.latest_run_inserted ?? 0} inserted</b></div>
            <div><span>Zero-yield success</span><b>{delivery?.latest_success_zero_yield ? "Yes · not a failure" : "No"}</b></div>
          </div>
          <p className="f4c-health-boundary">
            A historical successful run is run history only. Current health becomes healthy or stale only with explicit cadence authority; current reachability remains unknown until actually measured.
          </p>
        </section>,
        detailRoot,
      )
    : null;

  return <>{summaryPortal}{detailPortal}</>;
}
