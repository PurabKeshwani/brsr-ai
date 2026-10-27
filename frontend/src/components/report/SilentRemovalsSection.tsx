"use client"

import { SilentRemovalItem } from "@/lib/api"
import { Ghost, History } from "lucide-react"

export function SilentRemovalsSection({ removals }: { removals: SilentRemovalItem[] }) {
  if (!removals || removals.length === 0) return null

  return (
    <section className="py-16 border-t border-border/50">
      <div className="mb-10 flex items-center gap-3">
        <Ghost className="w-8 h-8 text-rose-500/50" />
        <h2 className="text-2xl font-medium tracking-tight">Silent Removals</h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {removals.map((removal, idx) => (
          <div key={idx} className="p-6 rounded-2xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors">
            <div className="flex items-center gap-2 mb-4 text-sm font-mono text-rose-300">
              <History className="w-4 h-4" />
              {removal.prior_year_period}
            </div>
            
            <h3 className="text-lg font-medium mb-2">{removal.concept}</h3>
            <div className="text-sm text-muted-foreground mb-4">Context: {removal.context}</div>
            
            <div className="p-4 bg-black/30 rounded-xl mb-4">
              <div className="text-xs text-muted-foreground mb-1">Prior Disclosed Value</div>
              <div className="font-mono text-foreground">{removal.prior_year_value}</div>
            </div>
            
            <p className="text-sm text-muted-foreground leading-relaxed">
              {removal.rationale}
            </p>
          </div>
        ))}
      </div>
    </section>
  )
}
