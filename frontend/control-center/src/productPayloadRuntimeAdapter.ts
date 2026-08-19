type JsonRecord = Record<string, unknown>;

const isRecord = (value: unknown): value is JsonRecord =>
  typeof value === "object" && value !== null && !Array.isArray(value);

function compactValue(value: unknown): string | null {
  if (value == null) return null;
  if (typeof value === "string") return value.trim() || null;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) {
    const items = value.map(compactValue).filter((item): item is string => Boolean(item));
    return items.length ? items.join(", ") : null;
  }
  if (isRecord(value)) return JSON.stringify(value);
  return String(value);
}

export function evidenceItemText(value: unknown): string {
  if (!isRecord(value)) return compactValue(value) || "Unspecified evidence";

  const factor = compactValue(value.factor);
  const status = compactValue(value.status);
  const evidence = compactValue(value.evidence);
  const action = compactValue(value.action);
  const observedAt = compactValue(value.observed_at_utc);

  const headline = [factor, status].filter(Boolean).join(" · ");
  const detail = [evidence, action, observedAt].filter(Boolean).join(" · ");
  if (headline && detail) return `${headline} — ${detail}`;
  if (headline) return headline;
  if (detail) return detail;
  return JSON.stringify(value);
}

function normalizeEvidence(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map(evidenceItemText);
}

export function structuredLocationText(value: unknown): string | null {
  if (!Array.isArray(value)) return null;

  const labels: string[] = [];
  for (const item of value) {
    if (!isRecord(item)) continue;
    const city = compactValue(item.city);
    if (!city) continue;
    const countryCode = compactValue(item.country_code);
    const display = countryCode ? `${city}, ${countryCode}` : city;
    if (!labels.includes(display)) labels.push(display);
  }
  return labels.length ? labels.join(" · ") : null;
}

function normalizeJobs(value: unknown): unknown {
  if (!Array.isArray(value)) return value;
  return value.map((job) => {
    if (!isRecord(job)) return job;
    const structuredLocation = structuredLocationText(job.structured_locations);
    return {
      ...job,
      city: structuredLocation || job.city,
      explanations: normalizeEvidence(job.explanations),
      uncertainties: normalizeEvidence(job.uncertainties),
    };
  });
}

export function normalizeProductV1Payload(value: unknown): unknown {
  if (!isRecord(value)) return value;
  return {
    ...value,
    job_readiness: normalizeJobs(value.job_readiness),
    top_jobs: normalizeJobs(value.top_jobs),
  };
}

function isProductV1Request(input: RequestInfo | URL): boolean {
  const rawUrl =
    typeof input === "string"
      ? input
      : input instanceof URL
        ? input.toString()
        : input.url;
  try {
    return new URL(rawUrl, window.location.href).pathname === "/api/v1/product-v1";
  } catch {
    return false;
  }
}

let installed = false;

export function installProductPayloadRuntimeAdapter(): void {
  if (installed) return;
  installed = true;

  const nativeFetch = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const response = await nativeFetch(input, init);
    if (!response.ok || !isProductV1Request(input)) return response;

    let rawPayload: unknown;
    try {
      rawPayload = await response.clone().json();
    } catch {
      return response;
    }

    const headers = new Headers(response.headers);
    headers.delete("content-length");
    return new Response(JSON.stringify(normalizeProductV1Payload(rawPayload)), {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
  };
}
