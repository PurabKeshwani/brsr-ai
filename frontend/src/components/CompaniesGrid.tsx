"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import Link from "next/link"
import { ArrowUpRight } from "lucide-react"
import type { CompanySummary } from "@/lib/api"
import { Card } from "@/components/ui/card"

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
  show: { opacity: 1, y: 0, transition: { type: "spring" as const, stiffness: 300, damping: 30 } }
}

export function CompaniesGrid({ companies }: { companies: CompanySummary[] }) {
  const [visibleCount, setVisibleCount] = useState(12)
  
  const visibleCompanies = companies.slice(0, visibleCount)
  const hasMore = visibleCount < companies.length

  return (
    <div>
      <motion.div 
        variants={container}
        initial="hidden"
        animate="show"
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
      >
        <AnimatePresence>
          {visibleCompanies.map((company) => (
            <motion.div key={company.id} variants={item} layout>
              <Link href={`/company/${encodeURIComponent(company.name)}`}>
                <Card className="group cursor-pointer hover:scale-[1.02] hover:border-accent/30 hover:shadow-[0_0_15px_rgba(16,185,129,0.15)] active:scale-95 hover:bg-card/80 transition-all duration-300 h-full flex flex-col relative overflow-hidden">
                  <div className="absolute top-0 right-0 p-6 opacity-0 group-hover:opacity-100 group-hover:-translate-y-1 group-hover:translate-x-1 transition-all">
                    <ArrowUpRight className="text-accent" />
                  </div>
                  <div className="mb-8">
                    <div className="inline-flex items-center rounded-full bg-white/5 border border-white/10 px-2.5 py-0.5 text-xs font-mono text-muted-foreground mb-4">
                      {company.cin}
                    </div>
                    <h2 className="text-2xl font-medium tracking-tight text-foreground group-hover:text-accent transition-colors">
                      {company.name}
                    </h2>
                  </div>
                  
                  <div className="mt-auto pt-6 border-t border-border/50 flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">NIC Code</span>
                    <span className="text-sm font-medium">{company.nic_code || "N/A"}</span>
                  </div>
                </Card>
              </Link>
            </motion.div>
          ))}
        </AnimatePresence>
      </motion.div>

      {hasMore && (
        <div className="mt-12 flex justify-center">
          <button 
            onClick={() => setVisibleCount(prev => prev + 12)}
            className="px-6 py-2.5 rounded-full border border-white/10 bg-white/5 hover:bg-white/10 text-sm font-medium transition-colors"
          >
            Load More Companies
          </button>
        </div>
      )}
    </div>
  )
}
