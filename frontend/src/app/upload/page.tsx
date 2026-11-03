"use client";
import { useState } from "react";
import Link from "next/link";
import { Upload, FileText, ArrowUpRight } from "lucide-react";
import { api, type CompanyFullReport } from "@/lib/api";
import { PageHead, Panel, Skeleton } from "@/components/workspace/Shared";
export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [report, setReport] = useState<CompanyFullReport | null>(null),
    [drag, setDrag] = useState(false);
  function choose(f: File | undefined) {
    if (!f) return;
    setError("");
    setReport(null);
    if (!/\.(xml|xbrl)$/i.test(f.name)) {
      setError("Choose a SEBI BRSR .xml or .xbrl filing.");
      return;
    }
    if (f.size > 20 * 1024 * 1024) {
      setError("Choose a filing smaller than 20 MB.");
      return;
    }
    setFile(f);
  }
  async function analyze() {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      setReport(await api.uploadAndAnalyze(file));
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "The filing could not be analyzed. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="workspace-page">
      <PageHead
        title="Analyze a filing"
        description="Add an official SEBI BRSR XBRL filing to the research workspace."
      />
      <div className="analysis-grid">
        <Panel
          title="Upload structured disclosure"
          note="XML or XBRL · up to 20 MB"
        >
          <div
            className="upload-zone"
            data-dragging={drag}
            onDragOver={(e) => {
              e.preventDefault();
              if (!busy) setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDrag(false);
              if (!busy) choose(e.dataTransfer.files[0]);
            }}
          >
            <Upload size={28} strokeWidth={1.3} />
            <strong>Drop a BRSR filing here</strong>
            <p className="data-footnote">
              Or choose a file from your computer.
            </p>
            <input
              aria-label="Choose BRSR filing"
              type="file"
              accept=".xml,.xbrl"
              disabled={busy}
              onChange={(e) => choose(e.target.files?.[0])}
            />
            {file && (
              <div className="upload-info">
                <FileText size={16} />
                {file.name}
                <span>{(file.size / 1024).toFixed(1)} KB</span>
              </div>
            )}
            <button
              className="btn btn-primary"
              disabled={!file || busy}
              onClick={analyze}
            >
              {busy ? "Analyzing filing…" : "Upload and analyze"}
            </button>
          </div>
          {error && (
            <div role="alert" className="scope-note">
              {error}
            </div>
          )}
          {report && (
            <div className="scope-note">
              <span>Analysis ready</span>
              {report.company.name} ·{" "}
              {report.filing.raw_fact_count.toLocaleString()} filed facts
              <Link
                className="text-action"
                href={`/company/${encodeURIComponent(report.company.name)}?filing=${report.filing.id}`}
              >
                Open detailed analysis <ArrowUpRight size={14} />
              </Link>
            </div>
          )}
        </Panel>
        <Panel
          title="What this adds"
          note="Structured evidence stays linked to the original concepts and reporting periods."
        >
          <dl className="method-definitions">
            <dt>Source-linked company detail</dt>
            <dd>
              Review raw facts, matched numeric history, assurance and
              claim–evidence signals in the same workspace.
            </dd>
            <dt>Reporting periods</dt>
            <dd>
              A filing can include both current and previous-year facts.
              Separate report score histories require separately scored reports.
            </dd>
            <dt>Why XBRL?</dt>
            <dd>
              Official taxonomy tags preserve units, periods and dimensional
              context. This workspace reads structured filings rather than
              inferring values from PDF layouts.
            </dd>
            <dt>Saved comparison population</dt>
            <dd>
              Ingested filings are available immediately. Corpus comparisons use
              the saved research score export, so newly ingested companies can
              appear without a saved comparison score.
            </dd>
          </dl>
        </Panel>
      </div>
      {busy && (
        <div aria-live="polite">
          <p className="data-footnote">
            The server is ingesting and analyzing the selected filing. Results
            will appear here when processing completes.
          </p>
          <Skeleton detail />
        </div>
      )}
    </div>
  );
}
