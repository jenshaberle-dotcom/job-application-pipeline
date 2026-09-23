import { useState } from "react";

type DocumentType = "base_cv" | "base_application_letter";

type UploadResult = {
  status?: string;
  reason?: string;
  template_id?: string;
  canonical_filename?: string;
  filename?: string;
  content_sha256?: string;
  byte_count?: number;
  extracted_text_char_count?: number;
  analysis?: {
    mode?: string;
    extractable_text?: boolean;
    provider_or_llm_requests?: number;
  };
};

function bytesToBase64(buffer: ArrayBuffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  const chunk = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunk) {
    binary += String.fromCharCode(...bytes.subarray(offset, Math.min(offset + chunk, bytes.length)));
  }
  return btoa(binary);
}

export default function ApplicationSourceUpload({
  documentType,
  title,
  ready,
  canonicalFilename,
  canonicalSha256,
  onUploaded,
}: {
  documentType: DocumentType;
  title: string;
  ready: boolean;
  canonicalFilename: string;
  canonicalSha256: string;
  onUploaded: () => Promise<void>;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const upload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const contentBase64 = bytesToBase64(await file.arrayBuffer());
      const response = await fetch("/api/v1/product-v1/application-source-upload", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          action: "install_f6_authority_template",
          document_type: documentType,
          filename: file.name,
          content_base64: contentBase64,
        }),
      });
      const payload = await response.json() as UploadResult;
      if (!response.ok || payload.status !== "approved") {
        throw new Error(payload.reason || `Upload failed with ${response.status}`);
      }
      setResult(payload);
      setFile(null);
      await onUploaded();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setUploading(false);
    }
  };

  return <section className={`ow-document-intake ${ready ? "ready" : "required"}`}>
    <header>
      <div><span>{title}</span><b>{ready ? "Exact F6 authority installed" : "Exact template required"}</b></div>
      <i>{ready ? "✓" : "PDF"}</i>
    </header>
    <p>{ready
      ? "The installed private PDF matches the frozen F6 binary hash and page geometry. Other layouts have no authority."
      : "Select the exact frozen PDF. Any other file, even a visually similar revision, is rejected before approval."}</p>
    <div className="ow-template-identity">
      <span>{canonicalFilename}</span>
      <code>sha256 {canonicalSha256.slice(0, 16)}…</code>
    </div>
    <div className="ow-upload-row">
      <label className="ow-file-picker">
        <input
          type="file"
          accept="application/pdf,.pdf"
          onChange={(event) => setFile(event.target.files?.[0] || null)}
        />
        <span>{file ? file.name : ready ? "Re-verify exact PDF…" : "Choose exact PDF…"}</span>
      </label>
      <button type="button" className="ow-primary" disabled={!file || uploading} onClick={() => void upload()}>
        {uploading ? "Verifying F6 authority…" : `Verify ${title}`}
      </button>
    </div>
    <small className="ow-private-note">Private bytes stay local · exact SHA-256 + page geometry required · no alternate template accepted.</small>
    {result && <div className="ow-upload-result"><b>Authority verified</b><span>{result.canonical_filename || result.filename} · {result.extracted_text_char_count ?? 0} extractable characters · hash {result.content_sha256?.slice(0, 12)}…</span></div>}
    {error && <div className="ow-upload-error"><b>Rejected by F6 authority</b><span>{error}</span></div>}
  </section>;
}
