/**
 * Typed API client — mirrors src/api/schemas.py exactly. Keeping these
 * types hand-aligned with the backend Pydantic models (rather than
 * generating them) is a deliberate short-term tradeoff for this project's
 * timeline; if the backend schema changes, this file must be updated
 * alongside it.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export interface CompanySummary {
  id: number;
  cin: string;
  name: string;
  nic_code: string | null;
}

export interface FilingSummary {
  id: number;
  financial_year_start: string;
  financial_year_end: string;
  raw_fact_count: number;
}

export interface TrendPoint {
  period: string;
  value: number;
}

export interface MetricTrend {
  concept: string;
  series: TrendPoint[];
  latest_value: number | null;
  previous_value: number | null;
  yoy_change_pct: number | null;
  direction: "increased" | "decreased" | "flat" | "insufficient_data";
}

export interface ConsistencyCheckItem {
  concept: string;
  context: string;
  status: string;
  message: string;
}

export interface ConsistencySummary {
  total_checks: number;
  passed: number;
  failed: number;
  skipped: number;
  failures: ConsistencyCheckItem[];
}

export interface AssuranceSummary {
  total_disclosure_areas: number;
  assured_count: number;
  reasonable_count: number;
  limited_count: number;
  unassured_count: number;
  reasonable_assurance_pct: number;
  low_assurance_areas: string[];
}

export interface GreenwashingSignalItem {
  concept: string;
  severity: "info" | "worth_reviewing" | "notable";
  matched_sentence: string;
  previous_value: number | null;
  latest_value: number | null;
  yoy_change_pct: number | null;
  assurance_level: string | null;
  rationale: string;
}

export interface SilentRemovalItem {
  concept: string;
  context: string;
  prior_year_value: string;
  prior_year_period: string;
  rationale: string;
}

export interface CompanyFullReport {
  company: CompanySummary;
  filing: FilingSummary;
  key_trends: MetricTrend[];
  consistency: ConsistencySummary;
  assurance: AssuranceSummary;
  greenwashing_signals: GreenwashingSignalItem[];
  silent_removals: SilentRemovalItem[];
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(
      res.status,
      body.detail ?? `Request failed: ${res.status}`,
    );
  }
  return res.json();
}

export const api = {
  listCompanies: () => apiGet<CompanySummary[]>("/companies"),
  getReport: (name: string) =>
    apiGet<CompanyFullReport>(`/companies/${encodeURIComponent(name)}/report`),
  listFilings: (name: string) =>
    apiGet<FilingSummary[]>(`/companies/${encodeURIComponent(name)}/filings`),
  getTransparencyScore: (name: string) =>
    apiGet<TransparencyScoreBreakdown>(
      `/companies/${encodeURIComponent(name)}/transparency-score`,
    ),
  getTruthAudit: (name: string) =>
    apiGet<TruthAuditorSummary>(
      `/companies/${encodeURIComponent(name)}/truth-audit`,
    ),
  getSectorBenchmark: (name: string) =>
    apiGet<SectorBenchmarkInfo>(
      `/companies/${encodeURIComponent(name)}/sector-benchmark`,
    ),
  uploadAndAnalyze: async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_BASE}/companies/upload-and-analyze`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ApiError(
        res.status,
        body.detail ?? `Request failed: ${res.status}`,
      );
    }
    return res.json() as Promise<CompanyFullReport>;
  },
  compareCompanies: (names: string[]) => {
    const query = new URLSearchParams();
    query.append("names", names.join(","));
    return apiGet<ComparisonResponse>(`/companies/compare?${query.toString()}`);
  }
};

export interface TransparencyScoreBreakdown {
  completeness_pct: number;
  specificity_pct: number;
  clarity_pct: number;
  sdg_alignment_pct: number;
  composite_score: number;
}

export interface TruthAuditorSummary {
  total_narrative_segments_checked: number;
  claim_evidence_contradictions_count: number;
  silent_removals_count: number;
  vague_segments_count: number;
  has_high_confidence_contradiction: boolean;
  claim_evidence_details: GreenwashingSignalItem[];
  silent_removal_details: SilentRemovalItem[];
}

export interface SectorBenchmarkInfo {
  sector: string;
  company_transparency_score: number;
  sector_mean: number;
  sector_median: number;
  percentile_rank: number;
  sector_peer_count: number;
  is_sector_leader: boolean;
  is_sector_laggard: boolean;
  benchmark_reliable: boolean;
}

export interface CompareCompanyResult {
  company_name: string;
  cin?: string;
  error?: string;
  transparency_score?: number;
  completeness_pct?: number;
  specificity_pct?: number;
  clarity_pct?: number;
  sdg_alignment_pct?: number;
  claim_evidence_contradictions?: number;
  silent_removals?: number;
  trends?: Record<string, { latest_value: number | null; yoy_change_pct: number | null; direction: string }>;
}

export interface ComparisonResponse {
  companies: CompareCompanyResult[];
}

