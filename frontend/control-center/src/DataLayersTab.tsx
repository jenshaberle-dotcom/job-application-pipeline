import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import "./data-layers-tab.css";

type FlowPoint = {
  date: string;
  bronze_new: number | null;
  bronze_observations: number | null;
  silver_normalized: number | null;
  gold_assessed: number | null;
};

type CurrentProductScope = {
  all_jobs: number;
  gold_in_all_jobs: number;
  gold_outside_all_jobs: number;
  all_jobs_without_gold: number;
  gold_outside_historical: number;
  gold_outside_out_of_profile: number;
  gold_outside_discovery_sources: number;
  gold_outside_duplicate_origin: number;
  gold_assessed_pct: number | null;
  rankable_now: number;
  top_jobs_now: number;
};

type DataLayersPayload = {
  schema_version: string;
  window_days: number;
  inventory: {
    bronze_jobs: number | null;
    silver_jobs: number | null;
    gold_assessed: number | null;
  };
  current_product_scope: CurrentProductScope;
  flow: FlowPoint[];
  coverage: {
    bronze_to_silver_pct: number | null;
    silver_to_gold_pct: number | null;
    all_jobs_gold_assessed_pct: number | null;
  };
  freshness: {
    latest_bronze_observation_at: string | null;
    latest_silver_normalized_at: string | null;
    latest_gold_assessed_at: string | null;
  };
  boundaries: {
    read_only: boolean;
    migration_free: boolean;
    creates_telemetry: boolean;
    historical_rankable_series_available: boolean;
    historical_top5_series_available: boolean;
    persisted_inventory_is_not_current_product_scope?: boolean;
  };
};

type SeriesKey = keyof Pick<
  FlowPoint,
  "bronze_new" | "bronze_observations" | "silver_normalized" | "gold_assessed"
>;

const SERIES: Array<{
  key: SeriesKey;
  label: string;
  helper: string;
  className: string;
}> = [
  {
    key: "bronze_new",
    label: "Bronze new",
    helper: "new raw jobs persisted",
    className: "bronze",
  },
  {
    key: "bronze_observations",
    label: "Bronze observations",
    helper: "repeat source sightings · not new jobs",
    className: "observations",
  },
  {
    key: "silver_normalized",
    label: "Silver normalized",
    helper: "jobs normalized into Silver",
    className: "silver",
  },
  {
    key: "gold_assessed",
    label: "Gold assessed",
    helper: "Product assessments created",
    className: "gold",
  },
];

const countText = (value: number | null) =>
  value == null ? "—" : value.toLocaleString();
const ratioText = (value: number | null) =>
  value == null ? "—" : `${value.toFixed(1)}%`;

function timeText(value: string | null) {
  if (!value) return "No observation";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) return value;
  return parsed.toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

async function readDataLayers(signal?: AbortSignal): Promise<DataLayersPayload> {
  const response = await fetch("/api/v1/product-v1/data-layers", {
    ...(signal ? { signal } : {}),
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`Data Layers API returned ${response.status}`);
  return response.json() as Promise<DataLayersPayload>;
}

function MiniFlowChart({
  points,
  series,
}: {
  points: FlowPoint[];
  series: (typeof SERIES)[number];
}) {
  const width = 360;
  const height = 118;
  const left = 8;
  const right = 8;
  const top = 10;
  const bottom = 22;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const values = points
    .map((point) => point[series.key])
    .filter((value): value is number => value != null);
  const maxValue = Math.max(1, ...values);
  const coordinates = points
    .map((point, index) => {
      const value = point[series.key];
      if (value == null) return null;
      const x =
        left +
        (points.length <= 1 ? 0 : (index / (points.length - 1)) * plotWidth);
      const y = top + plotHeight - (value / maxValue) * plotHeight;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .filter((value): value is string => Boolean(value))
    .join(" ");
  const firstDate = points[0]?.date.slice(5) || "";
  const lastDate = points[points.length - 1]?.date.slice(5) || "";
  const latest = points[points.length - 1]?.[series.key];

  return (
    <article className="dl-series-card">
      <div className="dl-series-head">
        <div>
          <strong>{series.label}</strong>
          <span>{series.helper}</span>
        </div>
        <div>
          <b>{latest == null ? "—" : latest.toLocaleString()}</b>
          <small>latest day</small>
        </div>
      </div>
      <svg
        className="dl-mini-chart"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`${series.label} over the last ${points.length} days; independently scaled`}
      >
        {[0, 0.5, 1].map((fraction) => {
          const y = top + plotHeight - fraction * plotHeight;
          return (
            <line
              key={fraction}
              x1={left}
              y1={y}
              x2={width - right}
              y2={y}
              className="dl-grid"
            />
          );
        })}
        {coordinates ? (
          <polyline
            points={coordinates}
            className={`dl-line ${series.className}`}
            fill="none"
          />
        ) : null}
        <text x={left} y={height - 4} className="dl-axis" textAnchor="start">
          {firstDate}
        </text>
        <text
          x={width - right}
          y={height - 4}
          className="dl-axis"
          textAnchor="end"
        >
          {lastDate}
        </text>
      </svg>
      <div className="dl-series-scale">
        <span>0–{maxValue.toLocaleString()} / day</span>
        <span>independent scale</span>
      </div>
    </article>
  );
}

function DataLayersScreen({
  payload,
  refreshing,
  refresh,
}: {
  payload: DataLayersPayload;
  refreshing: boolean;
  refresh: () => void;
}) {
  const scope = payload.current_product_scope;
  const persisted = [
    ["Bronze", payload.inventory.bronze_jobs, "raw source-preserving jobs"],
    ["Silver", payload.inventory.silver_jobs, "normalized jobs"],
    ["Gold", payload.inventory.gold_assessed, "persisted Product assessments"],
  ] as const;
  const current = [
    ["All jobs", scope.all_jobs, "current operator review scope"],
    ["Gold assessed", scope.gold_in_all_jobs, "current jobs with Gold assessment"],
    ["Awaiting Gold", scope.all_jobs_without_gold, "current jobs without Gold assessment"],
    ["Rankable", scope.rankable_now, "current hard-gate pass"],
    ["Top 5", scope.top_jobs_now, "current authoritative shortlist"],
  ] as const;

  const excludedParts = [
    scope.gold_outside_historical > 0
      ? `${scope.gold_outside_historical} historical`
      : null,
    scope.gold_outside_out_of_profile > 0
      ? `${scope.gold_outside_out_of_profile} out of profile`
      : null,
    scope.gold_outside_discovery_sources > 0
      ? `${scope.gold_outside_discovery_sources} discovery-source`
      : null,
    scope.gold_outside_duplicate_origin > 0
      ? `${scope.gold_outside_duplicate_origin} duplicate-origin`
      : null,
  ].filter((value): value is string => Boolean(value));

  return (
    <div className="data-layers-screen ow-stack">
      <header className="ow-page-header dl-header">
        <div>
          <span>Pipeline observability · DB truth</span>
          <h1>Data Layers</h1>
          <p>
            Persisted Bronze → Silver → Gold inventory and the current Product
            review scope are shown separately. Read-only and derived from existing
            persistence.
          </p>
        </div>
        <button
          type="button"
          className="dl-refresh"
          disabled={refreshing}
          onClick={refresh}
        >
          {refreshing ? "Refreshing…" : "↻ Refresh layers"}
        </button>
      </header>

      <section className="dl-scope-section" aria-label="Persisted data layer inventory">
        <div className="dl-scope-heading">
          <div>
            <span>Persisted inventory</span>
            <h2>Storage layers</h2>
          </div>
          <p>Historical rows remain counted here even when they are no longer in the current operator review scope.</p>
        </div>
        <div className="dl-funnel dl-funnel-persisted">
          {persisted.map(([name, value, helper], index) => (
            <div
              className={`dl-stage dl-stage-${name.toLowerCase()}`}
              key={name}
            >
              <span>{name}</span>
              <strong>{countText(value)}</strong>
              <small>{helper}</small>
              {index < persisted.length - 1 && <b aria-hidden="true">→</b>}
            </div>
          ))}
        </div>
      </section>

      <section className="dl-scope-section dl-current-section" aria-label="Current Product scope">
        <div className="dl-scope-heading">
          <div>
            <span>Current Product scope</span>
            <h2>What the operator can act on now</h2>
          </div>
          <p><b>All jobs</b> is the same current review population shown in the main navigation.</p>
        </div>
        <div className="dl-funnel dl-funnel-current">
          {current.map(([name, value, helper]) => (
            <div className="dl-stage dl-stage-current" key={name}>
              <span>{name}</span>
              <strong>{value.toLocaleString()}</strong>
              <small>{helper}</small>
            </div>
          ))}
        </div>
        <div className="dl-reconciliation">
          <b>{scope.gold_outside_all_jobs.toLocaleString()} persisted Gold outside current All jobs</b>
          <span>{excludedParts.length > 0 ? excludedParts.join(" · ") : "no excluded Gold rows"}</span>
          <i aria-hidden="true">•</i>
          <b>{scope.gold_in_all_jobs.toLocaleString()} / {scope.all_jobs.toLocaleString()} current jobs assessed</b>
          <span>{scope.all_jobs_without_gold.toLocaleString()} awaiting Gold</span>
        </div>
      </section>

      <section className="dl-grid-two">
        <article className="ow-card dl-flow-card">
          <div className="ow-card-title">
            <div>
              <span>Last {payload.window_days} days · independent scales</span>
              <h2>Layer flow</h2>
            </div>
          </div>
          <div className="dl-small-multiples">
            {SERIES.map((series) => (
              <MiniFlowChart key={series.key} points={payload.flow} series={series} />
            ))}
          </div>
          <p className="dl-truth-note">
            Each panel has its own vertical scale so low-volume Silver/Gold activity remains readable. Compare each series over time, not line height between panels. Bronze observations are repeated source sightings, not new jobs.
          </p>
        </article>

        <div className="dl-side-stack">
          <article className="ow-card">
            <div className="ow-card-title">
              <div><span>Population-aware</span><h2>Coverage</h2></div>
            </div>
            <div className="dl-coverage">
              <div>
                <span>Persisted Bronze → Silver</span>
                <strong>{ratioText(payload.coverage.bronze_to_silver_pct)}</strong>
                <i><b style={{ width: `${payload.coverage.bronze_to_silver_pct ?? 0}%` }} /></i>
              </div>
              <div>
                <span>Persisted Silver → Gold</span>
                <strong>{ratioText(payload.coverage.silver_to_gold_pct)}</strong>
                <i><b style={{ width: `${payload.coverage.silver_to_gold_pct ?? 0}%` }} /></i>
              </div>
              <div>
                <span>Current All jobs with Gold assessment</span>
                <strong>{ratioText(payload.coverage.all_jobs_gold_assessed_pct)}</strong>
                <i><b style={{ width: `${payload.coverage.all_jobs_gold_assessed_pct ?? 0}%` }} /></i>
              </div>
            </div>
          </article>
          <article className="ow-card">
            <div className="ow-card-title">
              <div><span>Most recent persisted evidence</span><h2>Freshness</h2></div>
            </div>
            <div className="dl-freshness">
              <div><span>Bronze observed</span><b>{timeText(payload.freshness.latest_bronze_observation_at)}</b></div>
              <div><span>Silver normalized</span><b>{timeText(payload.freshness.latest_silver_normalized_at)}</b></div>
              <div><span>Gold assessed</span><b>{timeText(payload.freshness.latest_gold_assessed_at)}</b></div>
            </div>
          </article>
        </div>
      </section>

      <footer className="dl-boundary">
        <b>Truth boundary</b>
        <span>Read-only · persisted inventory ≠ current Product scope · no migration · no telemetry writes · no source activation · no ranking/application authority.</span>
      </footer>
    </div>
  );
}

export default function DataLayersTab() {
  const [navRoot, setNavRoot] = useState<HTMLElement | null>(null);
  const [mainRoot, setMainRoot] = useState<HTMLElement | null>(null);
  const [active, setActive] = useState(false);
  const [payload, setPayload] = useState<DataLayersPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let observer: MutationObserver | null = null;

    const bindRoots = () => {
      if (cancelled) return false;
      const nav = document.querySelector<HTMLElement>(".ow-sidebar nav");
      const main = document.querySelector<HTMLElement>(".ow-main");
      if (!nav || !main) return false;
      setNavRoot(nav);
      setMainRoot(main);
      return true;
    };

    if (!bindRoots()) {
      observer = new MutationObserver(() => {
        if (bindRoots()) observer?.disconnect();
      });
      observer.observe(document.body, { childList: true, subtree: true });
    }

    return () => {
      cancelled = true;
      observer?.disconnect();
    };
  }, []);

  useEffect(() => {
    document.body.classList.toggle("data-layers-active", active);
    return () => document.body.classList.remove("data-layers-active");
  }, [active]);

  useEffect(() => {
    const onNavigationClick = (event: MouseEvent) => {
      const target = event.target as Element | null;
      const button = target?.closest<HTMLButtonElement>(".ow-sidebar nav button");
      if (!button || button.closest(".ow-data-layers-nav")) return;
      setActive(false);
    };
    document.addEventListener("click", onNavigationClick);
    return () => document.removeEventListener("click", onNavigationClick);
  }, []);

  const load = async () => {
    setRefreshing(true);
    try {
      setPayload(await readDataLayers());
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (!active || payload || refreshing) return;
    void load();
  }, [active, payload, refreshing]);

  const nav = useMemo(
    () =>
      navRoot
        ? createPortal(
            <div className="ow-data-layers-nav">
              <button
                type="button"
                className={active ? "active" : ""}
                onClick={() => setActive((value) => !value)}
              >
                <i>◫</i><span>Data Layers</span>
              </button>
            </div>,
            navRoot,
          )
        : null,
    [active, navRoot],
  );

  const screen = active && mainRoot
    ? createPortal(
        error ? (
          <div className="data-layers-screen ow-stack">
            <header className="ow-page-header">
              <div><span>Fail closed</span><h1>Data Layers unavailable</h1><p>{error}</p></div>
              <button type="button" className="dl-refresh" onClick={() => void load()}>Retry</button>
            </header>
          </div>
        ) : payload ? (
          <DataLayersScreen payload={payload} refreshing={refreshing} refresh={() => void load()} />
        ) : (
          <div className="data-layers-screen dl-loading"><div /><p>Reading Bronze / Silver / Gold truth…</p></div>
        ),
        mainRoot,
      )
    : null;

  return <>{nav}{screen}</>;
}
