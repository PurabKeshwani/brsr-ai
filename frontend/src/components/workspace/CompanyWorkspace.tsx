"use client";
import { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { ExternalLink, ArrowUpRight, Search } from "lucide-react";
import {
  components,
  useResearch,
  fmt,
  signed,
  fy,
  label,
  mean,
  scored,
  type Analytics,
  type Workspace,
  type FiledFact,
  type EvidenceSignal,
} from "@/lib/analytics";
import {
  PageHead,
  Panel,
  Skeleton,
  ErrorState,
  ExportButton,
  Empty,
} from "./Shared";

const principleNames = [
  "Ethics & governance",
  "Sustainable products",
  "Employee wellbeing",
  "Stakeholders",
  "Human rights",
  "Environment",
  "Public policy",
  "Inclusive growth",
  "Consumer value",
];
const sdgNames = [
  "No poverty",
  "Zero hunger",
  "Good health",
  "Quality education",
  "Gender equality",
  "Clean water",
  "Clean energy",
  "Decent work",
  "Industry & innovation",
  "Reduced inequalities",
  "Sustainable cities",
  "Responsible consumption",
  "Climate action",
  "Life below water",
  "Life on land",
  "Peace & institutions",
  "Partnerships",
];

function FactTable({ facts }: { facts: FiledFact[] }) {
  return (
    <div className="table-scroll">
      <table className="data-table fact-table">
        <thead>
          <tr>
            <th>Fact / concept</th>
            <th>Filed value</th>
            <th>Unit</th>
            <th>Period</th>
            <th>Context / dimensions</th>
          </tr>
        </thead>
        <tbody>
          {facts.map((f) => (
            <tr key={f.id}>
              <td>
                <strong>#{f.id}</strong>
                <small title={f.concept}>{label(f.concept)}</small>
              </td>
              <td className="filed-value">
                <div
                  className="raw-fact-value"
                  tabIndex={f.value.length > 200 ? 0 : undefined}
                >
                  {f.value}
                </div>
              </td>
              <td>{f.unit ?? "—"}</td>
              <td className="nowrap">
                {f.period_end ?? "—"}
                {f.period_start && <small>from {f.period_start}</small>}
              </td>
              <td>
                <div className="dimension-tags">
                  {Object.entries(f.dimensions ?? {}).map(([k, v]) => (
                    <span key={k} title={`${k}: ${v}`}>
                      {label(k)}: {label(v)}
                    </span>
                  ))}
                  {!Object.keys(f.dimensions ?? {}).length && (
                    <small>No dimensions</small>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function SourceParagraph({
  fact,
  sentence,
}: {
  fact: FiledFact;
  sentence: string;
}) {
  const index = fact.value.indexOf(sentence);
  return (
    <div className="source-paragraph">
      <div className="source-caption">
        Source fact #{fact.id} · {label(fact.concept)} ·{" "}
        {fact.period_end ?? "No explicit period"}
      </div>
      <p>
        {index >= 0 ? (
          <>
            {fact.value.slice(0, index)}
            <mark>{sentence}</mark>
            {fact.value.slice(index + sentence.length)}
          </>
        ) : (
          fact.value
        )}
      </p>
    </div>
  );
}
function EvidenceCard({ signal }: { signal: EvidenceSignal }) {
  return (
    <details className="evidence-item">
      <summary>
        <span
          className={`tag ${signal.severity === "notable" ? "tag-warning" : "tag-neutral"}`}
        >
          {signal.severity === "notable" ? "Priority review" : "Review signal"}
        </span>
        <strong>{label(signal.concept)}</strong>
        <span>View claim + filed evidence</span>
      </summary>
      <div className="evidence-content">
        <blockquote>{signal.matched_sentence}</blockquote>
        <p>{signal.rationale}</p>
        <div className="scope-note">
          Assurance: {signal.assurance_level ?? "Not recorded"}. This is a
          screening signal for human review; scope, intensity and reporting
          boundary can affect interpretation.
        </div>
        <h3>Matched numeric records</h3>
        <FactTable facts={signal.numeric_evidence} />
        <h3>Original filed paragraph</h3>
        {signal.sources.length ? (
          signal.sources.map((f) => (
            <SourceParagraph
              key={f.id}
              fact={f}
              sentence={signal.matched_sentence}
            />
          ))
        ) : (
          <Empty>
            The exact paragraph could not be linked to a source fact.
          </Empty>
        )}
      </div>
    </details>
  );
}
export function CompanyWorkspace({ name }: { name: string }) {
  const [filing, setFiling] = useState<number | undefined>(),
    [tab, setTab] = useState("overview"),
    [query, setQuery] = useState(""),
    [factType, setFactType] = useState("all"),
    [page, setPage] = useState(1),
    [metricIndex, setMetricIndex] = useState(0);
  useEffect(() => {
    const f = new URLSearchParams(location.search).get("filing");
    if (f && /^\d+$/.test(f)) setFiling(Number(f));
  }, []);
  const path = `/companies/${encodeURIComponent(name)}/workspace${filing ? `?filing_id=${filing}` : ""}`;
  const { data, error, retry } = useResearch<Workspace>(path);
  const { data: universe } = useResearch<Analytics>("/analytics/overview");
  useEffect(() => {
    setPage(1);
  }, [query, factType, filing]);
  const filtered = useMemo(
    () =>
      (data?.facts ?? []).filter(
        (f) =>
          (factType === "all" ||
            (factType === "narrative"
              ? f.concept.includes("ExplanatoryTextBlock")
              : f.unit != null)) &&
          `${f.concept} ${f.value} ${f.id} ${JSON.stringify(f.dimensions)}`
            .toLowerCase()
            .includes(query.toLowerCase()),
      ),
    [data, query, factType],
  );
  if (error) return <ErrorState message={error} retry={retry} />;
  if (!data) return <Skeleton detail />;
  const d = data,
    s = d.score,
    metric = d.metrics[metricIndex] ?? d.metrics[0];
  const peers = scored(
      (universe?.companies ?? []).filter((c) => c.sector === d.company.sector),
    ),
    peerMean = mean(peers.map((c) => c.transparency_score));
  const percentile =
    s && peers.length
      ? (peers.filter((c) => c.transparency_score < s.transparency_score)
          .length /
          peers.length) *
        100
      : null;
  const history = (universe?.history ?? []).filter(
    (h) => h.cin === d.company.cin,
  );
  const issues =
    d.signals.length +
    d.assurance_gaps.length +
    d.silent_removals.length +
    d.lexical_flags.length;
  const sourceUrl = /^https?:\/\//i.test(d.filing.source_url)
    ? d.filing.source_url
    : null;
  return (
    <div className="workspace-page">
      <div className="detail-breadcrumb">
        <Link href="/companies">Company explorer</Link>
        <span>/</span>
        <span>Report #{d.filing.id}</span>
      </div>
      <PageHead
        title={d.company.name}
        description={`${d.company.sector} · CIN ${d.company.cin}`}
        action={
          <div className="inline-actions">
            <Link
              className="btn"
              href={`/compare?cin=${encodeURIComponent(d.company.cin)}`}
            >
              Compare peers <ArrowUpRight size={14} />
            </Link>
            {sourceUrl && (
              <a
                className="btn"
                href={sourceUrl}
                target="_blank"
                rel="noreferrer"
              >
                Source filing <ExternalLink size={14} />
              </a>
            )}
          </div>
        }
      />
      <div className="detail-meta">
        <label>
          Report
          <select
            value={d.filing.id}
            onChange={(e) => {
              setFiling(Number(e.target.value));
              const url = new URL(location.href);
              url.searchParams.set("filing", e.target.value);
              historyReplace(url);
            }}
          >
            {d.filings.map((f) => (
              <option key={f.id} value={f.id}>
                {fy(f.financial_year_end)} · Report #{f.id}
              </option>
            ))}
          </select>
        </label>
        <span>{fmt(d.filing.raw_fact_count, 0)} raw facts</span>
        <span>
          {d.score_evidence.narrative_segments} retained narrative pairs
        </span>
        <span className="tag tag-neutral">
          {s
            ? d.score_source === "computed_current_rules"
              ? "Computed with current rules"
              : "Saved research score"
            : "Scoring unavailable"}
        </span>
      </div>
      <div className="tabs" role="tablist" aria-label="Company analysis">
        {[
          { id: "overview", name: "Score & coverage" },
          { id: "metrics", name: "Metrics & history" },
          { id: "evidence", name: "Evidence review", count: issues },
          { id: "checks", name: "Assurance & checks" },
          { id: "facts", name: "Source fact register", count: d.facts.length },
        ].map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
          >
            {t.name}
            {t.count != null && <small>{t.count}</small>}
          </button>
        ))}
      </div>
      <div key={tab} className="tab-content">
        {d.scoring_error && <div className="scope-note">{d.scoring_error}</div>}
        {tab === "overview" &&
          s &&
          Math.abs(
            (d.score_evidence.narrative_segments
              ? (100 * d.score_evidence.kpi_segments) /
                d.score_evidence.narrative_segments
              : 0) - s.specificity_pct,
          ) > 0.02 && (
            <div className="scope-note">
              <span>Snapshot / current-rule difference</span>The saved
              specificity is {fmt(s.specificity_pct)}%. Current evidence-marker
              rules identify {d.score_evidence.kpi_segments}/
              {d.score_evidence.narrative_segments} narrative pairs (
              {fmt(
                d.score_evidence.narrative_segments
                  ? (100 * d.score_evidence.kpi_segments) /
                      d.score_evidence.narrative_segments
                  : 0,
              )}
              %). The saved research score is retained for comparable paper
              results.
            </div>
          )}
        {tab === "overview" && (
          <>
            <div className="metric-strip">
              {[
                {
                  label: "Transparency score",
                  value: s ? fmt(s.transparency_score) : "—",
                  note: "0–100 · disclosure quality",
                },
                {
                  label: "Own-sector percentile",
                  value: percentile == null ? "—" : `${fmt(percentile, 1)}th`,
                  note: `${peers.length} peers · latest-report snapshot`,
                },
                {
                  label: "Accepted concepts",
                  value: fmt(d.score_evidence.accepted_concepts, 0),
                  note: `of ${fmt(d.score_evidence.universe_size, 0)} corpus concepts`,
                },
                {
                  label: "Review queue",
                  value: fmt(issues, 0),
                  note: "Screening items, not confirmed violations",
                },
              ].map((x) => (
                <div key={x.label}>
                  <span>{x.label}</span>
                  <strong>{x.value}</strong>
                  <small>{x.note}</small>
                </div>
              ))}
            </div>
            <div className="analysis-grid">
              <Panel
                title="Reconstruct the transparency score"
                note="Fixed weights make each component’s contribution explicit."
              >
                {s ? (
                  <>
                    <div className="contribution-bar">
                      {components.map((c) => (
                        <span
                          key={c.key}
                          style={{
                            width: `${s[c.key] * c.weight}%`,
                            background: c.color,
                          }}
                          title={`${c.label}: ${fmt(s[c.key] * c.weight)} points`}
                        />
                      ))}
                    </div>
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Component</th>
                          <th className="num">Percentage</th>
                          <th className="num">Weight</th>
                          <th className="num">Points</th>
                        </tr>
                      </thead>
                      <tbody>
                        {components.map((c) => (
                          <tr key={c.key}>
                            <td>
                              <span className="legend-inline">
                                <i style={{ background: c.color }} />
                                {c.label}
                              </span>
                            </td>
                            <td className="num">{fmt(s[c.key])}%</td>
                            <td className="num">{c.weight.toFixed(2)}</td>
                            <td className="num">
                              {fmt(s[c.key] * c.weight, 3)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <div className="calculation-total">
                      Transparency score
                      <strong>{fmt(s.transparency_score)} / 100</strong>
                    </div>
                  </>
                ) : (
                  <Empty>
                    This report has no score in the saved research export.
                    Source facts, metrics and checks remain available.
                  </Empty>
                )}
                <p className="data-footnote">
                  Completeness uses the corpus concept universe. Specificity is
                  evidence-marker presence; clarity is absence of flagged
                  vagueness. SDG breadth is a coverage proxy. Rounded components
                  can cause a 0.01-point difference.
                </p>
              </Panel>
              <Panel
                title="Read the score in context"
                note={`Peer group: ${d.company.sector}`}
              >
                <div className="benchmark-readout">
                  <strong>{s ? fmt(s.transparency_score) : "—"}</strong>
                  <span>
                    company TS <small>vs {fmt(peerMean)} sector mean</small>
                  </span>
                  {s && peers.length > 0 && (
                    <b>{signed(s.transparency_score - peerMean)} points</b>
                  )}
                </div>
                <svg
                  viewBox="0 0 550 100"
                  className="analysis-chart"
                  role="img"
                  aria-label="Company score against sector mean on a 0 to 100 scale"
                >
                  <line
                    x1="30"
                    x2="520"
                    y1="40"
                    y2="40"
                    stroke="#dbe4e5"
                    strokeWidth="7"
                  />
                  {[0, 25, 50, 75, 100].map((n) => (
                    <text key={n} x={30 + n * 4.9} y="70" textAnchor="middle">
                      {n}
                    </text>
                  ))}
                  {peers.length > 0 && (
                    <line
                      x1={30 + peerMean * 4.9}
                      x2={30 + peerMean * 4.9}
                      y1="27"
                      y2="53"
                      stroke="#6b7e83"
                      strokeWidth="2"
                    />
                  )}
                  {s && (
                    <circle
                      cx={30 + s.transparency_score * 4.9}
                      cy="40"
                      r="7"
                      fill="#087f72"
                    />
                  )}
                </svg>
                <div className="chart-legend">
                  <span>
                    <i style={{ background: "#087f72" }} />
                    Company
                  </span>
                  <span>
                    <i style={{ background: "#6b7e83" }} />
                    Sector mean
                  </span>
                </div>
                <div className="scope-note">
                  {peers.length < 5
                    ? "Fewer than five peers: sector comparisons are indicative only."
                    : "Benchmark uses the saved latest-report population, which can contain mixed years."}
                  {filing &&
                    history.some((h) => h.filing_id !== d.filing.id) &&
                    " Selected historical reports are compared against latest peer scores."}
                </div>
                <Link
                  className="text-action"
                  href={`/compare?sector=${encodeURIComponent(d.company.sector)}`}
                >
                  Explore complete sector <ArrowUpRight size={14} />
                </Link>
              </Panel>
              <Panel
                title="Evidence behind the components"
                note="Counts reconstructed from this report’s retained records."
              >
                <div className="evidence-counts">
                  <div>
                    <span>Completeness</span>
                    <strong>
                      {d.score_evidence.accepted_concepts} /{" "}
                      {d.score_evidence.universe_size}
                    </strong>
                    <small>Accepted concepts / corpus concept universe</small>
                  </div>
                  <div>
                    <span>Specificity</span>
                    <strong>
                      {d.score_evidence.kpi_segments} /{" "}
                      {d.score_evidence.narrative_segments}
                    </strong>
                    <small>Narrative pairs containing an evidence marker</small>
                  </div>
                  <div>
                    <span>SDG breadth</span>
                    <strong>{d.score_evidence.sdgs_covered.length} / 17</strong>
                    <small>Goals mapped from evidence-backed principles</small>
                  </div>
                </div>
                <p className="data-footnote">
                  These counts use the current database; a snapshot can differ
                  if the corpus has changed since scoring.
                </p>
              </Panel>
              <Panel
                title="Principles and mapped goals"
                note="Tags distinguish evidence-backed principle coverage from mapped SDG breadth."
              >
                <h3 className="subsection-label">
                  BRSR principles with KPI evidence
                </h3>
                <div className="coverage-tags">
                  {Array.from({ length: 9 }, (_, i) => i + 1).map((n) => (
                    <span
                      key={n}
                      className={
                        d.score_evidence.principles_disclosed.includes(n)
                          ? "covered"
                          : ""
                      }
                      title={
                        d.score_evidence.principles_disclosed.includes(n)
                          ? "KPI-backed narrative retained"
                          : "No KPI-backed narrative retained"
                      }
                    >
                      P{n} · {principleNames[n - 1]}
                    </span>
                  ))}
                </div>
                <h3 className="subsection-label">
                  Mapped sustainable development goals
                </h3>
                <div className="coverage-tags">
                  {Array.from({ length: 17 }, (_, i) => i + 1).map((n) => (
                    <span
                      key={n}
                      className={
                        d.score_evidence.sdgs_covered.includes(n)
                          ? "covered"
                          : ""
                      }
                    >
                      SDG {n} · {sdgNames[n - 1]}
                    </span>
                  ))}
                </div>
                <p className="data-footnote">
                  Filled tags indicate observed coverage. They do not measure
                  goal achievement or legal compliance.
                </p>
              </Panel>
            </div>
          </>
        )}
        {tab === "metrics" && (
          <>
            <div className="scope-note">
              <span>Like-for-like series</span>Each series preserves the filed
              unit and dimensions. Prior-period values within a single filing
              are different from paired report scores.
            </div>
            <div className="filter-bar">
              <label className="wide-control">
                Metric and reporting boundary
                <select
                  value={metricIndex}
                  onChange={(e) => setMetricIndex(Number(e.target.value))}
                >
                  {d.metrics.map((m, i) => (
                    <option key={i} value={i}>
                      {m.label} · {m.unit ?? "unit not filed"} ·{" "}
                      {Object.entries(m.dimensions)
                        .map(([k, v]) => `${label(k)}: ${label(v)}`)
                        .join(", ") || "No dimensions"}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {metric ? (
              <div className="analysis-grid">
                <Panel
                  title={metric.label}
                  note={`Filed unit: ${metric.unit ?? "not recorded"}. Separate observations, without invented intermediate values.`}
                >
                  <svg
                    viewBox="0 0 600 290"
                    className="analysis-chart"
                    role="img"
                    aria-label={`${metric.label} by reporting period`}
                  >
                    {[0, 0.25, 0.5, 0.75, 1].map((r) => {
                      const max =
                        Math.max(
                          1,
                          ...metric.series.map((p) => Math.abs(p.value)),
                        ) * 1.15;
                      return (
                        <g key={r}>
                          <line
                            x1="80"
                            x2="575"
                            y1={230 - r * 190}
                            y2={230 - r * 190}
                            stroke="#e6ecee"
                          />
                          <text x="67" y={234 - r * 190} textAnchor="end">
                            {fmt(max * r, 0)}
                          </text>
                        </g>
                      );
                    })}
                    {metric.series.map((p, i) => {
                      const max =
                        Math.max(
                          1,
                          ...metric.series.map((p) => Math.abs(p.value)),
                        ) * 1.15;
                      const x =
                        110 + i * (410 / Math.max(1, metric.series.length - 1));
                      return (
                        <g key={p.period}>
                          <rect
                            x={x - 22}
                            y={230 - (Math.max(0, p.value) / max) * 190}
                            width="44"
                            height={(Math.max(0, p.value) / max) * 190}
                            fill={
                              i === metric.series.length - 1
                                ? "#087f72"
                                : "#bdcdcf"
                            }
                          />
                          <text
                            x={x}
                            y={218 - (Math.max(0, p.value) / max) * 190}
                            textAnchor="middle"
                          >
                            {fmt(p.value)}
                          </text>
                          <text x={x} y="254" textAnchor="middle">
                            {fy(p.period)}
                          </text>
                        </g>
                      );
                    })}
                  </svg>
                  {metric.conflicting_periods.length > 0 && (
                    <div className="scope-note">
                      Conflicting duplicate values were excluded for{" "}
                      {metric.conflicting_periods.join(", ")}.
                    </div>
                  )}
                </Panel>
                <Panel
                  title="Period-matched records"
                  note={
                    metric.yoy_change_pct == null
                      ? "Percentage change unavailable: a second value or nonzero baseline is required."
                      : `${signed(metric.yoy_change_pct)}% from the previous recorded period.`
                  }
                >
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Period end</th>
                        <th className="num">Filed value</th>
                        <th>Source facts</th>
                      </tr>
                    </thead>
                    <tbody>
                      {metric.series.map((p) => (
                        <tr key={p.period}>
                          <td>{p.period}</td>
                          <td className="num">{fmt(p.value)}</td>
                          <td>{p.fact_ids.map((id) => `#${id}`).join(", ")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="scope-note">
                    A change in an absolute measure is not by itself proof of
                    improvement or deterioration. Business activity, intensity
                    and boundary matter.
                  </div>
                  <ExportButton
                    rows={metric.series}
                    filename="brsr-metric-history.csv"
                  />
                </Panel>
              </div>
            ) : (
              <Empty>
                No numeric series are available for the tracked environmental
                concepts.
              </Empty>
            )}
            <Panel
              title="Transparency scores across reports"
              note={
                history.length > 1
                  ? `${history.length} scored reports available for this company.`
                  : "Only one scored report is available. No score trend is inferred."
              }
            >
              <div className="report-links">
                {history.map((h) => (
                  <button
                    key={h.filing_id}
                    onClick={() => setFiling(h.filing_id)}
                  >
                    <span>
                      {fy(h.financial_year_end)}
                      <small>Report #{h.filing_id}</small>
                    </span>
                    <strong>{fmt(h.transparency_score)}</strong>
                  </button>
                ))}
              </div>
              <Link className="text-action" href="/time-series">
                Open paired-year analysis <ArrowUpRight size={14} />
              </Link>
            </Panel>
          </>
        )}
        {tab === "evidence" && (
          <>
            <div className="scope-note">
              <span>Review evidence</span>Claim–number tensions, missing
              evidence, lexical cues and removed disclosures are separate
              signals. The original filed text is preserved; flags do not
              establish intent.
            </div>
            <Panel
              title="Claim versus filed numbers"
              note={`${d.signals.length} sentence-level signals. Expand a row to inspect the claim, numeric facts and original paragraph.`}
            >
              {d.signals.length ? (
                d.signals.map((signal, i) => (
                  <EvidenceCard key={i} signal={signal} />
                ))
              ) : (
                <Empty>
                  No claim–number tensions were detected by the configured rules
                  in this filing. This does not establish an absence of
                  greenwashing.
                </Empty>
              )}
            </Panel>
            <Panel
              title="Claims with evidence or assurance gaps"
              note="Separate from numeric contradictions. Gaps retain their original source paragraph."
            >
              {d.assurance_gaps.length ? (
                d.assurance_gaps.map((g, i) => (
                  <details className="evidence-item" key={i}>
                    <summary>
                      <span className="tag tag-warning">
                        {g.severity.startsWith("high")
                          ? "Fact missing"
                          : "Assurance gap"}
                      </span>
                      <strong>{label(g.concept)}</strong>
                      <span>Inspect source</span>
                    </summary>
                    <div className="evidence-content">
                      <p>{g.rationale}</p>
                      <SourceParagraph fact={g.source} sentence="" />
                    </div>
                  </details>
                ))
              ) : (
                <Empty>
                  No configured evidence or assurance gaps were detected.
                </Empty>
              )}
            </Panel>
            <Panel
              title="Language cues for review"
              note="Lexical rule matches only. This list is distinct from the saved combined-model clarity score."
            >
              {d.lexical_flags.length ? (
                d.lexical_flags.map((f) => (
                  <details className="evidence-item" key={f.id}>
                    <summary>
                      <span className="tag tag-neutral">Language cue</span>
                      <strong>{label(f.concept)}</strong>
                      <span>Fact #{f.id}</span>
                    </summary>
                    <div className="evidence-content">
                      <SourceParagraph fact={f} sentence="" />
                    </div>
                  </details>
                ))
              ) : (
                <Empty>
                  No unsupported-language cues matched the lexical rules.
                </Empty>
              )}
            </Panel>
            <Panel
              title="Disclosures absent in the current period"
              note="A prior-period value without a corresponding current-period disclosure is a review lead."
            >
              {d.silent_removals.length ? (
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Metric</th>
                        <th>Prior value / period</th>
                        <th>Why it needs review</th>
                      </tr>
                    </thead>
                    <tbody>
                      {d.silent_removals.map((r, i) => (
                        <tr key={i}>
                          <td>
                            {label(r.concept)}
                            <small>{r.context}</small>
                          </td>
                          <td>
                            {r.prior_year_value}
                            <small>{r.prior_year_period}</small>
                          </td>
                          <td>{r.rationale}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <Empty>
                  No silent removals were detected for the configured metrics.
                </Empty>
              )}
            </Panel>
          </>
        )}
        {tab === "checks" && (
          <div className="analysis-grid">
            <Panel
              title="Independent assurance coverage"
              note="Reasonable, limited and unassured areas are shown separately."
            >
              <div className="assurance-rows">
                {[
                  {
                    name: "Reasonable assurance",
                    count: d.assurance.reasonable_count,
                    color: "#087f72",
                  },
                  {
                    name: "Limited assurance",
                    count: d.assurance.limited_count,
                    color: "#9c7930",
                  },
                  {
                    name: "Unassured",
                    count: d.assurance.unassured_count,
                    color: "#a8b6bc",
                  },
                ].map((a) => (
                  <div key={a.name}>
                    <span>{a.name}</span>
                    <div className="plain-bar">
                      <i
                        style={{
                          width: `${d.assurance.total_disclosure_areas ? (a.count / d.assurance.total_disclosure_areas) * 100 : 0}%`,
                          background: a.color,
                        }}
                      />
                    </div>
                    <strong>{a.count}</strong>
                  </div>
                ))}
              </div>
              <p className="data-footnote">
                {d.assurance.assured_count} assured of{" "}
                {d.assurance.total_disclosure_areas} disclosure areas. Assurance
                levels describe coverage, not a verified greenwashing verdict.
              </p>
            </Panel>
            <Panel
              title="Consistency checks"
              note="Arithmetic checks on structured data, including gender and workforce totals."
            >
              <div className="check-results">
                <span>
                  <strong>{d.consistency.passed}</strong>Passed
                </span>
                <span>
                  <strong>{d.consistency.failed}</strong>Failed
                </span>
                <span>
                  <strong>{d.consistency.skipped}</strong>Skipped
                </span>
              </div>
              {d.consistency.failures.map((f, i) => (
                <details className="evidence-item" key={i}>
                  <summary>
                    <span className="tag tag-warning">Check failed</span>
                    <strong>{label(f.concept)}</strong>
                  </summary>
                  <div className="evidence-content">
                    <p>{f.message}</p>
                    <small>{f.context}</small>
                  </div>
                </details>
              ))}
            </Panel>
            <Panel
              title="Areas with lower assurance"
              note="Filed disclosure-area tags retained for inspection."
            >
              <div className="dimension-tags">
                {d.assurance.low_assurance_areas.map((a, i) => (
                  <span key={i}>{label(a)}</span>
                ))}
              </div>
              {!d.assurance.low_assurance_areas.length && (
                <Empty>No low-assurance areas were returned.</Empty>
              )}
            </Panel>
          </div>
        )}
        {tab === "facts" && (
          <Panel
            title="Source fact register"
            note={`Showing ${Math.min((page - 1) * 30 + 1, filtered.length)}–${Math.min(page * 30, filtered.length)} of ${filtered.length} matched records. Raw strings are preserved.`}
            action={
              <ExportButton
                rows={filtered.map((f) => ({
                  ...f,
                  dimensions: JSON.stringify(f.dimensions),
                }))}
                filename={`report-${d.filing.id}-facts.csv`}
              />
            }
          >
            <div className="filter-bar">
              <label className="search-control">
                Search text, concept, context or fact ID
                <div>
                  <Search size={14} />
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="e.g. Scope1, water, Principle6Member…"
                  />
                </div>
              </label>
              <label>
                Fact type
                <select
                  value={factType}
                  onChange={(e) => setFactType(e.target.value)}
                >
                  <option value="all">All source facts</option>
                  <option value="narrative">Narrative text blocks</option>
                  <option value="numeric">Facts with filed units</option>
                </select>
              </label>
            </div>
            {filtered.length ? (
              <FactTable facts={filtered.slice((page - 1) * 30, page * 30)} />
            ) : (
              <Empty>No source facts match these filters.</Empty>
            )}
            <div className="pagination">
              <button
                className="btn"
                disabled={page === 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </button>
              <span>
                Page {page} of {Math.max(1, Math.ceil(filtered.length / 30))}
              </span>
              <button
                className="btn"
                disabled={page * 30 >= filtered.length}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          </Panel>
        )}
      </div>
      <p className="data-footnote">
        Report #{d.filing.id} · {d.filing.financial_year_start} to{" "}
        {d.filing.financial_year_end}. Evidence comes from filed XBRL records.
        PDF page coordinates are not stored; paragraphs and fact IDs provide
        source traceability.
      </p>
    </div>
  );
}
function historyReplace(url: URL) {
  window.history.replaceState(null, "", url);
}
