"use client"

import { TransparencyScoreBreakdown } from "@/lib/api"
import { Card } from "@/components/ui/card"
import { AnimatedNumber } from "@/components/ui/animated-number"
import { motion } from "framer-motion"

function getScoreColor(score: number) {
  if (score < 40) return { text: "text-rose-500", stroke: "#f43f5e", bg: "bg-rose-500" }
  if (score < 65) return { text: "text-amber-500", stroke: "#f59e0b", bg: "bg-amber-500" }
  return { text: "text-emerald-500", stroke: "#10b981", bg: "bg-emerald-500" }
}

export function TransparencyScoreSection({
  score,
}: {
  score: TransparencyScoreBreakdown
}) {
  const { composite_score } = score
  const color = getScoreColor(composite_score)
  
  const radius = 80
  const circumference = 2 * Math.PI * radius
  
  const subComponents = [
    { label: "Completeness", value: score.completeness_pct, weight: "40%" },
    { label: "Specificity", value: score.specificity_pct, weight: "30%" },
    { label: "Clarity", value: score.clarity_pct, weight: "20%" },
    { label: "SDG Alignment", value: score.sdg_alignment_pct, weight: "10%" },
  ]

  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1
      }
    }
  }

  const item = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0 }
  }

  return (
    <section className="py-12">
      <h2 className="text-3xl font-serif italic mb-8">Transparency Score</h2>
      
      <motion.div 
        variants={container}
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: "-100px" }}
        className="flex flex-col items-center"
      >
        <div className="relative w-64 h-64 flex items-center justify-center mb-12">
          {/* Background Track */}
          <svg className="absolute inset-0 w-full h-full -rotate-90">
            <circle
              cx="128"
              cy="128"
              r={radius}
              stroke="var(--border)"
              strokeWidth="12"
              fill="none"
            />
            {/* Animated Progress */}
            <motion.circle
              cx="128"
              cy="128"
              r={radius}
              stroke={color.stroke}
              strokeWidth="12"
              fill="none"
              strokeLinecap="round"
              initial={{ strokeDashoffset: circumference }}
              whileInView={{ strokeDashoffset: circumference - (composite_score / 100) * circumference }}
              viewport={{ once: true, margin: "-100px" }}
              transition={{ duration: 1.5, ease: "easeOut", delay: 0.2 }}
              style={{
                strokeDasharray: circumference,
              }}
            />
          </svg>
          
          <div className="flex flex-col items-center justify-center text-center z-10">
            <span className={`text-6xl font-medium tracking-tight ${color.text}`}>
              <AnimatedNumber value={composite_score} delay={200} />
            </span>
            <span className="text-sm text-muted-foreground mt-2 uppercase tracking-wider font-medium">Out of 100</span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 w-full">
          {subComponents.map((comp, idx) => {
            const compColor = getScoreColor(comp.value)
            return (
              <motion.div key={comp.label} variants={item}>
                <Card className="p-5 flex flex-col glass-panel">
                  <div className="flex justify-between items-baseline mb-3">
                    <h3 className="text-sm font-medium text-muted-foreground">{comp.label}</h3>
                    <span className="text-xs font-mono text-muted-foreground bg-white/5 px-2 py-0.5 rounded border border-white/10">
                      {comp.weight} weight
                    </span>
                  </div>
                  <div className="flex items-baseline gap-2 mb-3">
                    <span className={`text-2xl font-medium ${compColor.text}`}>
                      {comp.value !== null && comp.value !== undefined ? (
                        <><AnimatedNumber value={comp.value} delay={400 + idx * 100} />%</>
                      ) : (
                        "N/A"
                      )}
                    </span>
                  </div>
                  {/* Mini Progress Bar */}
                  <div className="h-1.5 w-full bg-white/10 rounded-full overflow-hidden">
                    <motion.div
                      className={`h-full ${compColor.bg}`}
                      initial={{ width: 0 }}
                      whileInView={{ width: `${comp.value}%` }}
                      viewport={{ once: true }}
                      transition={{ duration: 1, ease: "easeOut", delay: 0.5 + idx * 0.1 }}
                    />
                  </div>
                </Card>
              </motion.div>
            )
          })}
        </div>
      </motion.div>
    </section>
  )
}
