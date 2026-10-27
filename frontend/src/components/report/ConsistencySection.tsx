"use client"

import { ConsistencySummary } from "@/lib/api"
import { Card } from "@/components/ui/card"
import { CheckCircle2, AlertTriangle, Info } from "lucide-react"
import { AnimatedNumber } from "@/components/ui/animated-number"

export function ConsistencySection({ summary }: { summary: ConsistencySummary }) {
  if (!summary) return null

  return (
    <section className="py-12 border-t border-border/50">
      <h2 className="text-3xl font-serif italic mb-8">Consistency Checks</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-10">
        <Card className="flex items-center gap-4">
          <div className="p-3 bg-white/5 rounded-xl"><Info className="w-6 h-6 text-blue-400" /></div>
          <div>
            <div className="text-3xl font-medium">
              <AnimatedNumber value={summary.total_checks} />
            </div>
            <div className="text-sm text-muted-foreground">Total Checks</div>
          </div>
        </Card>
        <Card className="flex items-center gap-4 border-emerald-500/20">
          <div className="p-3 bg-emerald-500/10 rounded-xl"><CheckCircle2 className="w-6 h-6 text-emerald-500" /></div>
          <div>
            <div className="text-3xl font-medium text-emerald-500">
              <AnimatedNumber value={summary.passed} delay={100} />
            </div>
            <div className="text-sm text-muted-foreground">Passed</div>
          </div>
        </Card>
        <Card className="flex items-center gap-4 border-amber-500/20">
          <div className="p-3 bg-amber-500/10 rounded-xl"><AlertTriangle className="w-6 h-6 text-amber-500" /></div>
          <div>
            <div className="text-3xl font-medium text-amber-500">
              <AnimatedNumber value={summary.failed} delay={200} />
            </div>
            <div className="text-sm text-muted-foreground">Failed</div>
          </div>
        </Card>
        <Card className="flex items-center gap-4">
          <div className="p-3 bg-white/5 rounded-xl"><Info className="w-6 h-6 text-muted-foreground" /></div>
          <div>
            <div className="text-3xl font-medium">
              <AnimatedNumber value={summary.skipped} delay={300} />
            </div>
            <div className="text-sm text-muted-foreground">Skipped</div>
          </div>
        </Card>
      </div>

      {summary.failures.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-xl font-medium mb-4 flex items-center gap-2 text-amber-500">
            <AlertTriangle className="w-5 h-5" /> 
            Identified Discrepancies
          </h3>
          {summary.failures.map((f, i) => (
            <Card key={i} className="bg-amber-500/5 border-amber-500/20">
              <div className="flex flex-col md:flex-row justify-between gap-4">
                <div>
                  <div className="font-mono text-sm text-amber-500 mb-1">{f.concept}</div>
                  <div className="font-medium text-foreground">{f.message}</div>
                </div>
                <div className="text-sm text-muted-foreground bg-black/20 px-3 py-1.5 rounded-lg self-start">
                  Context: {f.context}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </section>
  )
}
