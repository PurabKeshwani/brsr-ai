"use client"

import { GreenwashingSignalItem } from "@/lib/api"
import { Badge } from "@/components/ui/badge"
import { ShieldCheck, Target, ArrowRight } from "lucide-react"

export function GreenwashingSection({ signals }: { signals: GreenwashingSignalItem[] }) {
  if (!signals || signals.length === 0) {
    return (
      <section className="py-12 border-t border-border/50">
        <div className="flex flex-col items-center justify-center text-center">
          <div className="w-24 h-24 rounded-full bg-emerald-500/10 flex items-center justify-center mb-8 relative">
            <div className="absolute inset-0 rounded-full border border-emerald-500/20 animate-ping opacity-20" />
            <ShieldCheck className="w-12 h-12 text-emerald-500" />
          </div>
          <h2 className="text-3xl font-serif italic mb-4">No Greenwashing Signals Detected</h2>
          <p className="text-xl text-muted-foreground max-w-2xl">
            Our engine analyzed the company's narrative disclosures against their reported XBRL metrics and found no significant contradictions.
          </p>
        </div>
      </section>
    )
  }

  return (
    <section className="py-12 border-t border-border/50">
      <div className="mb-12">
        <h2 className="text-3xl font-serif italic mb-4 text-orange-400">Greenwashing Signals</h2>
        <p className="text-xl text-muted-foreground">Discrepancies found between narrative claims and filed data.</p>
      </div>

      <div className="space-y-8">
        {signals.map((signal, idx) => (
          <div 
            key={idx} 
            className={`glass-panel rounded-3xl p-8 md:p-12 relative overflow-hidden group transition-colors duration-500 hover:bg-card/90 ${
              signal.severity === "notable" ? "border-orange-500/30" : "border-yellow-500/20"
            }`}
          >
            <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-orange-500/50 to-transparent" />
            
            <div className="flex flex-wrap items-center gap-3 mb-8">
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

            <div className="grid grid-cols-1 md:grid-cols-12 gap-12">
              <div className="md:col-span-8">
                <div className="mb-8">
                  <div className="text-xs text-muted-foreground uppercase tracking-widest mb-4 flex items-center gap-2">
                    <Target className="w-4 h-4" /> Narrative Claim
                  </div>
                  <blockquote className="text-2xl md:text-3xl font-serif italic text-foreground leading-relaxed">
                    "{signal.matched_sentence}"
                  </blockquote>
                </div>
                
                <div className="p-6 rounded-2xl bg-muted/50 border border-border">
                  <div className="text-sm font-medium text-muted-foreground mb-2">Analysis</div>
                  <p className="text-lg leading-relaxed">{signal.rationale}</p>
                </div>
              </div>

              <div className="md:col-span-4">
                <div className="p-6 rounded-2xl bg-muted border border-border h-full flex flex-col justify-center">
                  <div className="text-sm text-muted-foreground mb-6">Filed Data Reality</div>
                  
                  <div className="space-y-6">
                    <div>
                      <div className="text-sm text-muted-foreground mb-1">Previous Year</div>
                      <div className="text-2xl font-mono text-muted-foreground">
                        {signal.previous_value?.toLocaleString() ?? "N/A"}
                      </div>
                    </div>
                    <div className="flex justify-center -my-2 opacity-50">
                      <ArrowRight className="w-6 h-6 rotate-90 md:rotate-0" />
                    </div>
                    <div>
                      <div className="text-sm text-muted-foreground mb-1">Latest Year</div>
                      <div className="text-3xl font-mono text-foreground font-medium">
                        {signal.latest_value?.toLocaleString() ?? "N/A"}
                      </div>
                    </div>
                    {signal.yoy_change_pct !== null && (
                      <div className="pt-4 border-t border-border/50">
                        <div className="text-sm font-medium text-orange-400">
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
    </section>
  )
}
