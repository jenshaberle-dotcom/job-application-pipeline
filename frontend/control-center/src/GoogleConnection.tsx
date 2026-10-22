import { useEffect, useState } from "react";

type Connection = { state: string; authorization_url?: string };
const endpoint = "/api/v1/product-v1/google-connection";
const labels: Record<string, string> = {
  disconnected: "Google ist noch nicht verbunden.",
  configured: "Anmeldung vorhanden. Der nächste Abruf prüft die Verbindung.",
  reauth_required: "Die Google-Anmeldung ist abgelaufen. Bitte erneut anmelden.",
  starting: "Anmeldung wird vorbereitet …",
  awaiting_google: "Bitte im Browser bei Google anmelden.",
  connected: "Google-Anmeldung erfolgreich. Du kannst das Postfach jetzt synchronisieren.",
  login_failed: "Anmeldung nicht abgeschlossen. Du kannst es erneut versuchen.",
  setup_required: "Die lokale Google-Anbindung muss zuerst eingerichtet werden.",
  unavailable: "Verbindungsstatus derzeit nicht erreichbar.",
  sync_running: "Ein Postfachabruf läuft noch. Bitte danach erneut anmelden.",
};

export default function GoogleConnection() {
  const [open, setOpen] = useState(false);
  const [connection, setConnection] = useState<Connection>({ state: "loading" });
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState("");
  async function load() {
    try {
      const response = await fetch(endpoint);
      if (!response.ok) throw new Error();
      setConnection(await response.json());
    } catch { setConnection({ state: "unavailable" }); }
  }
  useEffect(() => {
    if (!open) return;
    void load();
    const timer = window.setInterval(() => void load(), 2000);
    return () => window.clearInterval(timer);
  }, [open]);
  async function connect() {
    setMessage("");
    try {
      const response = await fetch(endpoint, {
        method: "POST", headers: { "X-JAP-Action": "google-connect" },
      });
      if (!response.ok) throw new Error();
      setConnection(await response.json());
    } catch { setMessage("Anmeldung konnte nicht gestartet werden."); }
  }
  async function sync() {
    setSyncing(true);
    try {
      const response = await fetch("/api/v1/product-v1/mailbox-sync", { method: "POST" });
      setMessage(response.ok ? "Postfach abgeglichen. Aktualisiere jetzt die Ansicht."
        : "Abruf fehlgeschlagen. Bitte den Verbindungsstatus prüfen.");
      await load();
    } catch { setMessage("Postfach derzeit nicht erreichbar."); }
    finally { setSyncing(false); }
  }
  const busy = ["starting", "awaiting_google"].includes(connection.state);
  return <>
    <button type="button" onClick={() => setOpen(true)}>✉ Google / Postfach</button>
    {open && <dialog open aria-labelledby="google-heading" style={{
      position: "fixed", inset: "15% auto auto 50%", transform: "translateX(-50%)",
      zIndex: 1000, width: "min(520px, 90vw)", padding: 24,
      background: "#10212d", color: "#e5f3fa", border: "1px solid #39768a",
      borderRadius: 16, boxShadow: "0 20px 80px #0009",
    }}>
      <h2 id="google-heading">Google-Postfach verbinden</h2>
      <p>JAP liest Nachrichten. Es werden keine E-Mails versendet oder gelöscht.</p>
      <p role="status">{labels[connection.state] ?? "Status wird geprüft …"}</p>
      <button type="button" disabled={busy} onClick={() => void connect()}>
        {connection.state === "disconnected" ? "Mit Google verbinden" : "Google-Anmeldung erneuern"}
      </button>
      {connection.authorization_url && <p><a href={connection.authorization_url}
        target="_blank" rel="noopener noreferrer">Anmeldung bei Google im Browser öffnen ↗</a></p>}
      <p><button type="button" disabled={syncing || !["configured", "connected"].includes(connection.state)}
        onClick={() => void sync()}>{syncing ? "Postfach wird gelesen …" : "Postfach jetzt synchronisieren"}</button></p>
      <p role="status">{message}</p>
      <button type="button" onClick={() => setOpen(false)}>Schließen</button>
    </dialog>}
  </>;
}
