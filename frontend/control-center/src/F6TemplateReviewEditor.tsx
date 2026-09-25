import { useEffect, useMemo, useState } from "react";
import "./f6-template-review-editor.css";

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

type CombinedPackage = {
  download_filename: string;
  pdf_base64: string;
  sha256: string;
  page_count: number;
  component_order: string[];
  visual_identity: boolean;
};

type ExportPayload = {
  status?: string;
  reason?: string;
  package?: CombinedPackage;
  documents?: ExportDocument[];
  human_review_required?: boolean;
  submission_actions?: number;
  send_actions?: number;
};

type ZoneValues = Record<string, Record<string, string>>;

type LocalPackage = CombinedPackage & { objectUrl: string };

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

function applyDraftToBaseline(
  baseline: ZoneValues,
  replacements: ZoneValues,
): ZoneValues {
  const result: ZoneValues = Object.fromEntries(
    Object.entries(baseline).map(([documentType, zones]) => [
      documentType,
      { ...zones },
    ]),
  );
  Object.entries(replacements).forEach(([documentType, zones]) => {
    if (!result[documentType]) return;
    Object.entries(zones).forEach(([zoneId, text]) => {
      if (zoneId in result[documentType]) result[documentType][zoneId] = text;
    });
  });
  return result;
}

function label(documentType: string) {
  return documentType === "base_cv" ? "CV" : "Application letter";
}

export default function F6TemplateReviewEditor({
  silverJobId,
  sourceManifestSha256,
  zoneReplacements,
}: {
  silverJobId: number;
  sourceManifestSha256: string;
  zoneReplacements: ZoneValues;
}) {
  const [review, setReview] = useState<ReviewPayload | null>(null);
  const [baseline, setBaseline] = useState<ZoneValues>({});
  const [values, setValues] = useState<ZoneValues>({});
  const [loading, setLoading] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [packagePdf, setPackagePdf] = useState<LocalPackage | null>(null);
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
        setValues(applyDraftToBaseline(initial, zoneReplacements));
        setPackagePdf((current) => {
          if (current) URL.revokeObjectURL(current.objectUrl);
          return null;
        });
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : String(reason));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [silverJobId, sourceManifestSha256, zoneReplacements]);

  useEffect(() => () => {
    if (packagePdf) URL.revokeObjectURL(packagePdf.objectUrl);
  }, [packagePdf]);

  const updateZone = (documentType: string, zoneId: string, text: string) => {
    setError(null);
    setValues((current) => ({
      ...current,
      [documentType]: {
        ...(current[documentType] || {}),
        [zoneId]: text,
      },
    }));
    setPackagePdf((current) => {
      if (current) URL.revokeObjectURL(current.objectUrl);
      return null;
    });
  };

  const resetToGeneratedDraft = () => {
    setValues(applyDraftToBaseline(baseline, zoneReplacements));
    setError(null);
    setPackagePdf((current) => {
      if (current) URL.revokeObjectURL(current.objectUrl);
      return null;
    });
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

  const renderFinishedPdf = async () => {
    setRendering(true);
    setError(null);
    setPackagePdf((current) => {
      if (current) URL.revokeObjectURL(current.objectUrl);
      return null;
    });
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
      if (!payload.package?.pdf_base64) {
        throw new Error("Finished application PDF was not returned");
      }
      setPackagePdf({
        ...payload.package,
        objectUrl: pdfObjectUrl(payload.package.pdf_base64),
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setRendering(false);
    }
  };

  return <section className="f6-review-editor f6-finished-document">
    <header className="f6-review-head">
      <div>
        <span>F6-C · finished application</span>
        <h4>One finished PDF instead of zone-by-zone assembly</h4>
        <p>JAP maps the grounded draft into the approved CV and letter templates internally, verifies the protected pixels, then combines both into one local application PDF.</p>
      </div>
      <b>HUMAN REVIEW REQUIRED</b>
    </header>

    {loading && <div className="f6-review-loading">Preparing the exact local templates…</div>}
    {error && <div className="f6-review-error"><strong>PDF creation blocked</strong><span>{error}</span></div>}

    {!loading && templates.length === 2 && <>
      <div className="f6-finished-flow">
        <div className="f6-finished-copy">
          <strong>{error ? "Template text needs adjustment" : "Application PDF is ready to build"}</strong>
          <p>{error
            ? "The exact renderer rejected at least one text zone. Shorten the named zone in Advanced review or regenerate the review text before building again."
            : "The generated review text has already been mapped to the permitted template zones. You do not need to fill the individual fields manually."}</p>
          <div className="f6-finished-facts">
            <span><b>1</b> application letter</span>
            <span><b>2</b> CV pages</span>
            <span><b>0</b> automatic submissions</span>
          </div>
        </div>
        <button type="button" disabled={rendering || Boolean(error)} onClick={() => void renderFinishedPdf()}>
          {rendering ? "Building and verifying final PDF…" : "Create finished application PDF"}
        </button>
      </div>

      {packagePdf && <div className="f6-final-package">
        <div>
          <span>FINISHED LOCAL DOCUMENT</span>
          <h5>{packagePdf.download_filename}</h5>
          <p>{packagePdf.page_count} pages · letter + CV · {packagePdf.visual_identity ? "visual identity verified" : "verification unavailable"}</p>
          <code>{packagePdf.sha256.slice(0, 16)}…</code>
        </div>
        <nav>
          <a href={packagePdf.objectUrl} target="_blank" rel="noreferrer">Open final PDF</a>
          <a className="primary" href={packagePdf.objectUrl} download={packagePdf.download_filename}>Download final PDF</a>
        </nav>
      </div>}

      <details className="f6-advanced-review">
        <summary>Advanced: manual override (normally not required)</summary>
        <p>The normal path is exact-template preflighted and should need no zone-by-zone work. Use this only for an exceptional human correction after review.</p>
        <button type="button" className="f6-reset-draft" onClick={resetToGeneratedDraft}>Reset to generated draft</button>
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
      </details>

      <p className="f6-final-boundary">The final PDF is created locally. No DB write, provider call, application action, submission, or send occurs during rendering.</p>
    </>}
  </section>;
}
