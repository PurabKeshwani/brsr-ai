"use client"

import { useState } from "react"
import { TruthAuditorSummary } from "@/lib/api"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { AlertTriangle, FileText, Ghost, EyeOff, Target, ArrowRight, History, ChevronDown, ChevronUp } from "lucide-react"
import { motion, AnimatePresence } from "framer-motion"
import { AnimatedNumber } from "@/components/ui/animated-number"

export function TruthAuditorSection({
  summary,
}: {
  summary: TruthAuditorSummary
}) {
  const [expandedSection, setExpandedSection] = useState<"contradictions" | "removals" | null>(null)

  const toggleSection = (section: "contradictions" | "removals") => {
    setExpandedSection(prev => prev === section ? null : section)
  }

  const {
    total_narrative_segments_checked,
    claim_evidence_contradictions_count,
    silent_removals_count,
    vague_segments_count,
    has_high_confidence_contradiction,
    claim_evidence_details,
    silent_removal_details,
  } = summary

  return (
    <section className="py-12 border-t border-border/50">
      <div className="mb-8">
        <h2 className="text-3xl font-serif italic mb-2">Truth Auditor</h2>
        <p className="text-muted-foreground">Unified verification of narrative claims against reported data.</p>
      </div>

      {has_high_confidence_contradiction && (
        <div className="mb-8 p-4 rounded-xl bg-amber-900/20 border border-amber-500/30 flex items-start gap-4">
          <AlertTriangle className="w-6 h-6 text-amber-500 shrink-0 mt-0.5" />
          <div>
            <h4 className="text-amber-500 font-medium mb-1">High-Confidence Contradiction Detected</h4>
            <p className="text-sm text-amber-500/80">
              The Truth Auditor found a direct contradiction between a narrative claim and the company's filed numerical data. Review the Claim-Evidence Contradictions below for details.
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        {/* Contradictions Card */}
        <Card 
          className={`p-6 glass-panel flex flex-col transition-all duration-300 ${claim_evidence_details.length > 0 ? "cursor-pointer hover:bg-white/5 border-white/20" : "opacity-80"}`}
          onClick={() => claim_evidence_details.length > 0 && toggleSection("contradictions")}
        >
          <div className="flex justify-between items-start mb-4">
            <div className="p-2 rounded-lg bg-orange-500/10 text-orange-400">
              <FileText className="w-5 h-5" />
            </div>
            {claim_evidence_details.length > 0 && (
              <div className="text-muted-foreground">
                {expandedSection === "contradictions" ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
              </div>
            )}
          </div>
          <div className="text-3xl font-medium tracking-tight mb-1">
            <AnimatedNumber value={claim_evidence_contradictions_count} />
          </div>
          <div className="text-sm text-muted-foreground font-medium uppercase tracking-wider">Claim-Evidence Contradictions</div>
        </Card>

        {/* Silent Removals Card */}
        <Card 
          className={`p-6 glass-panel flex flex-col transition-all duration-300 ${silent_removal_details.length > 0 ? "cursor-pointer hover:bg-white/5 border-white/20" : "opacity-80"}`}
          onClick={() => silent_removal_details.length > 0 && toggleSection("removals")}
        >
          <div className="flex justify-between items-start mb-4">
            <div className="p-2 rounded-lg bg-rose-500/10 text-rose-400">
              <Ghost className="w-5 h-5" />
            </div>
            {silent_removal_details.length > 0 && (
              <div className="text-muted-foreground">
                {expandedSection === "removals" ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
              </div>
            )}
          </div>
          <div className="text-3xl font-medium tracking-tight mb-1">
            <AnimatedNumber value={silent_removals_count} delay={100} />
          </div>
          <div className="text-sm text-muted-foreground font-medium uppercase tracking-wider">Silent Removals</div>
        </Card>

        {/* Vague Segments Card */}
        <Card className="p-6 glass-panel flex flex-col opacity-80">
          <div className="flex justify-between items-start mb-4">
            <div className="p-2 rounded-lg bg-slate-500/10 text-slate-400">
              <EyeOff className="w-5 h-5" />
            </div>
          </div>
          <div className="text-3xl font-medium tracking-tight mb-1">
            <AnimatedNumber value={vague_segments_count} delay={200} />
          </div>
          <div className="text-sm text-muted-foreground font-medium uppercase tracking-wider">Vague/Unsubstantiated</div>
        </Card>
      </div>

      {total_narrative_segments_checked < 10 && (
        <div className="mb-8 text-xs text-muted-foreground text-center">
          * Note: This audit is based on a limited number of disclosed segments ({total_narrative_segments_checked} total).
        </div>
      )}

      {/* Expandable Details Area */}
      <AnimatePresence mode="wait">
        {expandedSection === "contradictions" && claim_evidence_details.length > 0 && (
          <motion.div 
            key="contradictions"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="space-y-6 pt-4 border-t border-border/30">
              <h3 className="text-xl font-medium mb-6 text-orange-400">Evidence Details: Contradictions</h3>
              {claim_evidence_details.map((signal, idx) => (
                <div 
                  key={idx} 
                  className={`glass-panel rounded-3xl p-6 md:p-8 relative overflow-hidden group ${
                    signal.severity === "notable" ? "border-orange-500/30" : "border-yellow-500/20"
                  }`}
                >
                  <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-orange-500/50 to-transparent" />
                  
                  <div className="flex flex-wrap items-center gap-3 mb-6">
                    <Badge variant={signal.severity === "notable" ? "notable" : "worth_reviewing"} className="uppercase tracking-wider">
                      {signal.severity.replace("_", " ")}
                    </Badge>
                    <span className="text-sm font-mono text-muted-foreground">{signal.concept}</span>
                    {signal.assurance_level && (
                      <Badge variant="default" className="text-muted-foreground bg-white/5 border-white/10">
                        {signal.assurance_level} Assurance
                      </Badge>
                    )}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-12 gap-8">
                    <div className="md:col-span-8">
                      <div className="mb-6">
                        <div className="text-xs text-muted-foreground uppercase tracking-widest mb-3 flex items-center gap-2">
                          <Target className="w-4 h-4" /> Narrative Claim
                        </div>
                        <blockquote className="text-xl md:text-2xl font-serif italic text-foreground leading-relaxed">
                          "{signal.matched_sentence}"
                        </blockquote>
                      </div>
                      
                      <div className="p-5 rounded-2xl bg-muted/50 border border-border">
                        <div className="text-sm font-medium text-muted-foreground mb-2">Analysis</div>
                        <p className="text-base leading-relaxed">{signal.rationale}</p>
                      </div>
                    </div>

                    <div className="md:col-span-4">
                      <div className="p-5 rounded-2xl bg-muted border border-border h-full flex flex-col justify-center">
                        <div className="text-sm text-muted-foreground mb-4">Filed Data Reality</div>
                        <div className="space-y-4">
                          <div>
                            <div className="text-xs text-muted-foreground mb-1">Previous Year</div>
                            <div className="text-xl font-mono text-muted-foreground">
                              {signal.previous_value?.toLocaleString() ?? "N/A"}
                            </div>
                          </div>
                          <div className="flex -my-2 opacity-50">
                            <ArrowRight className="w-5 h-5 rotate-90 md:rotate-0" />
                          </div>
                          <div>
                            <div className="text-xs text-muted-foreground mb-1">Latest Year</div>
                            <div className="text-2xl font-mono text-foreground font-medium">
                              {signal.latest_value?.toLocaleString() ?? "N/A"}
                            </div>
                          </div>
                          {signal.yoy_change_pct !== null && (
                            <div className="pt-3 border-t border-border/50">
                              <div className="text-xs font-medium text-orange-400">
                                {signal.yoy_change_pct > 0 ? "+" : ""}{signal.yoy_change_pct}% Change
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}

        {expandedSection === "removals" && silent_removal_details.length > 0 && (
          <motion.div 
            key="removals"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="space-y-6 pt-4 border-t border-border/30">
              <h3 className="text-xl font-medium mb-6 text-rose-400">Evidence Details: Silent Removals</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {silent_removal_details.map((removal, idx) => (
                  <div key={idx} className="p-6 rounded-2xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors relative overflow-hidden group">
                    <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-rose-500/50 to-transparent" />
                    
                    <div className="flex items-center gap-2 mb-4 text-sm font-mono text-rose-300">
                      <History className="w-4 h-4" />
                      {removal.prior_year_period}
                    </div>
                    
                    <h4 className="text-lg font-medium mb-2">{removal.concept}</h4>
                    <div className="text-sm text-muted-foreground mb-4">Context: {removal.context}</div>
                    
                    <div className="p-4 bg-black/30 rounded-xl mb-4 border border-white/10">
                      <div className="text-xs text-muted-foreground mb-1">Prior Disclosed Value</div>
                      <div className="font-mono text-foreground">{removal.prior_year_value}</div>
                    </div>
                    
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      {removal.rationale}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  )
}
