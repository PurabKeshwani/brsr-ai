"use client"

import { SectorBenchmarkInfo } from "@/lib/api"
import { Card } from "@/components/ui/card"
import { AnimatedNumber } from "@/components/ui/animated-number"
import { motion } from "framer-motion"
import { Trophy, AlertTriangle, Info } from "lucide-react"

function getScoreColorClass(score: number) {
  if (score < 40) return "bg-rose-500"
  if (score < 65) return "bg-amber-500"
  return "bg-emerald-500"
}

export function SectorBenchmarkSection({
  benchmark,
}: {
  benchmark: SectorBenchmarkInfo
}) {
  const {
    sector,
    company_transparency_score,
    sector_mean,
    sector_median,
    percentile_rank,
    sector_peer_count,
    is_sector_leader,
    is_sector_laggard,
    benchmark_reliable,
  } = benchmark

  const companyColor = getScoreColorClass(company_transparency_score)

  return (
    <section className="py-12">
      <h2 className="text-3xl font-serif italic mb-8">Sector Benchmark</h2>
      
      <Card className="p-8 glass-panel relative overflow-hidden">
        <div className="flex flex-col md:flex-row gap-8 justify-between">
          <div className="flex-1">
            <h3 className="text-lg font-medium text-muted-foreground mb-1 uppercase tracking-wider text-xs">Sector</h3>
            <div className="text-2xl font-medium mb-4">{sector}</div>
            
            <div className="flex items-center gap-3 flex-wrap mt-2">
              {is_sector_leader && (
                <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm font-medium">
                  <Trophy className="w-4 h-4" />
                  Sector Leader
                </div>
              )}
              {is_sector_laggard && (
                <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-500 text-sm font-medium">
                  <AlertTriangle className="w-4 h-4" />
                  Below Sector Average
                </div>
              )}
            </div>
            
            {!benchmark_reliable && (
              <div className="flex items-start gap-2 mt-6 text-sm text-muted-foreground bg-white/5 p-3 rounded-lg border border-white/5">
                <Info className="w-4 h-4 mt-0.5 shrink-0" />
                <p>Based on a small peer group ({sector_peer_count} companies) — interpret with caution</p>
              </div>
            )}
          </div>

          <div className="flex-1 flex flex-col justify-center">
            <div className="mb-8 text-center md:text-right">
              <div className="text-5xl font-medium tracking-tight text-foreground">
                <AnimatedNumber value={percentile_rank} delay={100} />
                <span className="text-2xl text-muted-foreground ml-1">th</span>
              </div>
              <div className="text-sm font-medium text-muted-foreground uppercase tracking-wider mt-2">
                Percentile in Sector
              </div>
            </div>

            {/* 1D Plot */}
            <div className="relative mt-8">
              <div className="flex justify-between text-xs text-muted-foreground mb-2 font-mono">
                <span>0</span>
                <span>50</span>
                <span>100</span>
              </div>
              
              <div className="relative w-full h-2 bg-white/10 rounded-full">
                {/* Sector Median */}
                <div 
                  className="absolute top-0 bottom-0 w-0.5 bg-white/20 z-0"
                  style={{ left: `${sector_median}%` }}
                />
                <div 
                  className="absolute top-4 -translate-x-1/2 text-[10px] text-muted-foreground font-mono"
                  style={{ left: `${sector_median}%` }}
                >
                  MEDIAN
                </div>

                {/* Sector Mean */}
                <div 
                  className="absolute top-0 bottom-0 w-0.5 bg-white/40 z-0"
                  style={{ left: `${sector_mean}%` }}
                />
                <div 
                  className="absolute -top-5 -translate-x-1/2 text-[10px] text-muted-foreground font-mono"
                  style={{ left: `${sector_mean}%` }}
                >
                  MEAN
                </div>

                {/* Company Score Marker */}
                <motion.div
                  className={`absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full ${companyColor} border-2 border-background shadow-[0_0_10px_rgba(255,255,255,0.1)] z-10`}
                  initial={{ left: "0%" }}
                  whileInView={{ left: `${company_transparency_score}%` }}
                  viewport={{ once: true }}
                  transition={{ duration: 1, ease: "easeOut", delay: 0.3 }}
                />
              </div>
            </div>
          </div>
        </div>
      </Card>
    </section>
  )
}
