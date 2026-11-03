"use client";
import Link from "next/link";
import { Download, RefreshCw, ArrowUpRight, AlertCircle } from "lucide-react";
import {
  components,
  fmt,
  fy,
  stats,
  exportCsv,
  type Score,
  type CompanyRecord,
} from "@/lib/analytics";
import type { ReactNode } from "react";

export function PageHead({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-head">
      <div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </header>
  );
}
export function Panel({
  title,
  note,
  children,
  className = "",
  action,
}: {
  title: string;
  note?: string;
  children: ReactNode;
  className?: string;
  action?: ReactNode;
}) {
  return (
    <section className={`analysis-panel ${className}`}>
      <div className="panel-head">
        <div>
          <h2>{title}</h2>
          {note && <p>{note}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty-state">{children}</div>;
}
export function ErrorState({
  message,
  retry,
}: {
  message: string;
  retry: () => void;
}) {
  return (
    <div className="error-state" role="alert">
      <AlertCircle size={18} />
      <div>
        <strong>Unable to load this analysis</strong>
        <p>{message}</p>
      </div>
      <button className="btn" onClick={retry}>
        <RefreshCw size={14} />
        Retry
      </button>
    </div>
  );
}
export function Skeleton({ detail = false }: { detail?: boolean }) {
  return (
    <div
      className="workspace-loading"
      role="status"
      aria-label="Loading analysis"
      aria-busy="true"
    >
      <div className="skeleton w-64 h-7" />
      <div className="skeleton w-96 h-4 mt-3" />
      <div className="skeleton h-14 mt-7" />
      <div className="metric-strip mt-5">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i}>
            <div className="skeleton h-3 w-24" />
            <div className="skeleton h-8 w-20 mt-3" />
          </div>
        ))}
      </div>
      <div className="analysis-grid mt-5">
        {Array.from({ length: detail ? 2 : 4 }, (_, i) => (
          <div key={i} className="analysis-panel">
            <div className="skeleton h-4 w-44" />
            <div className="skeleton h-52 mt-5" />
          </div>
        ))}
      </div>
      <span className="sr-only">Loading research data</span>
    </div>
  );
}
export function StatStrip({
  rows,
  extra,
}: {
  rows: Score[];
  extra?: { label: string; value: string; note: string };
}) {
  const s = stats(rows);
  return (
    <div className="metric-strip">
      {[
        {
          label: "Companies scored",
          value: fmt(s.n, 0),
          note: "One observation per CIN",
        },
        {
          label: "Mean transparency",
          value: fmt(s.mean),
          note: "Score out of 100",
        },
        {
          label: "Median transparency",
          value: fmt(s.median),
          note: `Range ${fmt(s.min)}–${fmt(s.max)}`,
        },
        extra ?? {
          label: "Standard deviation",
          value: fmt(s.sd),
          note: "Sample SD, score points",
        },
      ].map((x) => (
        <div key={x.label}>
          <span>{x.label}</span>
          <strong>{x.value}</strong>
          <small>{x.note}</small>
        </div>
      ))}
    </div>
  );
}
export function ExportButton({
  rows,
  filename = "brsr-comparison.csv",
}: {
  rows: object[];
  filename?: string;
}) {
  return (
    <button
      className="btn"
      disabled={!rows.length}
      onClick={() => exportCsv(filename, rows)}
    >
      <Download size={14} />
      Export CSV
    </button>
  );
}
export function ScoreTable({
  rows,
  selectable,
  selected = [],
  onSelect,
}: {
  rows: CompanyRecord[];
  selectable?: boolean;
  selected?: string[];
  onSelect?: (cin: string) => void;
}) {
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            {selectable && <th className="check-cell">Pick</th>}
            <th>Company / sector</th>
            <th>Report period</th>
            {components.map((c) => (
              <th key={c.key} className="num">
                {c.label} %
              </th>
            ))}
            <th className="num">TS / 100</th>
            <th aria-label="Open report" />
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.cin} data-selected={selected.includes(r.cin)}>
              {selectable && (
                <td className="check-cell">
                  <input
                    aria-label={`Select ${r.name}`}
                    type="checkbox"
                    disabled={
                      r.transparency_score == null ||
                      (selected.length >= 8 && !selected.includes(r.cin))
                    }
                    title={
                      r.transparency_score == null
                        ? "No saved comparison score yet"
                        : undefined
                    }
                    checked={selected.includes(r.cin)}
                    onChange={() => onSelect?.(r.cin)}
                  />
                </td>
              )}
              <td>
                <Link
                  className="company-link"
                  prefetch={false}
                  href={`/company/${encodeURIComponent(r.name)}`}
                >
                  {r.name}
                </Link>
                <small>{r.sector}</small>
              </td>
              <td className="nowrap">
                {fy(r.financial_year_end)}
                <small>Report #{r.filing_id}</small>
              </td>
              {components.map((c) => (
                <td key={c.key} className="num">
                  {fmt(r[c.key])}
                </td>
              ))}
              <td className="num score-cell">
                {r.transparency_score == null ? (
                  <span className="tag tag-neutral">Not scored</span>
                ) : (
                  fmt(r.transparency_score)
                )}
              </td>
              <td>
                <Link
                  aria-label={`Open ${r.name}`}
                  prefetch={false}
                  href={`/company/${encodeURIComponent(r.name)}`}
                >
                  <ArrowUpRight size={15} />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && <Empty>No companies match these filters.</Empty>}
    </div>
  );
}
