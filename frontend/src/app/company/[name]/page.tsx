import { notFound } from "next/navigation"
import { api } from "@/lib/api"
import { TrendsSection } from "@/components/report/TrendsSection"
import { ConsistencySection } from "@/components/report/ConsistencySection"
import { TransparencyScoreSection } from "@/components/report/TransparencyScoreSection"
import { SectorBenchmarkSection } from "@/components/report/SectorBenchmarkSection"
import { TruthAuditorSection } from "@/components/report/TruthAuditorSection"
import { AssuranceSection } from "@/components/report/AssuranceSection"
import { GreenwashingSection } from "@/components/report/GreenwashingSection"
import { SilentRemovalsSection } from "@/components/report/SilentRemovalsSection"
import { Building2, FileText, Calendar, BarChart3 } from "lucide-react"
import Link from "next/link"

export default async function CompanyReportPage({
  params,
}: {
  params: Promise<{ name: string }>
}) {
  const resolvedParams = await params;
  const decodedName = decodeURIComponent(resolvedParams.name)
  
  try {
    const [reportRes, transparencyRes, benchmarkRes, truthAuditRes] = await Promise.allSettled([
      api.getReport(decodedName),
      api.getTransparencyScore(decodedName),
      api.getSectorBenchmark(decodedName),
      api.getTruthAudit(decodedName),
    ])
    
    if (reportRes.status === "rejected") {
      throw reportRes.reason
    }
    const report = reportRes.value
    const transparencyScore = transparencyRes.status === "fulfilled" ? transparencyRes.value : null
    const sectorBenchmark = benchmarkRes.status === "fulfilled" ? benchmarkRes.value : null
    const truthAuditor = truthAuditRes.status === "fulfilled" ? truthAuditRes.value : null
    
    return (
      <div className="min-h-screen">
        {/* Header Section */}
        <header className="pt-24 pb-16 px-6 bg-card/50 border-b border-border/50">
          <div className="max-w-6xl mx-auto">
            <Link href="/companies" className="text-sm text-accent hover:underline mb-8 inline-block">
              ← Back to Companies
            </Link>
            
            <h1 className="text-5xl md:text-7xl font-medium tracking-tight mb-8">
              {report.company.name}
            </h1>
            
            <div className="flex flex-wrap gap-6 text-sm">
              <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10">
                <Building2 className="w-4 h-4 text-muted-foreground" />
                <span className="font-mono text-muted-foreground">{report.company.cin}</span>
              </div>
              <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10">
                <Calendar className="w-4 h-4 text-muted-foreground" />
                <span className="text-muted-foreground">
                  FY {new Date(report.filing.financial_year_start).getFullYear()}-{new Date(report.filing.financial_year_end).getFullYear().toString().slice(2)}
                </span>
              </div>
              <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10">
                <FileText className="w-4 h-4 text-muted-foreground" />
                <span className="text-muted-foreground">
                  <strong className="text-foreground">{report.filing.raw_fact_count}</strong> facts processed
                </span>
              </div>
            </div>
          </div>
        </header>

        {/* Report Content */}
        <main className="max-w-6xl mx-auto px-6 py-12 space-y-12">
          <TrendsSection trends={report.key_trends} />
          <ConsistencySection summary={report.consistency} />
          {transparencyScore && <TransparencyScoreSection score={transparencyScore} />}
          {sectorBenchmark ? (
            <SectorBenchmarkSection benchmark={sectorBenchmark} />
          ) : (
            <section className="py-12 border-t border-border/50">
              <h2 className="text-3xl font-serif italic mb-8">Sector Benchmark</h2>
              <div className="flex flex-col items-center justify-center text-center py-16 px-4 rounded-3xl glass-panel opacity-80">
                <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mb-6 border border-border">
                  <BarChart3 className="w-8 h-8 text-muted-foreground" />
                </div>
                <h3 className="text-xl font-medium mb-2 text-foreground">Sector Data Unavailable</h3>
                <p className="text-muted-foreground">
                  Sector benchmark data is not yet available for this company's peer group.
                </p>
              </div>
            </section>
          )}
          {truthAuditor && <TruthAuditorSection summary={truthAuditor} />}
          <AssuranceSection summary={report.assurance} />
          <GreenwashingSection signals={report.greenwashing_signals} />
          <SilentRemovalsSection removals={report.silent_removals} />
        </main>
      </div>
    )
  } catch (error) {
    notFound()
  }
}
