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

function authoritativeRankableScore(job: JsonRecord): unknown {
  const readiness = String(job.product_readiness_status || "").trim().toLowerCase();
  if (readiness !== "rankable") return job.overall_quality_score;
  return typeof job.product_overall_quality_score === "number"
    ? job.product_overall_quality_score
    : job.overall_quality_score;
}

function normalizeJobs(value: unknown): JsonRecord[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((job) => {
    if (!isRecord(job)) return [];
    const structuredLocation = structuredLocationText(job.structured_locations);
    return [{
      ...job,
      city: structuredLocation || job.city,
      overall_quality_score: authoritativeRankableScore(job),
      explanations: normalizeEvidence(job.explanations),
      uncertainties: normalizeEvidence(job.uncertainties),
    }];
  });
}

function demoActionable(job: JsonRecord): boolean {
  return job.demo_actionable === true && typeof job.employer_origin_url === "string";
}

export function normalizeProductV1Payload(value: unknown): unknown {
  if (!isRecord(value)) return value;

  const allJobs = normalizeJobs(value.job_readiness);
  const allTopJobs = normalizeJobs(value.top_jobs);
  const actionableJobs = allJobs.filter(demoActionable);
  const actionableTopJobs = allTopJobs.filter(demoActionable);
  const actionableRankable = actionableJobs.filter(
    (job) => String(job.product_readiness_status || "").trim().toLowerCase() === "rankable",
  );
  const summary = isRecord(value.summary) ? { ...value.summary } : {};

  return {
    ...value,
    // Preserve historical/discovery truth separately. The daily review surface is
    // deliberately fail-closed to current validated Employer-Origin vacancies.
    discovery_job_readiness: allJobs,
    job_readiness: actionableJobs,
    top_jobs: actionableTopJobs,
    summary: {
      ...summary,
      demo_actionable_job_count: actionableJobs.length,
      review_scope_current_active_job_count: actionableJobs.length,
      rankable_job_count: actionableRankable.length,
      top_job_count: actionableTopJobs.length,
    },
  };
}

type ProductTruthReadOptions = {
  fresh?: boolean;
};

let cachedProductTruth: Promise<unknown> | null = null;

async function fetchProductTruth(): Promise<unknown> {
  const response = await window.fetch("/api/v1/product-v1", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`API returned ${response.status}`);

  const rawPayload = await response.json();
  return normalizeProductV1Payload(rawPayload);
}

export function readProductTruth<T>(
  options: ProductTruthReadOptions = {},
): Promise<T> {
  if (options.fresh || cachedProductTruth === null) {
    const request = fetchProductTruth().catch((error: unknown) => {
      if (cachedProductTruth === request) cachedProductTruth = null;
      throw error;
    });
    cachedProductTruth = request;
  }

  return cachedProductTruth as Promise<T>;
}

export function clearProductTruthCache(): void {
  cachedProductTruth = null;
}
