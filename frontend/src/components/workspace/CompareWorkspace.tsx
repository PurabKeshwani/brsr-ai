"use client";
import { useMemo, useState, useEffect } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { X, Search, Plus, ArrowUpRight } from "lucide-react";
import {
  useResearch,
  scored,
  stats,
  fmt,
  fy,
  type Analytics,
} from "@/lib/analytics";
import {
  PageHead,
  Panel,
  StatStrip,
  Skeleton,
  ErrorState,
  ScoreTable,
  ExportButton,
  Empty,
} from "./Shared";
import { PeerEvidence } from "./PeerEvidence";
const Charts = dynamic(() => import("./ComparisonCharts"), {
  loading: () => <Skeleton />,
});
type Mode = "peers" | "sector" | "all";
export function CompareWorkspace({
  overview = false,
  explorer = false,
}: {
  overview?: boolean;
  explorer?: boolean;
}) {
  const { data, error, retry } = useResearch<Analytics>("/analytics/overview");
  const [mode, setMode] = useState<Mode>(overview ? "all" : "sector");
  const [sector, setSector] = useState(
    explorer ? "all" : "Financial Services (excl. Insurance)",
  );
  const [year, setYear] = useState("latest"),
    [query, setQuery] = useState(""),
    [selected, setSelected] = useState<string[]>([]),
    [page, setPage] = useState(1),
    [minimum, setMinimum] = useState(true);
  const [sort, setSort] = useState("score-desc");
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const chosen = params.getAll("cin");
    if (chosen.length) {
      setSelected(chosen.slice(0, 8));
      setMode("peers");
    }
    const s = params.get("sector");
    if (s) setSector(s);
  }, []);
  useEffect(() => setPage(1), [mode, sector, year, query, sort, minimum]);
  const all = useMemo(() => data?.companies ?? [], [data]);
  const sectors = useMemo(
    () => [...new Set(all.map((r) => r.sector))].sort(),
    [all],
  );
  const years = useMemo(
    () =>
      [...new Set(all.map((r) => r.financial_year_end).filter(Boolean))]
        .sort()
        .reverse(),
    [all],
  );
  const population = useMemo(
    () =>
      scored(
        all.filter((r) => year === "latest" || r.financial_year_end === year),
      ),
    [all, year],
  );
  const groups = useMemo(
    () =>
      sectors
        .map((name) => ({
          name,
          ...stats(population.filter((r) => r.sector === name)),
        }))
        .filter((s) => s.n > 0 && (!minimum || s.n >= 5))
        .sort((a, b) => b.mean - a.mean),
    [sectors, population, minimum],
  );
  const rows = useMemo(() => {
    let rs = (
      explorer
        ? all.filter((r) => year === "latest" || r.financial_year_end === year)
        : population
    ).filter((r) =>
      explorer
        ? !sector || sector === "all" || r.sector === sector
        : mode === "all"
          ? true
          : mode === "sector"
            ? r.sector === sector
            : selected.includes(r.cin),
    );
    if (query && (explorer || mode !== "peers"))
      rs = rs.filter((r) =>
        `${r.name} ${r.cin}`.toLowerCase().includes(query.toLowerCase()),
      );
    return [...rs].sort((a, b) =>
      sort === "name"
        ? a.name.localeCompare(b.name)
        : sort === "score-asc"
          ? (a.transparency_score ?? Infinity) -
            (b.transparency_score ?? Infinity)
          : (b.transparency_score ?? -Infinity) -
            (a.transparency_score ?? -Infinity),
    );
  }, [all, year, population, mode, sector, selected, query, explorer, sort]);
  const matches = population
    .filter(
      (r) =>
        (sector === "all" || r.sector === sector) &&
        !selected.includes(r.cin) &&
        `${r.name} ${r.cin}`.toLowerCase().includes(query.toLowerCase()),
    )
    .slice(0, 6);
  const toggle = (cin: string) =>
    setSelected((prev) =>
      prev.includes(cin)
        ? prev.filter((x) => x !== cin)
        : prev.length < 8
          ? [...prev, cin]
          : prev,
    );
  if (error) return <ErrorState message={error} retry={retry} />;
  if (!data) return <Skeleton />;
  const periods = new Set(rows.map((r) => r.financial_year_end));
  return (
    <div className="workspace-page">
      <PageHead
        title={
          overview
            ? "Disclosure overview"
            : explorer
              ? "Company explorer"
              : "Compare disclosures"
        }
        description={
          overview
            ? "A corpus-wide view of disclosure quality, sector differences and available evidence."
            : explorer
              ? "Search, filter and open the source-linked analysis for every ingested company."
              : "Move from selected peers to a complete sector or the full research universe."
        }
        action={<ExportButton rows={rows} />}
      />
      {overview && (
        <div className="overview-context">
          <span className="status-dot" />
          <strong>{fmt(all.length, 0)} companies</strong>
          <span>{fmt(data.report_count, 0)} reports</span>
          <span>{fmt(data.fact_count, 0)} filed facts</span>
          <Link href="/time-series">
            {new Set(data.history.map((r) => r.cin)).size} paired companies{" "}
            <ArrowUpRight size={13} />
          </Link>
        </div>
      )}
      {!overview && !explorer && (
        <div className="tabs" role="tablist" aria-label="Comparison level">
          {(
            [
              { id: "peers", label: "Selected peers", note: "Up to 8" },
              { id: "sector", label: "Complete sector", note: "Every company" },
              {
                id: "all",
                label: "All sectors",
                note: `${sectors.length} groups`,
              },
            ] as const
          ).map((t) => (
            <button
              key={t.id}
              role="tab"
              aria-selected={mode === t.id}
              onClick={() => {
                setMode(t.id);
                setQuery("");
              }}
            >
              {t.label}
              <small>{t.note}</small>
            </button>
          ))}
          <Link href="/time-series">
            Paired-year analysis <ArrowUpRight size={14} />
          </Link>
        </div>
      )}
      <div className="filter-bar">
        {!overview && (
          <label>
            Sector
            <select
              value={sector}
              onChange={(e) => setSector(e.target.value)}
              disabled={mode === "all" && !explorer}
            >
              {(explorer || mode === "peers") && (
                <option value="all">All sectors</option>
              )}
              {sectors.map((x) => (
                <option key={x}>{x}</option>
              ))}
            </select>
          </label>
        )}
        <label>
          Reporting basis
          <select value={year} onChange={(e) => setYear(e.target.value)}>
            <option value="latest">Latest available per company</option>
            {years.map((x) => (
              <option key={x} value={x}>
                {fy(x)} · latest-report subset
              </option>
            ))}
          </select>
        </label>
        <label className="search-control">
          {mode === "peers" && !explorer ? "Add a peer" : "Find company or CIN"}
          <div>
            <Search size={15} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search company or CIN…"
            />
          </div>
        </label>
        <label>
          Order by
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="score-desc">Highest score first</option>
            <option value="score-asc">Lowest score first</option>
            <option value="name">Company name</option>
          </select>
        </label>
      </div>
      {mode === "peers" && !explorer && (
        <div className="peer-picker">
          <div className="selected-peers">
            {selected.map((cin) => {
              const r = all.find((x) => x.cin === cin);
              return (
                <button key={cin} onClick={() => toggle(cin)}>
                  {r?.name ?? cin}
                  <X size={13} />
                </button>
              );
            })}
            {!selected.length && (
              <span>Select peers below, or use the sector sample.</span>
            )}
            <button
              className="text-action"
              onClick={() => {
                const peers = population
                  .filter((r) => sector === "all" || r.sector === sector)
                  .sort((a, b) => b.transparency_score - a.transparency_score);
                setSelected(
                  [...peers.slice(0, 4), ...peers.slice(-3)]
                    .map((r) => r.cin)
                    .filter((v, i, a) => a.indexOf(v) === i),
                );
                setQuery("");
              }}
            >
              Use sector sample
            </button>
            <span>{selected.length}/8 selected</span>
          </div>
          {selected.length < 8 && (
            <div className="peer-options">
              {matches.map((r) => (
                <button
                  key={r.cin}
                  onClick={() => {
                    toggle(r.cin);
                    setQuery("");
                  }}
                >
                  <span>
                    {r.name}
                    <small>
                      {fy(r.financial_year_end)} · TS{" "}
                      {fmt(r.transparency_score)}
                    </small>
                  </span>
                  <Plus size={14} />
                </button>
              ))}
              {!matches.length && (
                <Empty>
                  No matching peers in this sector and reporting basis.
                </Empty>
              )}
            </div>
          )}
        </div>
      )}
      <div className="scope-note">
        <span>
          {periods.size > 1 ? "Mixed reporting periods" : "Reporting scope"}
        </span>
        {periods.size > 1
          ? "Latest reports include different financial years. Select one reporting period for a consistent-year subset."
          : rows.length
            ? `${fy(rows[0].financial_year_end)} · ${fmt(rows.length, 0)} companies in view.`
            : "Choose companies to begin."}
        <Link href="/methodology">How to interpret</Link>
      </div>
      {scored(rows).length > 0 && <StatStrip rows={scored(rows)} />}
      {overview && (
        <div className="overview-links">
          <Link href="/compare">
            Compare companies and sectors <ArrowUpRight size={15} />
          </Link>
          <Link href="/time-series">
            Explain changes between reports <ArrowUpRight size={15} />
          </Link>
          <Link href="/company/Triveni%20Turbine%20Limited">
            Open the paper’s company case <ArrowUpRight size={15} />
          </Link>
        </div>
      )}
      {!explorer && (
        <Charts
          rows={scored(rows)}
          population={population}
          sectorMode={mode === "all"}
        />
      )}
      {mode === "peers" && !explorer && <PeerEvidence rows={scored(rows)} />}
      {(mode === "all" || overview) && !explorer && (
        <Panel
          title="Sector benchmarks"
          note={`${groups.length} groups shown. Overall mean ${fmt(stats(population).mean)}. Small samples need additional care.`}
          action={
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={minimum}
                onChange={(e) => setMinimum(e.target.checked)}
              />
              At least 5 companies
            </label>
          }
        >
          <div className="table-scroll sector-table">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Sector</th>
                  {[
                    "N",
                    "Mean TS",
                    "Median",
                    "Minimum",
                    "Maximum",
                    "SD",
                    "vs overall",
                  ].map((h) => (
                    <th className="num" key={h}>
                      {h}
                    </th>
                  ))}
                  <th />
                </tr>
              </thead>
              <tbody>
                {groups.map((g) => (
                  <tr key={g.name}>
                    <td>
                      <button
                        className="company-link"
                        onClick={() => {
                          setSector(g.name);
                          setMode("sector");
                          window.scrollTo({ top: 0, behavior: "smooth" });
                        }}
                      >
                        {g.name}
                      </button>
                      {g.n < 5 && <small>Small peer group</small>}
                    </td>
                    {[
                      g.n,
                      g.mean,
                      g.median,
                      g.min,
                      g.max,
                      g.sd,
                      g.mean - stats(population).mean,
                    ].map((v, i) => (
                      <td className="num" key={i}>
                        {fmt(v, i === 0 ? 0 : 2)}
                      </td>
                    ))}
                    <td>
                      <button
                        className="text-action"
                        onClick={() => {
                          setSector(g.name);
                          setMode("sector");
                          window.scrollTo({ top: 0, behavior: "smooth" });
                        }}
                      >
                        Explore
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
      <Panel
        title={
          explorer ? `${rows.length} companies` : "Underlying company scores"
        }
        note={
          rows.length
            ? `Showing ${Math.min((page - 1) * 25 + 1, rows.length)}–${Math.min(page * 25, rows.length)} of ${rows.length}. Components are percentages; TS uses fixed weights.`
            : "No scored observations in this selection."
        }
        action={
          explorer && selected.length > 0 ? (
            <Link
              className="btn"
              href={`/compare?${selected.map((cin) => `cin=${encodeURIComponent(cin)}`).join("&")}`}
            >
              Compare {selected.length} selected <ArrowUpRight size={14} />
            </Link>
          ) : undefined
        }
      >
        <ScoreTable
          rows={rows.slice((page - 1) * 25, page * 25)}
          selectable={explorer}
          selected={selected}
          onSelect={toggle}
        />
        {rows.length > 25 && (
          <div className="pagination">
            <button
              className="btn"
              disabled={page === 1}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </button>
            <span>
              Page {page} of {Math.ceil(rows.length / 25)}
            </span>
            <button
              className="btn"
              disabled={page * 25 >= rows.length}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        )}
      </Panel>
      {explorer && all.length > scored(all).length && (
        <div className="scope-note">
          {all.length - scored(all).length} ingested companies have no saved
          score yet. Open their reports from the table; saved-score comparison is unavailable until they are scored into the research export.
        </div>
      )}
      <p className="data-footnote">
        {data.methodology} Snapshot file updated{" "}
        {data.score_updated_at
          ? new Date(data.score_updated_at).toLocaleDateString("en-IN")
          : "unknown"}
        . Within-period filters select latest reports only; historical paired
        scores are in Time series.
      </p>
    </div>
  );
}
