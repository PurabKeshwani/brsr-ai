"use client"

import { useState, useRef, useEffect } from "react"
import { api, CompanyFullReport, TransparencyScoreBreakdown, SectorBenchmarkInfo, TruthAuditorSummary, ApiError } from "@/lib/api"
import { UploadCloud, FileType, CheckCircle2, AlertCircle, RefreshCw } from "lucide-react"
import { Card } from "@/components/ui/card"
import { motion } from "framer-motion"

// Re-usable components from the report page
import { TrendsSection } from "@/components/report/TrendsSection"
import { ConsistencySection } from "@/components/report/ConsistencySection"
import { TransparencyScoreSection } from "@/components/report/TransparencyScoreSection"
import { SectorBenchmarkSection } from "@/components/report/SectorBenchmarkSection"
import { TruthAuditorSection } from "@/components/report/TruthAuditorSection"
import { AssuranceSection } from "@/components/report/AssuranceSection"
import { GreenwashingSection } from "@/components/report/GreenwashingSection"
import { SilentRemovalsSection } from "@/components/report/SilentRemovalsSection"

const LOADING_MESSAGES = [
  "Parsing XBRL facts...",
  "Auditing narrative consistency...",
  "Detecting silent removals...",
  "Calculating transparency scores...",
  "Cross-referencing reported numbers...",
  "Benchmarking against sector peers...",
]

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  const [loadingMsgIdx, setLoadingMsgIdx] = useState(0)

  const [report, setReport] = useState<CompanyFullReport | null>(null)
  const [transparencyScore, setTransparencyScore] = useState<TransparencyScoreBreakdown | null>(null)
  const [sectorBenchmark, setSectorBenchmark] = useState<SectorBenchmarkInfo | null>(null)
  const [truthAuditor, setTruthAuditor] = useState<TruthAuditorSummary | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const resultsRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let interval: NodeJS.Timeout
    if (isAnalyzing) {
      interval = setInterval(() => {
        setLoadingMsgIdx((prev) => (prev + 1) % LOADING_MESSAGES.length)
      }, 2500)
    }
    return () => clearInterval(interval)
  }, [isAnalyzing])

  useEffect(() => {
    if (report && resultsRef.current) {
      setTimeout(() => {
        resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
      }, 100)
    }
  }, [report])

  const validateAndSetFile = (selectedFile: File) => {
    setError(null)
    const name = selectedFile.name.toLowerCase()
    if (!name.endsWith(".xml") && !name.endsWith(".xbrl")) {
      setError("Invalid file type. Please upload a valid .xml or .xbrl SEBI BRSR filing.")
      setFile(null)
      return
    }
    setFile(selectedFile)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndSetFile(e.dataTransfer.files[0])
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndSetFile(e.target.files[0])
    }
  }

  const handleAnalyze = async () => {
    if (!file) return

    setIsAnalyzing(true)
    setError(null)
    setReport(null)
    setTransparencyScore(null)
    setSectorBenchmark(null)
    setTruthAuditor(null)
    setLoadingMsgIdx(0)

    try {
      // 1. Upload and ingest
      const uploadedReport = await api.uploadAndAnalyze(file)
      
      // 2. Fetch the extra sections concurrently based on the ingested company's name
      const name = uploadedReport.company.name
      const [transparencyRes, benchmarkRes, truthAuditRes] = await Promise.allSettled([
        api.getTransparencyScore(name),
        api.getSectorBenchmark(name),
        api.getTruthAudit(name),
      ])

      setReport(uploadedReport)
      if (transparencyRes.status === "fulfilled") setTransparencyScore(transparencyRes.value)
      if (benchmarkRes.status === "fulfilled") setSectorBenchmark(benchmarkRes.value)
      if (truthAuditRes.status === "fulfilled") setTruthAuditor(truthAuditRes.value)

    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError("An unexpected error occurred while analyzing the filing.")
      }
    } finally {
      setIsAnalyzing(false)
    }
  }

  const reset = () => {
    setFile(null)
    setReport(null)
    setError(null)
    if (fileInputRef.current) fileInputRef.current.value = ""
  }

  return (
    <div className="min-h-screen py-24 px-6">
      <div className="max-w-4xl mx-auto mb-16">
        <header className="mb-12">
          <h1 className="text-5xl font-medium tracking-tight mb-4">
            Analyze a <span className="font-serif italic text-accent">Filing</span>
          </h1>
          <p className="text-xl text-muted-foreground">
            Upload a company's BRSR filing for automated auditing and scoring.
          </p>
        </header>

        {/* Why XBRL Callout */}
        <div className="mb-8 p-6 rounded-2xl bg-white/5 border border-white/10 text-muted-foreground leading-relaxed">
          <strong className="text-foreground font-medium block mb-2 text-lg">Why only XML/XBRL?</strong>
          This system analyzes SEBI's officially-tagged XBRL filings — not PDFs — because XBRL data is structured and machine-verifiable, eliminating the extraction errors and hallucinations common in PDF/OCR-based ESG tools. 
          Download your company's XBRL file from the NSE/BSE filing portal to analyze it here.
        </div>

        {/* Upload Zone */}
        {!report && !isAnalyzing && (
          <div className="space-y-6">
            <div 
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              onClick={() => !file && fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-3xl p-16 text-center transition-all duration-300 ${
                isDragging ? "border-accent bg-accent/10 scale-[1.02] shadow-[0_0_20px_rgba(16,185,129,0.2)]" : 
                file ? "border-white/20 bg-white/5" : 
                "border-border/50 hover:border-accent/30 hover:bg-white/5 hover:scale-[1.01] hover:shadow-[0_0_15px_rgba(16,185,129,0.1)] cursor-pointer"
              }`}
            >
              <input 
                type="file" 
                ref={fileInputRef} 
                className="hidden" 
                accept=".xml,.xbrl" 
                onChange={handleChange}
              />
              
              {file ? (
                <div className="flex flex-col items-center">
                  <div className="w-16 h-16 rounded-full bg-emerald-500/10 flex items-center justify-center mb-6">
                    <FileType className="w-8 h-8 text-emerald-500" />
                  </div>
                  <h3 className="text-2xl font-medium mb-2">{file.name}</h3>
                  <p className="text-muted-foreground mb-8">{(file.size / 1024).toFixed(1)} KB</p>
                  <div className="flex gap-4">
                    <button 
                      onClick={(e) => { e.stopPropagation(); reset() }}
                      className="px-6 py-3 rounded-full bg-white/10 hover:bg-white/15 text-foreground font-medium transition-all duration-300 active:scale-95"
                    >
                      Clear
                    </button>
                    <button 
                      onClick={(e) => { e.stopPropagation(); handleAnalyze() }}
                      className="px-6 py-3 rounded-full bg-accent hover:bg-accent/90 text-accent-foreground font-medium transition-all duration-300 shadow-[0_0_20px_rgba(16,185,129,0.3)] hover:shadow-[0_0_30px_rgba(16,185,129,0.5)] active:scale-95"
                    >
                      Analyze Filing
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center">
                  <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mb-6 border border-white/10">
                    <UploadCloud className="w-8 h-8 text-muted-foreground" />
                  </div>
                  <h3 className="text-xl font-medium mb-2">Drag & drop your XBRL file here</h3>
                  <p className="text-muted-foreground">or click to browse from your computer (only .xml, .xbrl)</p>
                </div>
              )}
            </div>

            {error && (
              <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-rose-500 shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-rose-500 font-medium mb-1">Upload Failed</h4>
                  <p className="text-sm text-rose-400">{error}</p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Loading State */}
        {isAnalyzing && (
          <Card className="p-16 glass-panel flex flex-col items-center justify-center text-center">
            <div className="w-20 h-20 rounded-full bg-accent/10 flex items-center justify-center mb-8 relative">
              <div className="absolute inset-0 rounded-full border border-accent/30 animate-ping opacity-40" />
              <RefreshCw className="w-10 h-10 text-accent animate-spin duration-3000" />
            </div>
            
            <div className="h-8 relative w-full overflow-hidden">
              <motion.div
                key={loadingMsgIdx}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.5 }}
                className="absolute inset-0 text-xl font-medium text-foreground font-serif italic"
              >
                {LOADING_MESSAGES[loadingMsgIdx]}
              </motion.div>
            </div>
          </Card>
        )}
      </div>

      {/* Inline Report rendering */}
      {report && (
        <div ref={resultsRef} className="max-w-6xl mx-auto pt-12 border-t border-border/50 animate-in fade-in slide-in-from-bottom-12 duration-1000">
          <div className="mb-12 flex justify-between items-end">
            <div>
              <div className="flex items-center gap-2 mb-4 text-emerald-500 font-medium bg-emerald-500/10 border border-emerald-500/20 px-4 py-1.5 rounded-full inline-flex">
                <CheckCircle2 className="w-4 h-4" /> Filing processed successfully
              </div>
              <h2 className="text-5xl font-medium tracking-tight">{report.company.name}</h2>
            </div>
            <button 
              onClick={reset}
              className="px-5 py-2.5 rounded-full bg-white/5 border border-white/10 hover:bg-white/10 text-sm font-medium transition-colors"
            >
              Analyze Another
            </button>
          </div>

          <div className="space-y-12">
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
          </div>
        </div>
      )}
    </div>
  )
}
