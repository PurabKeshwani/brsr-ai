"use client"

import { useEffect } from "react"
import { CompanySearch } from "@/components/CompanySearch"
import Link from "next/link"
import { UploadCloud, BarChart2, TrendingUp, BadgeCheck, ShieldAlert, Search, Eraser } from "lucide-react"
import { motion, useMotionValue, useSpring, useMotionTemplate, type Variants } from "framer-motion"
import type { CompanySummary } from "@/lib/api"

export function HomeClient({ companies }: { companies: CompanySummary[] }) {
  const mouseX = useMotionValue(0)
  const mouseY = useMotionValue(0)

  const springX = useSpring(mouseX, { stiffness: 50, damping: 20 })
  const springY = useSpring(mouseY, { stiffness: 50, damping: 20 })

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      mouseX.set(e.clientX)
      mouseY.set(e.clientY)
    }
    window.addEventListener("mousemove", handleMouseMove)
    return () => window.removeEventListener("mousemove", handleMouseMove)
  }, [mouseX, mouseY])

  const backgroundGlow = useMotionTemplate`radial-gradient(800px circle at ${springX}px ${springY}px, rgba(16, 185, 129, 0.15), transparent 80%)`

  const capabilities = [
    { title: "Multi-Year Trends", icon: <TrendingUp className="w-4 h-4 text-blue-500" /> },
    { title: "Consistency Checks", icon: <BadgeCheck className="w-4 h-4 text-emerald-500" /> },
    { title: "Assurance Coverage", icon: <ShieldAlert className="w-4 h-4 text-purple-500" /> },
    { title: "Greenwashing Signals", icon: <Search className="w-4 h-4 text-orange-500" /> },
    { title: "Silent Removals", icon: <Eraser className="w-4 h-4 text-rose-500" /> }
  ]

  const containerVariants: Variants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.15
      }
    }
  }

  const itemVariants: Variants = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 24 } }
  }

  return (
    <div className="flex-1 flex flex-col items-center justify-center py-12 px-6 relative overflow-hidden bg-white">
      
      {/* Clean Premium Dot Pattern */}
      <div className="absolute inset-0 z-0 opacity-[0.03] pointer-events-none" style={{ backgroundImage: 'radial-gradient(circle at 2px 2px, black 1px, transparent 0)', backgroundSize: '24px 24px' }} />
      
      {/* Interactive Radial Glow Spotlight */}
      <motion.div 
        className="absolute inset-0 pointer-events-none z-0"
        style={{ background: backgroundGlow }}
      />

      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="w-full max-w-4xl mx-auto space-y-12 relative z-10"
      >

        {/* Header */}
        <motion.div variants={itemVariants} className="text-center space-y-4">
          <h1 className="text-4xl font-medium tracking-tight text-foreground">
            BRSR Analysis Workspace
          </h1>
          <p className="text-muted-foreground text-lg">
            Search a company or upload a new SEBI BRSR filing for automated analysis.
          </p>
        </motion.div>

        {/* Main Search Action */}
        <motion.div variants={itemVariants} className="bg-white/80 backdrop-blur-xl p-8 rounded-3xl border border-border shadow-sm space-y-6">
          <CompanySearch companies={companies} />

          <div className="pt-6 border-t border-border/50">
            <div className="flex flex-wrap items-center justify-center gap-3">
              {capabilities.map((cap, idx) => (
                <div
                  key={idx}
                  className="group relative flex items-center gap-2 px-4 py-2 bg-muted/30 border border-border/50 rounded-full text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-white hover:shadow-[0_8px_30px_rgb(0,0,0,0.08)] hover:-translate-y-0.5 hover:border-accent/30 transition-all duration-300 cursor-default"
                >
                  <div className="absolute inset-0 rounded-full bg-gradient-to-r from-accent/0 via-accent/5 to-accent/0 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                  <div className="relative z-10 flex items-center gap-2">
                    <div className="p-1 rounded-full bg-white shadow-sm border border-border/50 group-hover:scale-110 transition-transform duration-300">
                      {cap.icon}
                    </div>
                    <span>{cap.title}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </motion.div>

        {/* Other Tools Grid */}
        <motion.div variants={itemVariants} className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Link
            href="/upload"
            className="group flex flex-col p-6 bg-white/80 backdrop-blur-md rounded-2xl border border-border hover:border-accent/50 hover:shadow-lg hover:-translate-y-1 transition-all duration-300"
          >
            <div className="w-12 h-12 bg-accent/10 text-accent rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-300">
              <UploadCloud className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-medium text-foreground mb-1">Analyze Custom Filing</h3>
            <p className="text-muted-foreground text-sm">Upload raw XBRL or PDF filings to run custom consistency checks and extract data.</p>
          </Link>

          <Link
            href="/compare"
            className="group flex flex-col p-6 bg-white/80 backdrop-blur-md rounded-2xl border border-border hover:border-accent/50 hover:shadow-lg hover:-translate-y-1 transition-all duration-300"
          >
            <div className="w-12 h-12 bg-accent/10 text-accent rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-300">
              <BarChart2 className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-medium text-foreground mb-1">Compare Peer Companies</h3>
            <p className="text-muted-foreground text-sm">Select multiple companies to benchmark their ESG metrics and disclosures side-by-side.</p>
          </Link>
        </motion.div>

      </motion.div>
    </div>
  )
}
