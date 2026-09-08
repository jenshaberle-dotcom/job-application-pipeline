import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import "./about-panel.css";

type AppInfo = {
  schema?: string;
  app_name?: string;
  product_name?: string;
  desktop_version?: string;
  source_revision?: string;
  desktop_host?: string;
  runtime_surface?: string;
  data_truth?: string;
  product_mode?: string;
  update_policy?: string;
  compatibility_line?: string;
};

async function readAppInfo(signal?: AbortSignal): Promise<AppInfo> {
  const response = await fetch("/app-info.json", {
    ...(signal ? { signal } : {}),
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`App info returned ${response.status}`);
  return response.json() as Promise<AppInfo>;
}

const value = (raw: string | undefined, fallback = "Unavailable") =>
  raw?.trim() || fallback;

function AboutScreen({ info, error }: { info: AppInfo | null; error: string | null }) {
  const revision = info?.source_revision?.trim();
  const shortRevision = revision && /^[0-9a-f]{40}$/i.test(revision)
    ? revision.slice(0, 12)
    : value(revision, "development");

  return <div className="about-screen ow-stack">
    <header className="ow-page-header">
      <div>
        <span>Application information</span>
        <h1>About</h1>
        <p>Installed desktop, runtime and update identity for the local JAP Control Center.</p>
      </div>
    </header>

    {error && <section className="ow-card about-error"><h2>App information unavailable</h2><p>{error}</p></section>}

    <section className="about-grid">
      <article className="ow-card about-version-card">
        <span className="ow-kicker">Installed application</span>
        <h2>{value(info?.app_name, "JAP Control Center")}</h2>
        <strong className="about-version">v{value(info?.desktop_version, "?")}</strong>
        <p>{value(info?.product_name, "Job Application Pipeline")}</p>
      </article>

      <article className="ow-card">
        <span className="ow-kicker">Runtime identity</span>
        <h2>Local execution</h2>
        <div className="about-facts">
          <div><span>Source revision</span><code title={revision || undefined}>{shortRevision}</code></div>
          <div><span>Desktop host</span><b>{value(info?.desktop_host)}</b></div>
          <div><span>Runtime</span><b>{value(info?.runtime_surface)}</b></div>
          <div><span>Data truth</span><b>{value(info?.data_truth)}</b></div>
        </div>
      </article>

      <article className="ow-card">
        <span className="ow-kicker">Product boundary</span>
        <h2>Review-first</h2>
        <div className="about-facts">
          <div><span>Product mode</span><b>{value(info?.product_mode, "review-first")}</b></div>
          <div><span>Application action</span><b>Human review required</b></div>
          <div><span>Submission</span><b>No automatic submit/send</b></div>
          <div><span>Evidence preview</span><b>Internal diagnostic only</b></div>
        </div>
      </article>

      <article className="ow-card">
        <span className="ow-kicker">Updates</span>
        <h2>Managed desktop channel</h2>
        <div className="about-facts">
          <div><span>Policy</span><b>{value(info?.update_policy, "latest-direct")}</b></div>
          <div><span>Compatibility line</span><b>v{value(info?.compatibility_line, "1")}.x</b></div>
          <div><span>Consent</span><b>GUI-confirmed updates</b></div>
          <div><span>Deferral</span><b>6 hour snooze</b></div>
        </div>
      </article>
    </section>
  </div>;
}

export default function AboutPanel() {
  const [navRoot, setNavRoot] = useState<HTMLElement | null>(null);
  const [mainRoot, setMainRoot] = useState<HTMLElement | null>(null);
  const [active, setActive] = useState(false);
  const [info, setInfo] = useState<AppInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: number | null = null;
    let attempts = 0;

    const bindRoots = () => {
      if (cancelled) return;
      const nav = document.querySelector<HTMLElement>(".ow-sidebar nav");
      const main = document.querySelector<HTMLElement>(".ow-main");
      if (nav && main) {
        setNavRoot(nav);
        setMainRoot(main);
        return;
      }
      attempts += 1;
      if (attempts < 80) timer = window.setTimeout(bindRoots, 50);
    };

    bindRoots();
    return () => {
      cancelled = true;
      if (timer != null) window.clearTimeout(timer);
    };
  }, []);

  useEffect(() => {
    document.body.classList.toggle("about-active", active);
    return () => document.body.classList.remove("about-active");
  }, [active]);

  useEffect(() => {
    const onNavigationClick = (event: MouseEvent) => {
      const target = event.target as Element | null;
      const button = target?.closest<HTMLButtonElement>(".ow-sidebar nav button");
      if (!button || button.closest(".ow-about-nav")) return;
      setActive(false);
    };
    document.addEventListener("click", onNavigationClick);
    return () => document.removeEventListener("click", onNavigationClick);
  }, []);

  useEffect(() => {
    if (!active || info) return;
    const controller = new AbortController();
    readAppInfo(controller.signal)
      .then((payload) => {
        setInfo(payload);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => controller.abort();
  }, [active, info]);

  const nav = useMemo(
    () => navRoot
      ? createPortal(
          <div className="ow-about-nav">
            <button type="button" className={active ? "active" : ""} onClick={() => setActive((current) => !current)}>
              <i>ⓘ</i><span>About</span>
            </button>
          </div>,
          navRoot,
        )
      : null,
    [active, navRoot],
  );

  const screen = active && mainRoot
    ? createPortal(<AboutScreen info={info} error={error} />, mainRoot)
    : null;

  return <>{nav}{screen}</>;
}
