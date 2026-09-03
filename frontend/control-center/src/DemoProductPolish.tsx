import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import "./demo-product-polish.css";

type PolishPayload = {
  summary: {
    observed_job_count: number;
    current_active_job_count: number;
    rankable_job_count: number;
    top_job_count: number;
    application_ready_count: number;
  };
  application_sources_ready: {
    base_cv: boolean;
    base_application_letter: boolean;
  };
  source_connector_overview: {
    summary: {
      source_count: number;
      final_approved_count: number;
      attention_count: number;
    };
    sources: Array<{
      source_name: string;
      source_label: string;
      current_blocker?: string | null;
      next_action: string;
    }>;
  };
  operator_blockers: Array<{
    code: string;
    title: string;
    detail: string;
  }>;
};

type IconName =
  | "discover"
  | "verify"
  | "rank"
  | "prepare"
  | "attention"
  | "prepared"
  | "applied"
  | "reply"
  | "interview"
  | "offer"
  | "closed";

const TOOLTIP_COPY: Record<string, string> = {
  Bronze: "Raw, source-preserving job evidence before normalization.",
  Silver: "Normalized canonical job records derived from source evidence.",
  Gold: "Product V1 assessment materialization. It is not historical Top-5 membership.",
  Rankable: "Current jobs for which the required hard gates have passed.",
  "Top 5": "The current authoritative shortlist. Empty slots stay empty rather than being fabricated.",
  "Profile fit": "Deterministic Product V1 fit score. It is not a probability of getting hired and does not create ranking authority by itself.",
  "Bronze → Silver": "Materialization coverage only; this is not a quality or causal conversion metric.",
  "Silver → Gold": "Assessment materialization coverage only; this is not a quality or causal conversion metric.",
  "Gold → Rankable now": "Current share of assessed jobs passing required ranking gates; not a historical conversion rate.",
};

const viewId = () => {
  if (document.body.classList.contains("data-layers-active")) return "data-layers";
  return (document.querySelector<HTMLElement>(".ow-topline > div > b")?.textContent || "")
    .trim()
    .toLocaleLowerCase();
};

const countText = (value: number) => value.toLocaleString();

function Icon({ name }: { name: IconName }) {
  const paths: Record<IconName, JSX.Element> = {
    discover: <><circle cx="11" cy="11" r="6" /><path d="m16 16 4 4" /></>,
    verify: <><path d="M12 3 5 6v5c0 4.8 2.9 8.1 7 10 4.1-1.9 7-5.2 7-10V6l-7-3Z" /><path d="m9 12 2 2 4-5" /></>,
    rank: <><path d="m12 3 2.5 5.1 5.6.8-4 3.9.9 5.5-5-2.6-5 2.6.9-5.5-4-3.9 5.6-.8L12 3Z" /></>,
    prepare: <><path d="M7 3h8l4 4v14H7z" /><path d="M15 3v5h5M10 13h6M10 17h6" /></>,
    attention: <><path d="M12 4 3 20h18L12 4Z" /><path d="M12 9v5M12 17h.01" /></>,
    prepared: <><path d="M6 3h9l3 3v15H6z" /><path d="m9 13 2 2 4-5" /></>,
    applied: <><path d="M4 12h12" /><path d="m12 8 4 4-4 4" /><path d="M20 5v14" /></>,
    reply: <><path d="M4 5h16v11H8l-4 4V5Z" /><path d="M8 9h8M8 12h5" /></>,
    interview: <><rect x="4" y="5" width="16" height="15" rx="2" /><path d="M8 3v4M16 3v4M4 10h16M9 14h2M13 14h2" /></>,
    offer: <><path d="M5 8h14v12H5z" /><path d="M9 8V5h6v3M5 12h14" /></>,
    closed: <><circle cx="12" cy="12" r="9" /><path d="m8 12 3 3 5-6" /></>,
  };
  return <svg className="demo-icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}

async function readProductTruth(): Promise<PolishPayload> {
  const response = await fetch("/api/v1/product-v1", { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`API returned ${response.status}`);
  return response.json() as Promise<PolishPayload>;
}

function applyTooltips() {
  document.querySelectorAll<HTMLElement>("span, h2, h3, th").forEach((element) => {
    const copy = TOOLTIP_COPY[(element.textContent || "").trim()];
    if (!copy) return;
    element.title = copy;
    element.classList.add("demo-has-tooltip");
  });
}

function Journey({ payload }: { payload: PolishPayload }) {
  const steps = [
    { icon: "discover" as const, label: "Discover", value: payload.summary.observed_job_count, helper: "observed jobs" },
    { icon: "verify" as const, label: "Verify", value: payload.summary.current_active_job_count, helper: "current vacancies" },
    { icon: "rank" as const, label: "Rank", value: payload.summary.rankable_job_count, helper: "hard gates passed" },
    { icon: "prepare" as const, label: "Prepare", value: payload.summary.application_ready_count, helper: "draft context ready" },
  ];
  return <section className="demo-journey" aria-label="Product journey Discover Verify Rank Prepare">
    <div className="demo-section-heading"><span>Product journey</span><b>Discover → Verify → Rank → Prepare</b></div>
    <div className="demo-journey-steps">
      {steps.map((step, index) => <article key={step.label}>
        <div className="demo-icon-tile"><Icon name={step.icon} /></div>
        <div><span>{step.label}</span><strong>{countText(step.value)}</strong><small>{step.helper}</small></div>
        {index < steps.length - 1 && <i aria-hidden="true">→</i>}
      </article>)}
    </div>
  </section>;
}

function AttentionPanel({ payload }: { payload: PolishPayload }) {
  const attention = useMemo(() => {
    const items: Array<{ key: string; title: string; detail: string }> = [];
    payload.source_connector_overview.sources
      .filter((source) => Boolean(source.current_blocker))
      .forEach((source) => items.push({
        key: `source:${source.source_name}`,
        title: source.source_label,
        detail: source.next_action,
      }));
    payload.operator_blockers.forEach((blocker) => items.push({
      key: `product:${blocker.code}`,
      title: blocker.title,
      detail: blocker.detail,
    }));
    if (!payload.application_sources_ready.base_cv) items.push({ key: "base-cv", title: "Base CV required", detail: "Approve the local base CV in Application before preparing a grounded review draft." });
    if (!payload.application_sources_ready.base_application_letter) items.push({ key: "base-letter", title: "Base letter required", detail: "Approve the local base letter in Application before preparing a grounded review draft." });
    return items;
  }, [payload]);

  return <section className={`demo-attention ${attention.length ? "has-items" : "clear"}`} aria-label="Operator attention and next actions">
    <div className="demo-attention-head">
      <div className="demo-icon-tile"><Icon name="attention" /></div>
      <div><span>Operator focus</span><h2>{attention.length ? `${attention.length} item${attention.length === 1 ? "" : "s"} need attention` : "No current operator blocker"}</h2><p>{attention.length ? "Existing Product V1/source truth only — no inferred authority." : "The current Product V1 projection exposes no operator blocker."}</p></div>
      <strong>{attention.length}</strong>
    </div>
    {attention.length > 0 && <div className="demo-attention-list">{attention.slice(0, 4).map((item) => <article key={item.key}><b>{item.title}</b><span>{item.detail}</span></article>)}</div>}
  </section>;
}

function ApplicationLifecycle({ payload }: { payload: PolishPayload }) {
  const prepared = payload.summary.top_job_count > 0
    && payload.application_sources_ready.base_cv
    && payload.application_sources_ready.base_application_letter;
  const stages: Array<{ icon: IconName; label: string; detail: string; state: "current" | "pending" | "future" }> = [
    { icon: "prepared", label: "Prepared", detail: prepared ? "Ready for a human-reviewed draft" : "Preparation prerequisites incomplete", state: prepared ? "current" : "pending" },
    { icon: "applied", label: "Applied", detail: "Awaiting manual submission confirmation", state: "future" },
    { icon: "reply", label: "Reply", detail: "Tracking begins only after submission", state: "future" },
    { icon: "interview", label: "Interview", detail: "No authoritative event recorded", state: "future" },
    { icon: "offer", label: "Offer", detail: "No authoritative event recorded", state: "future" },
    { icon: "closed", label: "Closed", detail: "No authoritative outcome recorded", state: "future" },
  ];
  return <section className="demo-application-lifecycle" aria-label="Planned evidence-first application lifecycle">
    <div className="demo-lifecycle-heading"><div><span>Evidence-first lifecycle · APP-TRACK-001</span><h2>Prepared → Applied → Reply → Interview → Offer → Closed</h2></div><b>Future-safe surface</b></div>
    <div className="demo-lifecycle-stages">{stages.map((stage, index) => <article key={stage.label} className={stage.state}>
      <div className="demo-icon-tile"><Icon name={stage.icon} /></div>
      <span>{stage.label}</span>
      <b>{stage.detail}</b>
      {index < stages.length - 1 && <i aria-hidden="true">→</i>}
    </article>)}</div>
    <div className="demo-lifecycle-boundary"><strong>Tracking begins after manual submission confirmation.</strong><span>Email/recruiter communication may later become evidence, but it does not silently become application-state authority.</span></div>
  </section>;
}

export default function DemoProductPolish() {
  const [payload, setPayload] = useState<PolishPayload | null>(null);
  const [stackRoot, setStackRoot] = useState<HTMLElement | null>(null);
  const [view, setView] = useState("");

  useEffect(() => {
    let cancelled = false;
    const load = () => readProductTruth().then((truth) => {
      if (!cancelled) setPayload(truth);
    }).catch(() => {
      // Cosmetic enhancement must never replace or weaken the canonical fail-closed UI.
    });
    void load();

    const syncDom = () => {
      const nextView = viewId();
      setView((current) => current === nextView ? current : nextView);
      const nextRoot = document.querySelector<HTMLElement>(".ow-main > .ow-stack");
      setStackRoot((current) => current === nextRoot ? current : nextRoot);
      document.body.dataset.demoView = nextView;
      applyTooltips();
    };
    syncDom();

    const observer = new MutationObserver(syncDom);
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["class"] });
    const onClick = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest(".ow-topline button, .dl-refresh")) window.setTimeout(() => void load(), 250);
    };
    document.addEventListener("click", onClick);

    return () => {
      cancelled = true;
      observer.disconnect();
      document.removeEventListener("click", onClick);
      delete document.body.dataset.demoView;
      document.body.classList.remove("demo-polish-ready");
    };
  }, []);

  useEffect(() => {
    document.body.classList.toggle("demo-polish-ready", Boolean(payload));
    applyTooltips();
  }, [payload, view]);

  if (!payload || !stackRoot) return null;

  if (view === "overall") return createPortal(<><Journey payload={payload} /><AttentionPanel payload={payload} /></>, stackRoot);
  if (view === "applications") return createPortal(<ApplicationLifecycle payload={payload} />, stackRoot);
  return null;
}
