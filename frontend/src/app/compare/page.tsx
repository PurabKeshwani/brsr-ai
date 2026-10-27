"use client"

import { useState, useEffect, useMemo } from "react"
import { api, CompanySummary, CompareCompanyResult, ComparisonResponse } from "@/lib/api"
import { Card } from "@/components/ui/card"
import { X, Search, Plus, ArrowDown, ArrowUp, Minus, Star, ShieldCheck, AlertTriangle } from "lucide-react"
import { motion, AnimatePresence } from "framer-motion"

function getScoreColorClass(score: number) {
  if (score < 40) return "bg-rose-500"
  if (score < 65) return "bg-amber-500"
  return "bg-emerald-500"
}

function getScoreTextColor(score: number) {
  if (score < 40) return "text-rose-500"
  if (score < 65) return "text-amber-500"
  return "text-emerald-500"
}

const TREND_METRICS = ["Scope 1 Emissions", "Scope 2 Emissions", "Scope 3 Emissions", "Total Waste Generated", "Total Water Consumption", "Total Energy Consumed"]

export default function ComparePage() {
  const [allCompanies, setAllCompanies] = useState<CompanySummary[]>([])
  const [search, setSearch] = useState("")
  const [selectedNames, setSelectedNames] = useState<string[]>([])
  
  const [isComparing, setIsComparing] = useState(false)
  const [results, setResults] = useState<ComparisonResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.listCompanies().then(setAllCompanies).catch(console.error)
  }, [])

  const filteredCompanies = useMemo(() => {
    return allCompanies.filter(c => 
      c.name.toLowerCase().includes(search.toLowerCase()) && 
      !selectedNames.includes(c.name)
    ).slice(0, 5)
  }, [allCompanies, search, selectedNames])

  const toggleSelect = (name: string) => {
    if (selectedNames.includes(name)) {
      setSelectedNames(prev => prev.filter(n => n !== name))
    } else {
      if (selectedNames.length >= 5) return
      setSelectedNames(prev => [...prev, name])
      setSearch("")
    }
  }

  const handleCompare = async () => {
    if (selectedNames.length < 2) return
    setIsComparing(true)
    setError(null)
    setResults(null)
    try {
      const res = await api.compareCompanies(selectedNames)
      // Map requested names to results (in case some were not returned at all)
      const mappedResults: CompareCompanyResult[] = selectedNames.map(name => {
        const found = res.companies.find(c => c.company_name === name)
        return found || { company_name: name, error: "not found" }
      })
      setResults({ companies: mappedResults })
    } catch (err: any) {
      setError(err.message || "Failed to fetch comparison data.")
    } finally {
      setIsComparing(false)
    }
  }

  // Pre-calculate best performers
  const bestScore = useMemo(() => {
    if (!results) return -1
    const scores = results.companies.map(c => c.transparency_score || -1)
    return Math.max(...scores)
  }, [results])

  const bestTrends = useMemo(() => {
    if (!results) return {}
    const bests: Record<string, number> = {}
    TREND_METRICS.forEach(metric => {
      let minChange = Infinity
      results.companies.forEach(c => {
        const t = c.trends?.[metric]
        if (t && t.yoy_change_pct !== null && t.yoy_change_pct < minChange) {
          minChange = t.yoy_change_pct
        }
      })
      bests[metric] = minChange
    })
    return bests
  }, [results])

  const bestAuditor = useMemo(() => {
    if (!results) return -1
    let minFlags = Infinity
    results.companies.forEach(c => {
      if (c.error) return
      const flags = (c.claim_evidence_contradictions || 0) + (c.silent_removals || 0)
      if (flags < minFlags) minFlags = flags
    })
    return minFlags
  }, [results])

  return (
    <div className="min-h-screen py-24 overflow-x-hidden">
      <div className="max-w-6xl mx-auto mb-16 px-6">
        <header className="mb-12">
          <h1 className="text-5xl font-medium tracking-tight mb-4">
            Compare <span className="font-serif italic text-accent">Companies</span>
          </h1>
          <p className="text-xl text-muted-foreground">
            Select up to 5 companies to compare their BRSR disclosures side-by-side.
          </p>
        </header>

        {/* Company Picker */}
        <div className="p-6 rounded-3xl glass-panel relative z-10 mb-8 border border-border/50">
          <div className="flex flex-wrap gap-2 mb-6 min-h-[40px]">
            <AnimatePresence>
              {selectedNames.map(name => (
                <motion.div 
                  key={name}
                  initial={{ scale: 0.8, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  exit={{ scale: 0.8, opacity: 0 }}
                  className="flex items-center gap-2 px-4 py-2 bg-white/10 rounded-full text-sm font-medium border border-white/5 hover:border-white/20 transition-colors"
                >
                  {name}
                  <button onClick={() => toggleSelect(name)} className="hover:bg-white/20 rounded-full p-0.5 transition-colors">
                    <X className="w-4 h-4" />
                  </button>
                </motion.div>
              ))}
            </AnimatePresence>
            {selectedNames.length === 0 && (
              <div className="text-muted-foreground text-sm flex items-center">
                No companies selected. Search below to add them.
              </div>
            )}
          </div>

          <div className="relative">
            <div className="flex items-center gap-3 bg-black/40 border border-white/10 rounded-full px-4 py-2">
              <Search className="w-5 h-5 text-muted-foreground" />
              <input
                type="text"
                placeholder={selectedNames.length >= 5 ? "Maximum of 5 companies reached" : "Search company name..."}
                value={search}
                onChange={e => setSearch(e.target.value)}
                disabled={selectedNames.length >= 5}
                className="bg-transparent border-none outline-none flex-1 py-2 text-foreground placeholder:text-muted-foreground"
              />
            </div>

            {search && filteredCompanies.length > 0 && (
              <div className="absolute top-full left-0 w-full mt-2 bg-card border border-border/50 rounded-xl overflow-hidden shadow-2xl z-20">
                {filteredCompanies.map(c => (
                  <button
                    key={c.id}
                    onClick={() => toggleSelect(c.name)}
                    className="w-full text-left px-6 py-4 hover:bg-white/5 flex items-center justify-between border-b border-white/5 last:border-0 transition-colors"
                  >
                    <span>{c.name}</span>
                    <Plus className="w-5 h-5 text-muted-foreground" />
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="mt-8 flex justify-end">
            <button
              onClick={handleCompare}
              disabled={selectedNames.length < 2 || isComparing}
              className={`px-8 py-3 rounded-full font-medium transition-all duration-300 ${
                selectedNames.length >= 2 
                  ? "bg-accent hover:bg-accent/90 text-accent-foreground shadow-[0_0_20px_rgba(16,185,129,0.3)] hover:shadow-[0_0_30px_rgba(16,185,129,0.5)] active:scale-95 cursor-pointer" 
                  : "bg-white/5 text-muted-foreground cursor-not-allowed"
              }`}
            >
              {isComparing ? "Comparing..." : "Compare"}
            </button>
          </div>
          
          {error && <div className="mt-4 text-rose-500 text-sm text-right">{error}</div>}
        </div>
      </div>

      {/* Results Layout */}
      {results && (
        <div className="w-full overflow-x-auto pb-12 px-6 scrollbar-thin">
          <div 
            className="grid gap-6 mx-auto" 
            style={{ 
              gridTemplateColumns: `repeat(${results.companies.length}, minmax(300px, 1fr))`,
              width: "max-content",
              minWidth: "100%"
            }}
          >
            {/* Headers */}
            {results.companies.map((c, i) => (
              <div key={`header-${i}`} className="sticky top-0 z-10 bg-background/90 backdrop-blur-md pb-4 border-b border-border">
                <h3 className="text-xl font-medium mb-1 truncate px-2" title={c.company_name}>{c.company_name}</h3>
                <div className="text-xs text-muted-foreground font-mono px-2">{c.cin || " "}</div>
              </div>
            ))}

            {/* Row 1: Transparency Score */}
            {results.companies.map((c, i) => {
              if (c.error) {
                return (
                  <Card key={`score-${i}`} className="p-6 glass-panel flex flex-col items-center justify-center opacity-50 h-[300px]">
                    <div className="text-muted-foreground text-sm">Not found in database</div>
                  </Card>
                )
              }
              const score = c.transparency_score || 0
              const isBest = score === bestScore && score > 0
              const colorCls = getScoreTextColor(score)
              const bgCls = getScoreColorClass(score)
              
              const radius = 40
              const circumference = 2 * Math.PI * radius
              const offset = circumference - (score / 100) * circumference

              return (
                <Card key={`score-${i}`} className={`p-6 glass-panel flex flex-col relative transition-colors ${isBest ? "border-accent/50 bg-accent/5" : ""}`}>
                  {isBest && <Star className="w-4 h-4 text-accent absolute top-4 right-4 fill-accent" />}
                  <div className="text-sm text-muted-foreground uppercase tracking-wider mb-6">Transparency Score</div>
                  
                  <div className="flex flex-col items-center mb-8">
                    <div className="relative w-32 h-32 flex items-center justify-center">
                      <svg className="absolute inset-0 w-full h-full -rotate-90">
                        <circle cx="64" cy="64" r={radius} stroke="var(--border)" strokeWidth="8" fill="none" />
                        <motion.circle
                          cx="64" cy="64" r={radius} stroke="currentColor" strokeWidth="8" fill="none" strokeLinecap="round"
                          className={colorCls}
                          initial={{ strokeDashoffset: circumference }}
                          animate={{ strokeDashoffset: offset }}
                          transition={{ duration: 1, ease: "easeOut" }}
                          style={{ strokeDasharray: circumference }}
                        />
                      </svg>
                      <div className={`text-3xl font-medium ${colorCls}`}>{Math.round(score)}</div>
                    </div>
                  </div>

                  {/* Stacked Bar for Sub-components */}
                  <div className="mt-auto space-y-3 w-full">
                    <div className="flex h-2 w-full bg-white/10 rounded-full overflow-hidden">
                      <div className="bg-emerald-500" style={{ width: `${(c.completeness_pct || 0) * 0.4}%` }} title="Completeness (40%)" />
                      <div className="bg-amber-500" style={{ width: `${(c.specificity_pct || 0) * 0.3}%` }} title="Specificity (30%)" />
                      <div className="bg-blue-500" style={{ width: `${(c.clarity_pct || 0) * 0.2}%` }} title="Clarity (20%)" />
                      <div className="bg-purple-500" style={{ width: `${(c.sdg_alignment_pct || 0) * 0.1}%` }} title="SDG Alignment (10%)" />
                    </div>
                    <div className="flex justify-between text-[10px] text-muted-foreground uppercase tracking-widest px-1">
                      <span>Cmp</span><span>Spc</span><span>Clr</span><span>SDG</span>
                    </div>
                  </div>
                </Card>
              )
            })}

            {/* Row 2: Key Trends */}
            <div className="col-span-full mt-12 mb-4">
              <h3 className="text-2xl font-serif italic">Key Trends</h3>
            </div>
            
            {results.companies.map((c, i) => {
              if (c.error) return <div key={`trends-${i}`} className="opacity-50 text-sm text-center">N/A</div>
              return (
                <div key={`trends-${i}`} className="space-y-4">
                  {TREND_METRICS.map(metric => {
                    const t = c.trends?.[metric]
                    const val = t?.latest_value
                    const change = t?.yoy_change_pct
                    const isBest = change !== null && change !== undefined && change === bestTrends[metric] && change < Infinity
                    const isIncrease = change !== null && change !== undefined && change > 0
                    const isDecrease = change !== null && change !== undefined && change < 0
                    const color = isIncrease ? "text-amber-500" : isDecrease ? "text-emerald-500" : "text-muted-foreground"
                    
                    return (
                      <Card key={metric} className={`p-4 glass-panel flex flex-col justify-center relative ${isBest ? "border-emerald-500/30 bg-emerald-500/5" : ""}`}>
                        {isBest && <Star className="w-3 h-3 text-emerald-500 absolute top-3 right-3 fill-emerald-500" />}
                        <div className="text-[11px] text-muted-foreground uppercase tracking-wider mb-2 truncate" title={metric}>{metric}</div>
                        <div className="flex items-baseline justify-between">
                          <span className="text-xl font-medium">{val !== null && val !== undefined ? val.toLocaleString() : "N/A"}</span>
                          {change !== null && change !== undefined && (
                            <span className={`text-xs font-semibold flex items-center ${color}`}>
                              {isIncrease ? <ArrowUp className="w-3 h-3 mr-0.5" /> : isDecrease ? <ArrowDown className="w-3 h-3 mr-0.5" /> : <Minus className="w-3 h-3 mr-0.5" />}
                              {Math.abs(change)}%
                            </span>
                          )}
                        </div>
                      </Card>
                    )
                  })}
                </div>
              )
            })}

            {/* Row 3: Truth Auditor */}
            <div className="col-span-full mt-12 mb-4">
              <h3 className="text-2xl font-serif italic">Truth Auditor Summary</h3>
            </div>

            {results.companies.map((c, i) => {
              if (c.error) return <div key={`audit-${i}`} className="opacity-50 text-sm text-center">N/A</div>
              
              const flags = (c.claim_evidence_contradictions || 0) + (c.silent_removals || 0)
              const isBest = flags === bestAuditor
              const isZero = flags === 0
              const isWorst = !isBest && flags > 0

              return (
                <Card key={`audit-${i}`} className={`p-6 transition-colors ${isZero ? "bg-emerald-500/5 border-emerald-500/20" : isWorst ? "bg-white/2 border-white/5 opacity-70" : "glass-panel"} relative flex flex-col`}>
                  {isZero && <ShieldCheck className="w-5 h-5 text-emerald-500 absolute top-4 right-4" />}
                  
                  <div className="space-y-6">
                    <div>
                      <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-2">
                        <AlertTriangle className="w-3.5 h-3.5" /> Contradictions
                      </div>
                      <div className={`text-3xl font-medium ${c.claim_evidence_contradictions ? "text-amber-500" : "text-emerald-500"}`}>
                        {c.claim_evidence_contradictions || 0}
                      </div>
                    </div>
                    
                    <div className="pt-6 border-t border-border/50">
                      <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-2">
                        <AlertTriangle className="w-3.5 h-3.5" /> Silent Removals
                      </div>
                      <div className={`text-3xl font-medium ${c.silent_removals ? "text-rose-400" : "text-emerald-500"}`}>
                        {c.silent_removals || 0}
                      </div>
                    </div>
                  </div>
                </Card>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
