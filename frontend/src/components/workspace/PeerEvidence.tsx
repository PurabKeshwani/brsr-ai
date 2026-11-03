"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import {
  researchGet,
  fmt,
  signed,
  fy,
  type ResearchCompany,
  type Workspace,
} from "@/lib/analytics";
import { Panel, Skeleton, Empty } from "./Shared";
export function PeerEvidence({ rows }: { rows: ResearchCompany[] }) {
  const [enabled, setEnabled] = useState(false),
    [records, setRecords] = useState<
      { cin: string; data?: Workspace; error?: string }[]
    >([]),
    [busy, setBusy] = useState(false),
    [concept, setConcept] = useState("TotalScope1Emissions");
  const key = rows.map((r) => r.cin).join("|");
  useEffect(() => {
    if (!enabled) return;
    let active = true;
    setBusy(true);
    Promise.all(
      rows.map(async (r) => {
        try {
          return {
            cin: r.cin,
            data: await researchGet<Workspace>(
              `/companies/${encodeURIComponent(r.cin)}/workspace`,
            ),
          };
        } catch (error) {
          return {
            cin: r.cin,
            error:
              error instanceof Error
                ? error.message
                : "Unable to load evidence",
          };
        }
      }),
    ).then((result) => {
      if (active) {
        setRecords(result);
        setBusy(false);
      }
    });
    return () => {
      active = false;
    };
  }, [enabled, key]);
  const concepts = [
    ...new Map(
      records
        .flatMap((r) => r.data?.metrics ?? [])
        .map((m) => [m.concept, m.label]),
    ).entries(),
  ];
  return (
    <Panel
      title="Compare filed metrics and review signals"
      note="Load detailed evidence for selected peers only. Units and dimensional boundaries remain separate."
      action={
        <button
          className="btn"
          disabled={rows.length < 2 || busy}
          onClick={() => setEnabled(true)}
        >
          {busy
            ? "Loading evidence…"
            : enabled
              ? "Evidence loaded"
              : "Load evidence comparison"}
        </button>
      }
    >
      {!enabled ? (
        <Empty>
          Select at least two peers, then load their numeric disclosures and
          evidence review counts.
        </Empty>
      ) : busy ? (
        <Skeleton detail />
      ) : (
        <>
          <div className="filter-bar">
            <label>
              Environmental measure
              <select
                value={concept}
                onChange={(e) => setConcept(e.target.value)}
              >
                {concepts.map(([c, l]) => (
                  <option key={c} value={c}>
                    {l}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Company / report</th>
                  <th>Boundary and unit</th>
                  <th className="num">Previous</th>
                  <th className="num">Latest</th>
                  <th className="num">Change %</th>
                  <th className="num">Claim–number signals</th>
                  <th className="num">Assurance gaps</th>
                </tr>
              </thead>
              <tbody>
                {records.flatMap((r) => {
                  const company = rows.find((c) => c.cin === r.cin);
                  const metrics =
                    r.data?.metrics.filter((m) => m.concept === concept) ?? [];
                  return metrics.length
                    ? metrics.map((m, i) => (
                        <tr key={`${r.cin}-${i}`}>
                          <td>
                            <Link
                              className="company-link"
                              href={`/company/${encodeURIComponent(company?.name ?? r.cin)}`}
                            >
                              {company?.name}
                            </Link>
                            <small>
                              {fy(r.data?.filing.financial_year_end)} · #
                              {r.data?.filing.id}
                            </small>
                          </td>
                          <td>
                            {m.unit ?? "Unit not filed"}
                            <small>
                              {Object.entries(m.dimensions)
                                .map(([k, v]) => `${k}: ${v}`)
                                .join(", ") || "No dimensions"}
                            </small>
                          </td>
                          <td className="num">{fmt(m.series.at(-2)?.value)}</td>
                          <td className="num">{fmt(m.series.at(-1)?.value)}</td>
                          <td className="num">
                            {m.yoy_change_pct == null
                              ? "—"
                              : signed(m.yoy_change_pct)}
                          </td>
                          <td className="num">{r.data?.signals.length}</td>
                          <td className="num">
                            {r.data?.assurance_gaps.length}
                          </td>
                        </tr>
                      ))
                    : [
                        <tr key={r.cin}>
                          <td>{company?.name}</td>
                          <td colSpan={6}>
                            {r.error ?? "No matched records for this measure."}
                          </td>
                        </tr>,
                      ];
                })}
              </tbody>
            </table>
          </div>
          <p className="data-footnote">
            Compare absolute values only when units, periods and reporting
            boundaries agree. Lower absolute emissions or resource use alone
            does not establish better performance. Review counts are screening
            leads and are not adjusted for report size.
          </p>
        </>
      )}
    </Panel>
  );
}
