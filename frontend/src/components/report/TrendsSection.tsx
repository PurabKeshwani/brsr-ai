"use client"

import { MetricTrend } from "@/lib/api"
import { Card } from "@/components/ui/card"
import dynamic from "next/dynamic"
import { AnimatedNumber } from "@/components/ui/animated-number"
const Sparkline = dynamic(() => import("@/components/ui/sparkline").then(mod => mod.Sparkline), { ssr: false })
import { ArrowDown, ArrowUp, Minus } from "lucide-react"

function humanize(camelCase: string) {
  const result = camelCase.replace(/([A-Z])/g, " $1")
  return result.charAt(0).toUpperCase() + result.slice(1)
}

export function TrendsSection({ trends }: { trends: MetricTrend[] }) {
  if (!trends || trends.length === 0) return null

  return (
    <section className="py-12">
      <h2 className="text-3xl font-serif italic mb-8">Key Metrics & Trends</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {trends.map((trend, idx) => {
          const isIncrease = trend.yoy_change_pct !== null && trend.yoy_change_pct > 0
          const isDecrease = trend.yoy_change_pct !== null && trend.yoy_change_pct < 0
          
          // Assuming most reported metrics (emissions, waste) are "less is better"
          // We can use generic colors or try to guess. Let's use red/amber for up, green/emerald for down.
          const color = isIncrease ? "text-amber-500" : isDecrease ? "text-emerald-500" : "text-muted-foreground"
          const strokeColor = isIncrease ? "#f59e0b" : isDecrease ? "#10b981" : "#9ca3af"

          return (
            <Card key={idx} className="flex flex-col">
              <div className="mb-4">
                <h3 className="text-lg font-medium text-muted-foreground">{humanize(trend.concept)}</h3>
                <div className="flex items-baseline gap-2 mt-2">
                  <span className="text-3xl font-medium tracking-tight">
                    {trend.latest_value !== null ? trend.latest_value.toLocaleString() : "N/A"}
                  </span>
                  {trend.yoy_change_pct !== null && (
                    <div className={`flex items-center text-sm font-semibold ${color}`}>
                      {isIncrease ? <ArrowUp className="w-4 h-4 mr-1" /> : isDecrease ? <ArrowDown className="w-4 h-4 mr-1" /> : <Minus className="w-4 h-4 mr-1" />}
                      <AnimatedNumber value={Math.abs(trend.yoy_change_pct)} delay={idx * 100} />% YoY
                    </div>
                  )}
                </div>
              </div>
              <div className="mt-auto">
                <Sparkline data={trend.series} color={strokeColor} />
              </div>
            </Card>
          )
        })}
      </div>
    </section>
  )
}
