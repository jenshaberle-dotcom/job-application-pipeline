import { useEffect, useMemo, useState } from "react";
import "./f6-template-review-editor.css";

type DraftFragment = {
  kind?: string;
  text?: string;
};

type ReviewZone = {
  id: string;
  page: number;
  bbox: number[];
  source_text: string;
  editable: boolean;
};

type ReviewTemplate = {
  document_type: "base_cv" | "base_application_letter";
  template_id: string;
  canonical_filename: string;
  source_sha256: string;
  page_count: number;
  zones: ReviewZone[];
};

type ReviewPayload = {
  status?: string;
  reason?: string;
  templates?: ReviewTemplate[];
  human_review_required?: boolean;
};

type RenderEvidence = {
  status?: string;
  output_sha256?: string;
  applied_zone_ids?: string[];
  outside_zone_pixel_identity?: boolean;
};

type ExportDocument = {
  document_type: "base_cv" | "base_application_letter";
  download_filename: string;
  pdf_base64: string;
  render_evidence: RenderEvidence;
};

type ExportPayload = {
  status?: string;
  reason?: string;
  documents?: ExportDocument[];
  human_review_required?: boolean;
  submission_actions?: number;
  send_actions?: number;
};

type ZoneValues = Record<string, Record<string, string>>;

type LocalExport = ExportDocument & { objectUrl: string };

async function readJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers || {}),
    },
  });
  const payload = await response.json() as T;
  if (!response.ok) {
    const reason = (payload as { reason?: string }).reason || `API returned ${response.status}`;
    throw new Error(reason);
  }
  return payload;
}

function cloneValues(values: ZoneValues): ZoneValues {
  return Object.fromEntries(
    Object.entries(values).map(([documentType, zones]) => [
      documentType,
      { ...zones },
    ]),
  );
}

function valuesFromTemplates(templates: ReviewTemplate[]): ZoneValues {
  return Object.fromEntries(
    templates.map((template) => [
      template.document_type,
      Object.fromEntries(template.zones.map((zone) => [zone.id, zone.source_text || ""])),
    ]),
  );
}

function pdfObjectUrl(contentBase64: string) {
  const binary = atob(contentBase64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
}

function draftSuggestions(fragments: DraftFragment[]): Record<string, Record<string, string>> {
  const cvSummary = fragments.find((fragment) => fragment.kind === "cv_summary")?.text?.trim();
  const opening = fragments.find((fragment) => fragment.kind === "letter_opening")?.text?.trim();
  const fits = fragments.filter((fragment) => fragment.kind === "letter_fit" && fragment.text?.trim());
  const closing = fragments.find((fragment) => fragment.kind === "letter_closing")?.text?.trim();

  const cv: Record<string, string> = {};
  const letter: Record<string, string> = {};

  if (cvSummary) cv["p1.short_profile"] = cvSummary;
  if (opening) letter["body.paragraph_1"] = opening;
  fits.slice(0, 4).forEach((fragment, index) => {
    if (fragment.text) letter[`body.paragraph_${index + 2}`] = fragment.text.trim();
  });
  if (closing) letter["body.paragraph_6"] = closing;

  return {
    base_cv: cv,
    base_application_letter: letter,
  };
}

function label(documentType: string) {
  return documentType === "base_cv" ? "CV" : "Application letter";
}

export default function F6TemplateReviewEditor({
  silverJobId,
  sourceManifestSha256,
  fragments,
}: {
  silverJobId: number;
  sourceManifestSha256: string;
  fragments: DraftFragment[];
}) {
  const [review, setReview] = useState<ReviewPayload | null>(null);
  const [baseline, setBaseline] = useState<ZoneValues>({});
  const [values, setValues] = useState<ZoneValues>({});
  const [loading, setLoading] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [suggestionsApplied, setSuggestionsApplied] = useState(false);
  const [exports, setExports] = useState<LocalExport[]>([]);
  const [error, setError] = useState<string | null>(null);

  const templates = useMemo(
    () => Array.isArray(review?.templates) ? review.templates : [],
    [review?.templates],
  );

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    readJson<ReviewPayload>("/api/v1/product-v1/f6-template-review")
      .then((payload) => {
        if (!active) return;
        const loaded = Array.isArray(payload.templates) ? payload.templates : [];
        const initial = valuesFromTemplates(loaded);
        setReview(payload);
        setBaseline(initial);
        setValues(initial);
        setSuggestionsApplied(false);
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : String(reason));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [silverJobId, sourceManifestSha256]);

  useEffect(() => () => {
    exports.forEach((item) => URL.revokeObjectURL(item.objectUrl));
  }, [exports]);

  const applySuggestions = () => {
    const next = cloneValues(baseline);
    const suggestions = draftSuggestions(fragments);
    Object.entries(suggestions).forEach(([documentType, zones]) => {
      if (!next[documentType]) return;
      Object.entries(zones).forEach(([zoneId, text]) => {
        if (zoneId in next[documentType]) next[documentType][zoneId] = text;
      });
    });
    setValues(next);
    setSuggestionsApplied(true);
    setError(null);
    exports.forEach((item) => URL.revokeObjectURL(item.objectUrl));
    setExports([]);
  };

  const updateZone = (documentType: string, zoneId: string, text: string) => {
    setValues((current) => ({
      ...current,
      [documentType]: {
        ...(current[documentType] || {}),
        [zoneId]: text,
      },
    }));
    exports.forEach((item) => URL.revokeObjectURL(item.objectUrl));
    setExports([]);
  };

  const changedReplacements = () => Object.fromEntries(
    templates.map((template) => {
      const documentType = template.document_type;
      const current = values[documentType] || {};
      const source = baseline[documentType] || {};
      const changed = Object.fromEntries(
        template.zones
          .filter((zone) => (current[zone.id] ?? "") !== (source[zone.id] ?? ""))
          .map((zone) => [zone.id, current[zone.id] ?? ""]),
      );
      return [documentType, changed];
    }),
  );

  const renderLocalPdfs = async () => {
    setRendering(true);
    setError(null);
    exports.forEach((item) => URL.revokeObjectURL(item.objectUrl));
    setExports([]);
    try {
      const payload = await readJson<ExportPayload>("/api/v1/product-v1/f6-template-export", {
        method: "POST",
        body: JSON.stringify({
          action: "render_f6_review_package",
          silver_job_id: silverJobId,
          source_manifest_sha256: sourceManifestSha256,
          documents: changedReplacements(),
        }),
      });
      const localExports = (payload.documents || []).map((document) => ({
        ...document,
        objectUrl: pdfObjectUrl(document.pdf_base64),
      }));
      setExports(localExports);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setRendering(false);
    }
  };

  return <section className="f6-review-editor">
    <header className="f6-review-head">
      <div>
        <span>F6-C · exact-template review</span>
        <h4>Review and edit permitted PDF text zones</h4>
        <p>Only manifest-declared zones are editable. Rendering fails closed on overflow or any pixel change outside those zones.</p>
      </div>
      <b>HUMAN REVIEW REQUIRED</b>
    </header>

    {loading && <div className="f6-review-loading">Loading the two exact local templates…</div>}
    {error && <div className="f6-review-error"><strong>Export blocked</strong><span>{error}</span></div>}

    {!loading && templates.length === 2 && <>
      <div className="f6-review-actions">
        <button type="button" onClick={applySuggestions}>
          {suggestionsApplied ? "Reset and re-apply draft suggestions" : "Apply draft suggestions to zones"}
        </button>
        <small>CV summary → short profile. Letter opening/fit/closing → body zones. All other template text stays unchanged unless you edit it explicitly.</small>
      </div>

      <div className="f6-review-documents">
        {templates.map((template) => <article key={template.document_type}>
          <header>
            <div><span>{label(template.document_type)}</span><b>{template.canonical_filename}</b></div>
            <code>{template.source_sha256.slice(0, 12)}… · {template.page_count} page{template.page_count === 1 ? "" : "s"}</code>
          </header>
          <div className="f6-zone-list">
            {template.zones.map((zone) => <label key={zone.id}>
              <span><b>{zone.id}</b><small>page {zone.page}</small></span>
              <textarea
                value={values[template.document_type]?.[zone.id] ?? ""}
                onChange={(event) => updateZone(template.document_type, zone.id, event.target.value)}
                rows={Math.max(2, Math.min(6, (values[template.document_type]?.[zone.id] || "").split("\n").length + 1))}
              />
            </label>)}
          </div>
        </article>)}
      </div>

      <div className="f6-render-panel">
        <div>
          <strong>Local PDF export</strong>
          <p>The loopback runtime renders the exact private templates. No DB write, provider call, application action, submission, or send occurs.</p>
        </div>
        <button type="button" disabled={rendering} onClick={() => void renderLocalPdfs()}>
          {rendering ? "Rendering and verifying pixels…" : "Render local PDFs"}
        </button>
      </div>

      {exports.length > 0 && <div className="f6-export-results">
        {exports.map((item) => <article key={item.document_type}>
          <div>
            <span>{label(item.document_type)}</span>
            <b>{item.render_evidence.outside_zone_pixel_identity ? "Outside-zone identity PASS" : "Verification unavailable"}</b>
            <small>output {item.render_evidence.output_sha256?.slice(0, 12) || "—"}… · {(item.render_evidence.applied_zone_ids || []).length} edited zone(s)</small>
          </div>
          <nav>
            <a href={item.objectUrl} target="_blank" rel="noreferrer">Open PDF</a>
            <a href={item.objectUrl} download={item.download_filename}>Download PDF</a>
          </nav>
        </article>)}
        <p>No automatic submit/send authority is created by these files. Review the PDFs before using them outside JAP.</p>
      </div>}
    </>}
  </section>;
}
