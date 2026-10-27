"use client"

import { AssuranceSummary } from "@/lib/api"
import { Card } from "@/components/ui/card"
import { AnimatedNumber } from "@/components/ui/animated-number"
import { Badge } from "@/components/ui/badge"
import { FileQuestion } from "lucide-react"

export function AssuranceSection({ summary }: { summary: AssuranceSummary }) {
  if (!summary) return null

  if (summary.total_disclosure_areas === 0) {
    return (
      <section className="py-12 border-t border-border/50">
        <h2 className="text-3xl font-serif italic mb-8">Third-Party Assurance</h2>
        <div className="flex flex-col items-center justify-center text-center py-16 px-4 rounded-3xl glass-panel opacity-80">
          <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mb-6 border border-white/10">
            <FileQuestion className="w-8 h-8 text-muted-foreground" />
          </div>
          <h3 className="text-xl font-medium mb-2 text-foreground">No Assurance Disclosures</h3>
          <p className="text-muted-foreground">
            No assurance-related disclosures found in this filing.
          </p>
        </div>
      </section>
    )
  }

  const reasonablePct = summary.total_disclosure_areas ? (summary.reasonable_count / summary.total_disclosure_areas) * 100 : 0
  const limitedPct = summary.total_disclosure_areas ? (summary.limited_count / summary.total_disclosure_areas) * 100 : 0
  const unassuredPct = summary.total_disclosure_areas ? (summary.unassured_count / summary.total_disclosure_areas) * 100 : 0

  return (
    <section className="py-12 border-t border-border/50">
      <h2 className="text-3xl font-serif italic mb-8">Third-Party Assurance</h2>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-12">
        <div className="lg:col-span-1">
          <div className="text-8xl font-light tracking-tighter text-accent mb-2">
            <AnimatedNumber value={summary.reasonable_assurance_pct} />%
          </div>
          <p className="text-xl text-muted-foreground">of disclosures are backed by reasonable assurance.</p>
        </div>

        <div className="lg:col-span-2 flex flex-col justify-center">
          <div className="h-4 w-full flex rounded-full overflow-hidden mb-6 bg-muted">
            <div style={{ width: `${reasonablePct}%` }} className="bg-accent transition-all duration-1000" />
            <div style={{ width: `${limitedPct}%` }} className="bg-emerald-500/50 transition-all duration-1000" />
            <div style={{ width: `${unassuredPct}%` }} className="bg-white/10 transition-all duration-1000" />
          </div>
          
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <div className="w-3 h-3 rounded-full bg-accent" />
                <span className="font-medium text-foreground">Reasonable</span>
              </div>
              <div className="text-muted-foreground">{summary.reasonable_count} areas</div>
            </div>
            <div>
              <div className="flex items-center gap-2 mb-1">
                <div className="w-3 h-3 rounded-full bg-emerald-500/50" />
                <span className="font-medium text-foreground">Limited</span>
              </div>
              <div className="text-muted-foreground">{summary.limited_count} areas</div>
            </div>
            <div>
              <div className="flex items-center gap-2 mb-1">
                <div className="w-3 h-3 rounded-full bg-white/10" />
                <span className="font-medium text-foreground">Unassured</span>
              </div>
              <div className="text-muted-foreground">{summary.unassured_count} areas</div>
            </div>
          </div>
        </div>
      </div>

      {summary.low_assurance_areas.length > 0 && (
        <div className="mt-12">
          <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-4">Low or No Assurance Areas</h3>
          <div className="flex flex-wrap gap-2">
            {summary.low_assurance_areas.map((area, i) => (
              <Badge key={i} variant="default" className="text-sm py-1 px-3">{area}</Badge>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}
