"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import {
  components,
  useResearch,
  fmt,
  signed,
  fy,
  mean,
  short,
  type Analytics,
  type ScoreKey,
} from "@/lib/analytics";
import {
  PageHead,
  Panel,
  Skeleton,
  ErrorState,
  ExportButton,
  Empty,
} from "./Shared";

export function TimeSeriesWorkspace() {
  const { data, error, retry } = useResearch<Analytics>("/analytics/overview");
  const [sector, setSector] = useState("all"),
    [company, setCompany] = useState(""),
    [metric, setMetric] = useState<ScoreKey | "transparency_score">(
      "transparency_score",
    );
  const pairs = useMemo(() => {
    const groups = new Map<string, NonNullable<typeof data>["history"]>();
    for (const row of data?.history ?? [])
      groups.set(row.cin, [...(groups.get(row.cin) ?? []), row]);
    return [...groups]
      .map(([cin, history]) => {
        history.sort((a, b) =>
          a.financial_year_end.localeCompare(b.financial_year_end),
        );
        return {
          cin,
          history,
          first: history[0],
          last: history[history.length - 1],
        };
      })
      .filter(
        (p) =>
          p.history.length > 1 &&
          (sector === "all" || p.first.sector === sector),
      )
      .sort(
        (a, b) =>
          b.last.transparency_score -
          b.first.transparency_score -
          (a.last.transparency_score - a.first.transparency_score),
      );
  }, [data, sector]);
  const selected = pairs.find((p) => p.cin === company) ?? pairs[0];
  if (error) return <ErrorState message={error} retry={retry} />;
  if (!data) return <Skeleton />;
  const sectors = [...new Set(data.history.map((r) => r.sector))].sort();
  const from = mean(pairs.map((p) => p.first.transparency_score)),
    to = mean(pairs.map((p) => p.last.transparency_score));
  return (
    <div className="workspace-page">
      <PageHead
        title="Time series"
        description="Compare the same companies over time and trace each score change to its components."
        action={
          <ExportButton
            rows={pairs.flatMap((p) => p.history)}
            filename="brsr-paired-reports.csv"
          />
        }
      />
      <div className="filter-bar">
        <label>
          Sector
          <select value={sector} onChange={(e) => setSector(e.target.value)}>
            <option value="all">All paired sectors</option>
            {sectors.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <label>
          Company to investigate
          <select
            value={selected?.cin ?? ""}
            onChange={(e) => setCompany(e.target.value)}
          >
            {pairs.map((p) => (
              <option key={p.cin} value={p.cin}>
                {p.first.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Measure
          <select
            value={metric}
            onChange={(e) => setMetric(e.target.value as typeof metric)}
          >
            <option value="transparency_score">Transparency score</option>
            {components.map((c) => (
              <option key={c.key} value={c.key}>
                {c.label} %
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="scope-note">
        <span>Available-case analysis</span>
        {pairs.length} companies have multiple scored reports in this view. This
        is a paired sample, not a market-wide trend. Values are observed,
        without interpolation or forecasts.
      </div>
      <div className="metric-strip">
        {[
          {
            label: "Paired companies",
            value: fmt(pairs.length, 0),
            note: `${pairs.flatMap((p) => p.history).length} scored reports`,
          },
          {
            label: "Mean earlier score",
            value: fmt(from),
            note: pairs.length
              ? fy(pairs[0].first.financial_year_end)
              : "No pairs",
          },
          {
            label: "Mean later score",
            value: fmt(to),
            note: pairs.length
              ? fy(pairs[0].last.financial_year_end)
              : "No pairs",
          },
          {
            label: "Mean change",
            value: signed(to - from),
            note: `${pairs.filter((p) => p.last.transparency_score > p.first.transparency_score).length} increased · ${pairs.filter((p) => p.last.transparency_score < p.first.transparency_score).length} decreased`,
          },
        ].map((s) => (
          <div key={s.label}>
            <span>{s.label}</span>
            <strong>{s.value}</strong>
            <small>{s.note}</small>
          </div>
        ))}
      </div>
      {!selected ? (
        <Empty>No paired reports are available for this sector.</Empty>
      ) : (
        <>
          <div className="analysis-grid">
            <Panel
              title="Observed report trajectory"
              note={`${selected.first.name} · ${metric === "transparency_score" ? "TS / 100" : components.find((c) => c.key === metric)?.label + " %"}`}
            >
              <svg
                viewBox="0 0 600 290"
                role="img"
                aria-label="Selected company's observed score history"
                className="analysis-chart"
              >
                {[0, 25, 50, 75, 100].map((v) => (
                  <g key={v}>
                    <line
                      x1="58"
                      x2="550"
                      y1={232 - v * 1.9}
                      y2={232 - v * 1.9}
                      stroke="#e6ecee"
                    />
                    <text x="43" y={236 - v * 1.9} textAnchor="end">
                      {v}
                    </text>
                  </g>
                ))}
                <polyline
                  fill="none"
                  stroke="#087f72"
                  strokeWidth="2.5"
                  points={selected.history
                    .map(
                      (r, i) =>
                        `${90 + (i / (selected.history.length - 1)) * 410},${232 - r[metric] * 1.9}`,
                    )
                    .join(" ")}
                />
                {selected.history.map((r, i) => (
                  <g key={r.filing_id}>
                    <circle
                      cx={90 + (i / (selected.history.length - 1)) * 410}
                      cy={232 - r[metric] * 1.9}
                      r="5"
                      fill="#087f72"
                    />
                    <text
                      x={90 + (i / (selected.history.length - 1)) * 410}
                      y={220 - r[metric] * 1.9}
                      textAnchor="middle"
                      className="chart-value"
                    >
                      {fmt(r[metric])}
                    </text>
                    <text
                      x={90 + (i / (selected.history.length - 1)) * 410}
                      y="258"
                      textAnchor="middle"
                    >
                      {fy(r.financial_year_end)}
                    </text>
                    <text
                      x={90 + (i / (selected.history.length - 1)) * 410}
                      y="276"
                      textAnchor="middle"
                    >
                      Report #{r.filing_id}
                    </text>
                  </g>
                ))}
              </svg>
            </Panel>
            <Panel
              title="What drove the score change?"
              note="Signed change in component percentage × fixed weight = score-point contribution."
            >
              <div className="delta-components">
                {components.map((c) => {
                  const delta =
                    (selected.last[c.key] - selected.first[c.key]) * c.weight;
                  return (
                    <div key={c.key}>
                      <div>
                        <span>
                          <i style={{ background: c.color }} />
                          {c.label} × {c.weight}
                        </span>
                        <strong>{signed(delta)} pts</strong>
                      </div>
                      <div className="delta-track">
                        <span
                          style={{
                            left: `${50 + Math.min(delta, 0) * 2}%`,
                            width: `${Math.abs(delta) * 2}%`,
                            background: delta >= 0 ? "#087f72" : "#b47728",
                          }}
                        />
                      </div>
                      <small>
                        {fmt(selected.first[c.key])}% →{" "}
                        {fmt(selected.last[c.key])}%
                      </small>
                    </div>
                  );
                })}
              </div>
              <div className="calculation-total">
                Total score change
                <strong>
                  {signed(
                    selected.last.transparency_score -
                      selected.first.transparency_score,
                  )}{" "}
                  points
                </strong>
              </div>
              <p className="data-footnote">
                Contributions may differ by 0.01 due to rounding in saved
                component percentages.
              </p>
            </Panel>
            <Panel
              title="Which companies changed most?"
              note={`Paired ${metric === "transparency_score" ? "score" : components.find((c) => c.key === metric)?.label} changes; the same reporting entities at both endpoints.`}
            >
              <svg
                viewBox={`0 0 600 ${80 + pairs.length * 31}`}
                role="img"
                aria-label="Paired company score changes"
                className="analysis-chart"
              >
                <line
                  x1="382"
                  x2="382"
                  y1="10"
                  y2={20 + pairs.length * 31}
                  stroke="#a8b9be"
                />
                {pairs.map((p, i) => {
                  const d = p.last[metric] - p.first[metric];
                  const scale =
                    145 /
                    Math.max(
                      15,
                      ...pairs.map((x) =>
                        Math.abs(x.last[metric] - x.first[metric]),
                      ),
                    );
                  return (
                    <g
                      key={p.cin}
                      onClick={() => setCompany(p.cin)}
                      className="chart-clickable"
                    >
                      <text x="250" y={33 + i * 31} textAnchor="end">
                        <title>{p.first.name}</title>
                        {short(p.first.name, 35)}
                      </text>
                      <rect
                        x={382 + Math.min(d, 0) * scale}
                        y={20 + i * 31}
                        width={Math.abs(d) * scale}
                        height="18"
                        fill={d >= 0 ? "#087f72" : "#b47728"}
                      />
                      <text
                        x={d >= 0 ? 390 + d * scale : 374 + d * scale}
                        y={33 + i * 31}
                        textAnchor={d >= 0 ? "start" : "end"}
                      >
                        {signed(d)}
                      </text>
                    </g>
                  );
                })}
                <text x="382" y={55 + pairs.length * 31} textAnchor="middle">
                  Change in points; baseline = 0
                </text>
              </svg>
            </Panel>
            <Panel
              title="Open the underlying reports"
              note="The selected company’s report IDs and periods stay linked to the score observations."
            >
              <div className="report-links">
                {selected.history.map((r) => (
                  <Link
                    key={r.filing_id}
                    href={`/company/${encodeURIComponent(r.name)}?filing=${r.filing_id}`}
                  >
                    <span>
                      <strong>{fy(r.financial_year_end)}</strong>
                      <small>
                        Report #{r.filing_id} · {r.financial_year_end}
                      </small>
                    </span>
                    <span>
                      {fmt(r.transparency_score)}{" "}
                      <small>Transparency score</small>
                    </span>
                  </Link>
                ))}
              </div>
              <div className="scope-note">
                Environmental measures can have several periods within a single
                filing. Open a report’s “Metrics & history” tab for unit- and
                boundary-matched numeric series.
              </div>
            </Panel>
          </div>
          <Panel
            title="Paired report register"
            note="Every observed report, all component values and the stable CIN identifier."
          >
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Company</th>
                    <th>Report / period</th>
                    {components.map((c) => (
                      <th className="num" key={c.key}>
                        {c.label} %
                      </th>
                    ))}
                    <th className="num">TS / 100</th>
                  </tr>
                </thead>
                <tbody>
                  {pairs
                    .flatMap((p) => p.history)
                    .map((r) => (
                      <tr key={r.filing_id}>
                        <td>
                          <Link
                            className="company-link"
                            href={`/company/${encodeURIComponent(r.name)}?filing=${r.filing_id}`}
                          >
                            {r.name}
                          </Link>
                          <small>{r.cin}</small>
                        </td>
                        <td>
                          {fy(r.financial_year_end)}
                          <small>#{r.filing_id}</small>
                        </td>
                        {components.map((c) => (
                          <td className="num" key={c.key}>
                            {fmt(r[c.key])}
                          </td>
                        ))}
                        <td className="num score-cell">
                          {fmt(r.transparency_score)}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </>
      )}
    </div>
  );
}
