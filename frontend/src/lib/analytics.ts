"use client";

import { useEffect, useState } from "react";
import type {
  AssuranceSummary,
  ConsistencySummary,
  SilentRemovalItem,
} from "./api";

export const components = [
  {
    key: "completeness_pct",
    label: "Completeness",
    weight: 0.4,
    color: "#087f72",
  },
  {
    key: "specificity_pct",
    label: "Specificity",
    weight: 0.3,
    color: "#3d789e",
  },
  { key: "clarity_pct", label: "Clarity", weight: 0.2, color: "#9c7930" },
  {
    key: "sdg_alignment_pct",
    label: "SDG breadth",
    weight: 0.1,
    color: "#8c969d",
  },
] as const;
export type ScoreKey = (typeof components)[number]["key"];
export interface Score {
  completeness_pct: number;
  specificity_pct: number;
  clarity_pct: number;
  sdg_alignment_pct: number;
  transparency_score: number;
}
export interface ResearchCompany extends Score {
  id: number;
  cin: string;
  name: string;
  sector: string;
  nic_code: string | null;
  filing_id: number;
  financial_year_end: string;
  raw_fact_count: number;
  report_count: number;
  score_source: string;
}
export type CompanyRecord = Omit<ResearchCompany, keyof Score> & {
  [K in keyof Score]: number | null;
};
export interface HistoryRow extends Score {
  id: number;
  cin: string;
  name: string;
  sector: string;
  filing_id: number;
  financial_year_end: string;
  financial_year: string;
}
export interface Analytics {
  companies: CompanyRecord[];
  history: HistoryRow[];
  report_count: number;
  fact_count: number;
  score_updated_at: string | null;
  methodology: string;
}
export interface FiledFact {
  id: number;
  concept: string;
  value: string;
  unit: string | null;
  period_start: string | null;
  period_end: string | null;
  dimensions: Record<string, string>;
}
export interface MetricSeries {
  concept: string;
  label: string;
  unit: string | null;
  dimensions: Record<string, string>;
  series: { period: string; value: number; fact_ids: number[] }[];
  yoy_change_pct: number | null;
  conflicting_periods: string[];
}
export interface EvidenceSignal {
  concept: string;
  severity: string;
  matched_sentence: string;
  rationale: string;
  assurance_level: string | null;
  sources: FiledFact[];
  numeric_evidence: FiledFact[];
}
export interface Workspace {
  company: {
    id: number;
    name: string;
    cin: string;
    sector: string;
    nic_code: string | null;
  };
  filing: {
    id: number;
    financial_year_start: string;
    financial_year_end: string;
    raw_fact_count: number;
    source_url: string;
  };
  filings: { id: number; financial_year_end: string }[];
  score: Score | null;
  score_source: string;
  scoring_error?: string | null;
  score_evidence: {
    accepted_concepts: number;
    universe_size: number;
    narrative_segments: number;
    kpi_segments: number;
    sdgs_covered: number[];
    principles_disclosed: number[];
  };
  metrics: MetricSeries[];
  signals: EvidenceSignal[];
  lexical_flags: FiledFact[];
  assurance_gaps: {
    concept: string;
    rationale: string;
    severity: string;
    source: FiledFact;
  }[];
  silent_removals: SilentRemovalItem[];
  assurance: AssuranceSummary;
  consistency: ConsistencySummary;
  facts: FiledFact[];
}

const base = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";
const cache = new Map<string, { time: number; promise: Promise<unknown> }>();
export async function researchGet<T>(
  path: string,
  refresh = false,
): Promise<T> {
  let entry = cache.get(path);
  if (refresh || !entry || Date.now() - entry.time > 60_000) {
    for (const [key, value] of cache) {
      if (Date.now() - value.time > 60_000) cache.delete(key);
    }
    if (cache.size >= 24) cache.delete(cache.keys().next().value!);
    const promise = fetch(`${base}${path}`, {
      signal: AbortSignal.timeout(90_000),
    })
      .then(async (r) => {
        if (!r.ok) {
          const body = await r.json().catch(() => ({}));
          throw new Error(body.detail || `Request failed (${r.status})`);
        }
        return r.json();
      })
      .catch((error) => {
        cache.delete(path);
        throw error;
      });
    entry = { time: Date.now(), promise };
    cache.set(path, entry);
  }
  return entry.promise as Promise<T>;
}
export function useResearch<T>(path: string) {
  const [state, setState] = useState<{
    path: string;
    data?: T;
    error?: string;
  }>({ path });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    researchGet<T>(path, attempt > 0)
      .then((data) => {
        if (active) setState({ path, data });
      })
      .catch((error) => {
        if (active) setState({ path, error: error.message });
      });
    return () => {
      active = false;
    };
  }, [path, attempt]);
  return {
    data: state.path === path ? state.data : undefined,
    error: state.path === path ? state.error : undefined,
    retry: () => {
      setState({ path });
      setAttempt((n) => n + 1);
    },
  };
}
export const fmt = (n: number | null | undefined, digits = 2) =>
  n == null || !Number.isFinite(n)
    ? "—"
    : n.toLocaleString("en-IN", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      });
export const signed = (n: number) => `${n > 0 ? "+" : ""}${fmt(n)}`;
export const fy = (date?: string | null) =>
  date
    ? `FY ${Number(date.slice(0, 4)) - 1}–${date.slice(2, 4)}`
    : "Period unavailable";
export const label = (concept: string) =>
  concept
    .replace(/ExplanatoryTextBlock$/, "")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/([A-Z])([A-Z][a-z])/g, "$1 $2");
export const short = (name: string, length = 26) =>
  name.length > length ? `${name.slice(0, length - 1)}…` : name;
export const mean = (ns: number[]) =>
  ns.length ? ns.reduce((a, b) => a + b, 0) / ns.length : 0;
type NullableScore = { [K in keyof Score]: number | null };
export const scored = <T extends NullableScore>(rows: T[]): (T & Score)[] =>
  rows.filter(
    (r): r is T & Score =>
      r.transparency_score != null &&
      Number.isFinite(r.transparency_score) &&
      components.every((c) => r[c.key] != null && Number.isFinite(r[c.key])),
  );
export function stats(rows: NullableScore[]) {
  const values = scored(rows)
    .map((r) => r.transparency_score)
    .sort((a, b) => a - b);
  const average = mean(values),
    mid = Math.floor(values.length / 2);
  return {
    n: values.length,
    mean: average,
    median: values.length
      ? values.length % 2
        ? values[mid]
        : (values[mid - 1] + values[mid]) / 2
      : 0,
    min: values[0] ?? 0,
    max: values.at(-1) ?? 0,
    sd:
      values.length > 1
        ? Math.sqrt(
            values.reduce((sum, v) => sum + (v - average) ** 2, 0) /
              (values.length - 1),
          )
        : 0,
  };
}
export function exportCsv(filename: string, rows: object[]) {
  if (!rows.length) return;
  const keys = Object.keys(rows[0]);
  const escape = (value: unknown) => {
    let s = String(value ?? "");
    if (/^[=+@\-\t\r]/.test(s)) s = `'${s}`;
    return `"${s.replaceAll('"', '""')}"`;
  };
  const text = [
    keys.map(escape).join(","),
    ...rows.map((row) =>
      keys.map((k) => escape((row as Record<string, unknown>)[k])).join(","),
    ),
  ].join("\r\n");
  const url = URL.createObjectURL(
    new Blob(["\uFEFF", text], { type: "text/csv;charset=utf-8" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
