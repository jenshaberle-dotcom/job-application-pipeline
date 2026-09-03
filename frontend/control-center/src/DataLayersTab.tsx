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

type SourceRow = {
  source_name: string;
  source_label: string;
  last_run_at: string | null;
  last_run_status: string;
  loaded: number;
  inserted: number;
  bronze: number;
  silver: number;
  layer_status: string;
};

type DataLayersPayload = {
  schema_version: string;
  window_days: number;
  inventory: {
    bronze_jobs: number | null;
    silver_jobs: number | null;
    gold_assessed: number | null;
    rankable_now: number;
    top_jobs_now: number;
  };
  flow: FlowPoint[];
  coverage: {
    bronze_to_silver_pct: number | null;
    silver_to_gold_pct: number | null;
    gold_to_rankable_pct: number | null;
  };
  freshness: {
    latest_bronze_observation_at: string | null;
    latest_silver_normalized_at: string | null;
    latest_gold_assessed_at: string | null;
  };
  sources: SourceRow[];
  boundaries: {
    read_only: boolean;
    migration_free: boolean;
    creates_telemetry: boolean;
    historical_rankable_series_available: boolean;
    historical_top5_series_available: boolean;
  };
};

type SeriesKey = keyof Pick<
  FlowPoint,
  "bronze_new" | "bronze_observations" | "silver_normalized" | "gold_assessed"
>;

const SERIES: Array<{ key: SeriesKey; label: string; className: string }> = [
  { key: "bronze_new", label: "Bronze new", className: "bronze" },
  { key: "bronze_observations", label: "Bronze observations", className: "observations" },
  { key: "silver_normalized", label: "Silver normalized", className: "silver" },
  { key: "gold_assessed", label: "Gold assessed", className: "gold" },
];

const countText = (value: number | null) => (value == null ? "—" : value.toLocaleString());
const ratioText = (value: number | null) => (value == null ? "—" : `${value.toFixed(1)}%`);

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

function statusTone(value: string) {
  const normalized = value.toLowerCase();
  if (["success", "succeeded", "completed", "bronze_and_silver_present"].some((item) => normalized.includes(item))) return "good";
  if (["error", "failed", "inconsistent"].some((item) => normalized.includes(item))) return "bad";
  if (["unknown", "pending", "partial", "not_run"].some((item) => normalized.includes(item))) return "warn";
  return "neutral";
}

async function readDataLayers(signal?: AbortSignal): Promise<DataLayersPayload> {
  const response = await fetch("/api/v1/product-v1/data-layers", {
    ...(signal ? { signal } : {}),
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`Data Layers API returned ${response.status}`);
  return response.json() as Promise<DataLayersPayload>;
}

function FlowChart({ points }: { points: FlowPoint[] }) {
  const width = 920;
  const height = 270;
  const left = 44;
  const right = 18;
  const top = 20;
  const bottom = 42;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const values = points.flatMap((point) => SERIES.map(({ key }) => point[key]).filter((value): value is number => value != null));
  const maxValue = Math.max(1, ...values);
  const coordinates = (key: SeriesKey) => points
    .map((point, index) => {
      const value = point[key];
      if (value == null) return null;
      const x = left + (points.length <= 1 ? 0 : (index / (points.length - 1)) * plotWidth);
      const y = top + plotHeight - (value / maxValue) * plotHeight;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .filter((value): value is string => Boolean(value))
    .join(" ");

  return <div className="dl-chart-wrap">
    <svg className="dl-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="14 day Bronze Silver Gold flow">
      {[0, 0.25, 0.5, 0.75, 1].map((fraction) => {
        const y = top + plotHeight - fraction * plotHeight;
        return <g key={fraction}><line x1={left} y1={y} x2={width - right} y2={y} className="dl-grid" /><text x={left - 8} y={y + 4} className="dl-axis" textAnchor="end">{Math.round(maxValue * fraction)}</text></g>;
      })}
      {SERIES.map(({ key, className }) => {
        const line = coordinates(key);
        return line ? <polyline key={key} points={line} className={`dl-line ${className}`} fill="none" /> : null;
      })}
      {points.map((point, index) => {
        if (index !== 0 && index !== points.length - 1 && index % 3 !== 0) return null;
        const x = left + (points.length <= 1 ? 0 : (index / (points.length - 1)) * plotWidth);
        return <text key={point.date} x={x} y={height - 14} className="dl-axis" textAnchor={index === 0 ? "start" : index === points.length - 1 ? "end" : "middle"}>{point.date.slice(5)}</text>;
      })}
    </svg>
    <div className="dl-legend">{SERIES.map((series) => <span key={series.key}><i className={series.className} />{series.label}</span>)}</div>
  </div>;
}

function DataLayersScreen({ payload, refreshing, refresh }: { payload: DataLayersPayload; refreshing: boolean; refresh: () => void }) {
  const inventory = [
    ["Bronze", payload.inventory.bronze_jobs, "raw source-preserving jobs"],
    ["Silver", payload.inventory.silver_jobs, "normalized jobs"],
    ["Gold", payload.inventory.gold_assessed, "Product V1 assessments"],
    ["Rankable", payload.inventory.rankable_now, "current hard-gate pass"],
    ["Top 5", payload.inventory.top_jobs_now, "current authoritative shortlist"],
  ] as const;

  return <div className="data-layers-screen ow-stack">
    <header className="ow-page-header dl-header">
      <div><span>Pipeline observability · DB truth</span><h1>Data Layers</h1><p>Bronze → Silver → Gold materialization, current coverage and 14-day flow. Read-only and derived from existing persistence.</p></div>
      <button type="button" className="dl-refresh" disabled={refreshing} onClick={refresh}>{refreshing ? "Refreshing…" : "↻ Refresh layers"}</button>
    </header>

    <section className="dl-funnel" aria-label="Current data layer inventory">
      {inventory.map(([name, value, helper], index) => <div className={`dl-stage dl-stage-${name.toLowerCase().replace(" ", "-")}`} key={name}><span>{name}</span><strong>{countText(value)}</strong><small>{helper}</small>{index < inventory.length - 1 && <b aria-hidden="true">→</b>}</div>)}
    </section>

    <section className="dl-grid-two">
      <article className="ow-card dl-flow-card">
        <div className="ow-card-title"><div><span>Last {payload.window_days} days</span><h2>Layer flow</h2></div></div>
        <FlowChart points={payload.flow} />
        <p className="dl-truth-note">Bronze observations are repeated source sightings, not new jobs. Gold shows assessment creation. Historical Rankable/Top-5 is deliberately not reconstructed from current-state views.</p>
      </article>

      <div className="dl-side-stack">
        <article className="ow-card">
          <div className="ow-card-title"><div><span>Materialization</span><h2>Coverage</h2></div></div>
          <div className="dl-coverage">
            <div><span>Bronze → Silver</span><strong>{ratioText(payload.coverage.bronze_to_silver_pct)}</strong><i><b style={{ width: `${payload.coverage.bronze_to_silver_pct ?? 0}%` }} /></i></div>
            <div><span>Silver → Gold</span><strong>{ratioText(payload.coverage.silver_to_gold_pct)}</strong><i><b style={{ width: `${payload.coverage.silver_to_gold_pct ?? 0}%` }} /></i></div>
            <div><span>Gold → Rankable now</span><strong>{ratioText(payload.coverage.gold_to_rankable_pct)}</strong><i><b style={{ width: `${payload.coverage.gold_to_rankable_pct ?? 0}%` }} /></i></div>
          </div>
        </article>
        <article className="ow-card">
          <div className="ow-card-title"><div><span>Most recent persisted evidence</span><h2>Freshness</h2></div></div>
          <div className="dl-freshness">
            <div><span>Bronze observed</span><b>{timeText(payload.freshness.latest_bronze_observation_at)}</b></div>
            <div><span>Silver normalized</span><b>{timeText(payload.freshness.latest_silver_normalized_at)}</b></div>
            <div><span>Gold assessed</span><b>{timeText(payload.freshness.latest_gold_assessed_at)}</b></div>
          </div>
        </article>
      </div>
    </section>

    <section className="ow-card dl-source-card">
      <div className="ow-card-title"><div><span>Existing source lifecycle projection</span><h2>Source contribution</h2></div><strong>{payload.sources.length}</strong></div>
      <div className="dl-table-wrap"><table className="dl-table"><thead><tr><th>Source</th><th>Last run</th><th>Loaded</th><th>Inserted</th><th>Bronze</th><th>Silver</th><th>Status</th></tr></thead><tbody>{payload.sources.map((source) => <tr key={source.source_name}><td><b>{source.source_label}</b><small>{source.source_name}</small></td><td>{timeText(source.last_run_at)}</td><td>{source.loaded.toLocaleString()}</td><td>{source.inserted.toLocaleString()}</td><td>{source.bronze.toLocaleString()}</td><td>{source.silver.toLocaleString()}</td><td><span className={`dl-status ${statusTone(source.last_run_status)}`}>{source.last_run_status.replaceAll("_", " ")}</span></td></tr>)}</tbody></table></div>
      {payload.sources.length === 0 && <p className="dl-empty">No source contribution rows are currently projected. The tab does not manufacture demo rows.</p>}
    </section>

    <footer className="dl-boundary"><b>Truth boundary</b><span>Read-only · no migration · no telemetry writes · no source activation · no ranking/application authority.</span></footer>
  </div>;
}

export default function DataLayersTab() {
  const [navRoot, setNavRoot] = useState<HTMLElement | null>(null);
  const [mainRoot, setMainRoot] = useState<HTMLElement | null>(null);
  const [active, setActive] = useState(false);
  const [payload, setPayload] = useState<DataLayersPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    setNavRoot(document.querySelector<HTMLElement>(".ow-sidebar nav"));
    setMainRoot(document.querySelector<HTMLElement>(".ow-main"));
  }, []);

  useEffect(() => {
    document.body.classList.toggle("data-layers-active", active);
    return () => document.body.classList.remove("data-layers-active");
  }, [active]);

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

  const nav = useMemo(() => navRoot ? createPortal(<div className="ow-data-layers-nav"><button type="button" className={active ? "active" : ""} onClick={() => setActive((value) => !value)}><i>◫</i><span>Data Layers</span></button></div>, navRoot) : null, [active, navRoot]);

  const screen = active && mainRoot ? createPortal(
    error
      ? <div className="data-layers-screen ow-stack"><header className="ow-page-header"><div><span>Fail closed</span><h1>Data Layers unavailable</h1><p>{error}</p></div><button type="button" className="dl-refresh" onClick={() => void load()}>Retry</button></header></div>
      : payload
        ? <DataLayersScreen payload={payload} refreshing={refreshing} refresh={() => void load()} />
        : <div className="data-layers-screen dl-loading"><div /><p>Reading Bronze / Silver / Gold truth…</p></div>,
    mainRoot,
  ) : null;

  return <>{nav}{screen}</>;
}
