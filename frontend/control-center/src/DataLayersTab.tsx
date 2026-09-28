import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import "./data-layers-tab.css";

type FlowPoint = {
  date: string;
  bronze_new: number | null;
  silver_normalized: number | null;
  gold_assessed: number | null;
};

type DataLayersPayload = {
  schema_version: string;
  window_days: number;
  population: {
    key: string;
    label: string;
    all_jobs: number;
  };
  layers: {
    bronze_jobs: number;
    silver_jobs: number;
    gold_assessed: number;
    rankable_now: number;
    top_jobs_now: number;
  };
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
    single_population_current_all_jobs?: boolean;
    historical_inventory_excluded_from_primary_counts?: boolean;
    repeat_observations_excluded_from_primary_flow?: boolean;
  };
};

type SeriesKey = keyof Pick<
  FlowPoint,
  "bronze_new" | "silver_normalized" | "gold_assessed"
>;

const SERIES: Array<{
  key: SeriesKey;
  label: string;
  helper: string;
  className: string;
}> = [
  {
    key: "bronze_new",
    label: "Raw evidence added",
    helper: "Bronze · current jobs first persisted from source evidence",
    className: "bronze",
  },
  {
    key: "silver_normalized",
    label: "Normalized",
    helper: "Silver · current jobs normalized for product use",
    className: "silver",
  },
  {
    key: "gold_assessed",
    label: "Assessed",
    helper: "Gold · current jobs with Product assessment",
    className: "gold",
  },
];

const ratioText = (value: number | null) =>
  value == null ? "—" : `${value.toFixed(1)}%`;

function timeText(value: string | null) {
  if (!value) return "No evidence yet";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) return value;
  const ageMs = Math.max(0, Date.now() - parsed.valueOf());
  const hours = Math.floor(ageMs / 3_600_000);
  const age = hours < 24 ? `${hours}h ago` : `${Math.floor(hours / 24)}d ago`;
  const timestamp = parsed.toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
  return `${timestamp} · ${age}`;
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
  const layers = payload.layers;
  const stages = [
    ["Raw evidence", layers.bronze_jobs, "Bronze · current jobs with source lineage"],
    ["Normalized", layers.silver_jobs, "Silver · current jobs normalized"],
    ["Assessed", layers.gold_assessed, "Gold · current jobs with Product assessment"],
    ["Ready to rank", layers.rankable_now, "current jobs with all ranking gates passed"],
    ["Top 5", layers.top_jobs_now, "current shortlist"],
  ] as const;

  return (
    <div className="data-layers-screen ow-stack">
      <header className="ow-page-header dl-header">
        <div>
          <span>Current job data pipeline</span>
          <h1>Data Layers</h1>
          <p>
            See how the same current <b>All Jobs</b> set progresses from source evidence
            to normalized job data, Product assessment and ranking readiness.
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

      <section className="dl-scope-section dl-current-section" aria-label="Current All jobs layer population">
        <div className="dl-scope-heading">
          <div>
            <span>{payload.population.label}</span>
            <h2>{payload.population.all_jobs.toLocaleString()} current jobs</h2>
          </div>
          <p>Every stage uses the same current job set. Equal Raw and Normalized counts mean every visible job already has both source lineage and a normalized record.</p>
        </div>
        <div className="dl-funnel dl-funnel-current">
          {stages.map(([name, value, helper], index) => (
            <div className="dl-stage dl-stage-current" key={name}>
              <span>{name}</span>
              <strong>{value.toLocaleString()}</strong>
              <small>{helper}</small>
              {index < stages.length - 1 && <b aria-hidden="true">→</b>}
            </div>
          ))}
        </div>
      </section>

      <section className="dl-grid-two">
        <article className="ow-card dl-flow-card">
          <div className="ow-card-title">
            <div>
              <span>Last {payload.window_days} days · independent scales</span>
              <h2>Recent processing activity</h2>
            </div>
          </div>
          <div className="dl-small-multiples">
            {SERIES.map((series) => (
              <MiniFlowChart key={series.key} points={payload.flow} series={series} />
            ))}
          </div>
          <p className="dl-truth-note">
            Each panel has its own vertical scale. Activity is restricted to the current All Jobs set, so this is processing history for today’s visible jobs rather than total database volume.
          </p>
        </article>

        <div className="dl-side-stack">
          <article className="ow-card">
            <div className="ow-card-title">
              <div><span>Same population</span><h2>Coverage</h2></div>
            </div>
            <div className="dl-coverage">
              <div>
                <span>Raw evidence → Normalized</span>
                <strong>{ratioText(payload.coverage.bronze_to_silver_pct)}</strong>
                <i><b style={{ width: `${payload.coverage.bronze_to_silver_pct ?? 0}%` }} /></i>
              </div>
              <div>
                <span>Normalized → Assessed</span>
                <strong>{ratioText(payload.coverage.silver_to_gold_pct)}</strong>
                <i><b style={{ width: `${payload.coverage.silver_to_gold_pct ?? 0}%` }} /></i>
              </div>
              <div>
                <span>Current jobs assessed</span>
                <strong>{ratioText(payload.coverage.all_jobs_gold_assessed_pct)}</strong>
                <i><b style={{ width: `${payload.coverage.all_jobs_gold_assessed_pct ?? 0}%` }} /></i>
              </div>
            </div>
          </article>
          <article className="ow-card">
            <div className="ow-card-title">
              <div><span>Evidence timestamps</span><h2>Freshness</h2></div>
            </div>
            <div className="dl-freshness">
              <div><span>Latest source observation</span><b>{timeText(payload.freshness.latest_bronze_observation_at)}</b></div>
              <div><span>Latest normalization</span><b>{timeText(payload.freshness.latest_silver_normalized_at)}</b></div>
              <div><span>Latest Product assessment</span><b>{timeText(payload.freshness.latest_gold_assessed_at)}</b></div>
            </div>
            <p className="dl-truth-note">These are evidence timestamps for the current jobs, not the time this dashboard was refreshed.</p>
            {layers.gold_assessed < payload.population.all_jobs && (
              <div className="ow-callout warn">
                <b>Assessment gap</b>
                <span>{payload.population.all_jobs - layers.gold_assessed} current jobs still need Product assessment. Candidate Fit and the Top 5 can only use jobs that have enough verified assessment evidence.</span>
              </div>
            )}
          </article>
        </div>
      </section>

      <footer className="dl-boundary">
        <b>Scope</b>
        <span>Read-only · current All Jobs set only · historical inventory and repeat sightings are excluded from these headline counts.</span>
      </footer>
    </div>
  );
}

export default function DataLayersTab() {
  const [navRoot, setNavRoot] = useState<HTMLElement | null>(null);
  const [mainRoot, setMainRoot] = useState<HTMLElement | null>(null);
  const [toplineRoot, setToplineRoot] = useState<HTMLElement | null>(null);
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
      const topline = document.querySelector<HTMLElement>(".ow-topline > div");
      if (!nav || !main || !topline) return false;
      setNavRoot(nav);
      setMainRoot(main);
      setToplineRoot(topline);
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
          <div className="data-layers-screen dl-loading"><div /><p>Reading current Bronze / Silver / Gold truth…</p></div>
        ),
        mainRoot,
      )
    : null;

  const topline = active && toplineRoot
    ? createPortal(<b className="ow-overlay-topline-title">Data Layers</b>, toplineRoot)
    : null;

  return <>{nav}{screen}{topline}</>;
}
