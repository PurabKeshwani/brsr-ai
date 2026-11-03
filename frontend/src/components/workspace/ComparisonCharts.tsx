"use client";
import { useMemo } from "react";
import {
  components,
  fmt,
  mean,
  short,
  stats,
  type ResearchCompany,
} from "@/lib/analytics";
import { Panel, Empty } from "./Shared";

const green = "#087f72",
  grey = "#dce4e7";
function Chart({
  name,
  children,
  height = 250,
}: {
  name: string;
  children: React.ReactNode;
  height?: number;
}) {
  return (
    <svg
      className="analysis-chart"
      viewBox={`0 0 600 ${height}`}
      role="img"
      aria-label={name}
    >
      {children}
    </svg>
  );
}
function Axis({
  max = 100,
  x = 190,
  width = 370,
  y = 20,
  height = 180,
}: {
  max?: number;
  x?: number;
  width?: number;
  y?: number;
  height?: number;
}) {
  return (
    <>
      {[0, 0.25, 0.5, 0.75, 1].map((r) => (
        <g key={r}>
          <line
            x1={x + r * width}
            x2={x + r * width}
            y1={y}
            y2={y + height}
            stroke="#e8edef"
          />
          <text x={x + r * width} y={y + height + 18} textAnchor="middle">
            {fmt(max * r, max < 10 ? 1 : 0)}
          </text>
        </g>
      ))}
    </>
  );
}
export default function ComparisonCharts({
  rows,
  population,
  sectorMode = false,
}: {
  rows: ResearchCompany[];
  population: ResearchCompany[];
  sectorMode?: boolean;
}) {
  const sorted = useMemo(
    () => [...rows].sort((a, b) => b.transparency_score - a.transparency_score),
    [rows],
  );
  const shown = sorted.slice(0, 8),
    average = mean(rows.map((r) => r.transparency_score));
  const bins = Array.from({ length: 10 }, (_, i) => ({
    label: `${i * 10}–${i === 9 ? 100 : i * 10 + 9.99}`,
    count: rows.filter(
      (r) =>
        r.transparency_score >= i * 10 &&
        (i === 9
          ? r.transparency_score <= 100
          : r.transparency_score < (i + 1) * 10),
    ).length,
  }));
  const maxBin = Math.max(
    4,
    Math.ceil(Math.max(0, ...bins.map((b) => b.count)) / 4) * 4,
  );
  const sectors = useMemo(() => {
    const groups = new Map<string, ResearchCompany[]>();
    for (const r of population)
      groups.set(r.sector, [...(groups.get(r.sector) ?? []), r]);
    return [...groups]
      .map(([sector, rs]) => ({ sector, ...stats(rs) }))
      .sort((a, b) => b.n - a.n)
      .slice(0, 10);
  }, [population]);
  if (!rows.length)
    return <Empty>Select companies or a sector to draw the comparison.</Empty>;
  return (
    <div className="analysis-grid">
      <Panel
        title="What builds each score?"
        note={`Weighted contributions in score points. ${rows.length > 8 ? `Highest 8 of ${rows.length} companies.` : "All selected companies."}`}
      >
        <div className="chart-legend">
          {components.map((c) => (
            <span key={c.key}>
              <i style={{ background: c.color }} />
              {c.label} × {c.weight}
            </span>
          ))}
        </div>
        <Chart name="Stacked score contributions by company" height={260}>
          <Axis height={190} />
          {shown.map((r, i) => {
            let start = 190;
            return (
              <g key={r.cin}>
                <text x="178" y={35 + i * 23} textAnchor="end">
                  <title>{r.name}</title>
                  {short(r.name, 25)}
                </text>
                {components.map((c) => {
                  const width = r[c.key] * c.weight * 3.7;
                  const x = start;
                  start += width;
                  return (
                    <rect
                      key={c.key}
                      x={x}
                      y={24 + i * 23}
                      width={width}
                      height="13"
                      fill={c.color}
                    >
                      <title>
                        {r.name}: {c.label} {fmt(r[c.key])}% × {c.weight} ={" "}
                        {fmt(r[c.key] * c.weight)} points
                      </title>
                    </rect>
                  );
                })}
                <text x={start + 6} y={35 + i * 23}>
                  {fmt(r.transparency_score)}
                </text>
              </g>
            );
          })}
        </Chart>
      </Panel>
      <Panel
        title="Where do scores concentrate?"
        note={`All ${rows.length} observations; fixed 10-point bins, including empty bands.`}
      >
        <Chart name="Transparency score histogram" height={285}>
          {[0, 0.25, 0.5, 0.75, 1].map((r) => (
            <g key={r}>
              <line
                x1="44"
                x2="576"
                y1={225 - r * 180}
                y2={225 - r * 180}
                stroke="#e8edef"
              />
              <text x="34" y={229 - r * 180} textAnchor="end">
                {fmt(Math.ceil(maxBin * r), 0)}
              </text>
            </g>
          ))}
          {bins.map((b, i) => (
            <g key={b.label}>
              <rect
                x={51 + i * 52}
                y={225 - (b.count / maxBin) * 180}
                width="35"
                height={(b.count / maxBin) * 180}
                fill={green}
              >
                <title>
                  {b.label}: {b.count} companies
                </title>
              </rect>
              <text x={68 + i * 52} y="245" textAnchor="middle">
                {i * 10}
              </text>
              {b.count > 0 && (
                <text
                  x={68 + i * 52}
                  y={218 - (b.count / maxBin) * 180}
                  textAnchor="middle"
                >
                  {b.count}
                </text>
              )}
            </g>
          ))}
          <text x="300" y="273" textAnchor="middle">
            Transparency score / 100
          </text>
        </Chart>
      </Panel>
      <Panel
        title="Which component needs attention?"
        note={`Component percentages, without weighting. ${rows.length > 8 ? "Highest 8 scores shown." : "Darker cells mean higher coverage."}`}
      >
        <div className="heatmap">
          <div className="heatmap-row heatmap-labels">
            <span>Company</span>
            {components.map((c) => (
              <span key={c.key}>{c.label}</span>
            ))}
          </div>
          {shown.map((r) => (
            <div className="heatmap-row" key={r.cin}>
              <span title={r.name}>{short(r.name, 26)}</span>
              {components.map((c) => {
                const t = 0.04 + (r[c.key] / 100) * 0.4;
                return (
                  <span
                    key={c.key}
                    style={{
                      background: `rgb(${Math.round(255 - 247 * t)},${Math.round(255 - 128 * t)},${Math.round(255 - 141 * t)})`,
                      color: "#173d38",
                    }}
                  >
                    {fmt(r[c.key])}
                  </span>
                );
              })}
            </div>
          ))}
        </div>
      </Panel>
      <Panel
        title="Clear wording, concrete evidence?"
        note="Each dot is one company. High clarity can coexist with low specificity."
      >
        <Chart name="Scatter plot of specificity versus clarity" height={285}>
          {[0, 25, 50, 75, 100].map((v) => (
            <g key={v}>
              <line
                x1="55"
                x2="570"
                y1={225 - v * 1.9}
                y2={225 - v * 1.9}
                stroke="#e8edef"
              />
              <text x="43" y={229 - v * 1.9} textAnchor="end">
                {v}
              </text>
              <text x={55 + v * 5.15} y="245" textAnchor="middle">
                {v}
              </text>
            </g>
          ))}
          <line x1="55" x2="570" y1="225" y2="225" stroke="#bac7cb" />
          {rows.map((r) => (
            <circle
              key={r.cin}
              cx={55 + r.specificity_pct * 5.15}
              cy={225 - r.clarity_pct * 1.9}
              r={rows.length > 30 ? 3.5 : 5}
              fill={green}
              opacity=".65"
              stroke="#f9fbfa"
              strokeWidth="1"
            >
              <title>
                {r.name}: specificity {fmt(r.specificity_pct)}%, clarity{" "}
                {fmt(r.clarity_pct)}%, TS {fmt(r.transparency_score)}
              </title>
            </circle>
          ))}
          <text x="300" y="274" textAnchor="middle">
            Specificity % →
          </text>
          <text
            x="14"
            y="128"
            transform="rotate(-90 14 128)"
            textAnchor="middle"
          >
            Clarity % →
          </text>
        </Chart>
      </Panel>
      <Panel
        title={
          sectorMode
            ? "How wide is each sector’s spread?"
            : "How far from the sector benchmark?"
        }
        note={
          sectorMode
            ? "10 largest sectors: range line, median tick and mean dot. N is the company count."
            : "Difference from each company’s own sector mean, in score points. Highest 8 scores shown."
        }
      >
        {sectorMode ? (
          <Chart name="Sector score ranges with means and medians" height={310}>
            <Axis x={235} width={320} height={238} />
            {sectors.map((s, i) => (
              <g key={s.sector}>
                <text x="223" y={34 + i * 23} textAnchor="end">
                  <title>{s.sector}</title>
                  {short(s.sector, 29)} ({s.n})
                </text>
                <line
                  x1={235 + s.min * 3.2}
                  x2={235 + s.max * 3.2}
                  y1={30 + i * 23}
                  y2={30 + i * 23}
                  stroke="#b5c5c8"
                  strokeWidth="3"
                />
                <line
                  x1={235 + s.median * 3.2}
                  x2={235 + s.median * 3.2}
                  y1={23 + i * 23}
                  y2={37 + i * 23}
                  stroke="#3d555a"
                />
                <circle
                  cx={235 + s.mean * 3.2}
                  cy={30 + i * 23}
                  r="4"
                  fill={green}
                >
                  <title>
                    {s.sector}: mean {fmt(s.mean)}, median {fmt(s.median)},
                    range {fmt(s.min)}–{fmt(s.max)}, N={s.n}
                  </title>
                </circle>
              </g>
            ))}
          </Chart>
        ) : (
          <Chart
            name="Diverging score gaps from each company's sector mean"
            height={260}
          >
            <line x1="390" x2="390" y1="15" y2="211" stroke="#99aaae" />
            {shown.map((r, i) => {
              const group = population.filter((p) => p.sector === r.sector);
              const gap =
                r.transparency_score -
                mean(group.map((p) => p.transparency_score));
              return (
                <g key={r.cin}>
                  <text x="179" y={34 + i * 23} textAnchor="end">
                    {short(r.name, 25)}
                  </text>
                  <rect
                    x={390 + Math.min(0, gap) * 5}
                    y={23 + i * 23}
                    width={Math.abs(gap) * 5}
                    height="13"
                    fill={gap >= 0 ? green : "#b47728"}
                  />
                  <text
                    x={gap >= 0 ? 397 + gap * 5 : 383 + gap * 5}
                    y={34 + i * 23}
                    textAnchor={gap >= 0 ? "start" : "end"}
                  >
                    {gap >= 0 ? "+" : ""}
                    {fmt(gap)}
                  </text>
                </g>
              );
            })}
            <text x="390" y="237" textAnchor="middle">
              Own sector mean = 0
            </text>
          </Chart>
        )}
      </Panel>
      <Panel
        title="How much of the score is still available?"
        note="Weighted headroom to 100. A diagnostic opportunity, not a prediction."
      >
        <Chart name="Weighted headroom by score component" height={260}>
          <Axis x={155} width={370} height={178} />
          {components.map((c, i) => {
            const value = mean(rows.map((r) => r[c.key]));
            const achieved = value * c.weight;
            const room = (100 - value) * c.weight;
            return (
              <g key={c.key}>
                <text x="144" y={44 + i * 39} textAnchor="end">
                  {c.label}
                </text>
                <rect
                  x="155"
                  y={29 + i * 39}
                  width={100 * c.weight * 3.7}
                  height="20"
                  fill={grey}
                />
                <rect
                  x="155"
                  y={29 + i * 39}
                  width={achieved * 3.7}
                  height="20"
                  fill={c.color}
                />
                <text x={164 + 100 * c.weight * 3.7} y={43 + i * 39}>
                  {fmt(room)} pts available
                  <title>
                    Mean {c.label}: {fmt(value)}%; {fmt(achieved)} of{" "}
                    {100 * c.weight} possible weighted points
                  </title>
                </text>
              </g>
            );
          })}
          <text x="300" y="232" textAnchor="middle">
            Mean transparency score {fmt(average)}
          </text>
        </Chart>
      </Panel>
    </div>
  );
}
