"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Search, ArrowRight } from "lucide-react"
import type { CompanySummary } from "@/lib/api"
import { cn } from "@/lib/utils"

export function CompanySearch({ companies }: { companies: CompanySummary[] }) {
  const [query, setQuery] = useState("")
  const [isFocused, setIsFocused] = useState(false)
  const router = useRouter()

  const filtered = query
    ? companies.filter(c => c.name.toLowerCase().includes(query.toLowerCase()) || c.cin.toLowerCase().includes(query.toLowerCase()))
    : companies

  return (
    <div className="relative w-full max-w-xl mx-auto z-50">
      <div 
        className={cn(
          "relative flex items-center bg-muted/50 border rounded-2xl transition-all duration-300 shadow-sm",
          isFocused ? "border-accent ring-4 ring-accent/10 bg-white shadow-md" : "border-border hover:border-accent/50 hover:bg-white"
        )}
      >
        <Search className="w-6 h-6 text-muted-foreground ml-6" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setTimeout(() => setIsFocused(false), 200)}
          placeholder="Search for a company (e.g. Reliance, TCS)..."
          className="w-full bg-transparent border-none outline-none py-4 px-4 text-lg text-foreground placeholder:text-muted-foreground/50"
        />
      </div>

      {isFocused && query && (
        <div className="absolute top-full left-0 right-0 mt-3 bg-card border border-border rounded-2xl shadow-xl overflow-hidden max-h-[300px] overflow-y-auto">
          {filtered.length > 0 ? (
            <ul className="py-2">
              {filtered.map(company => (
                <li key={company.id}>
                  <button
                    onMouseDown={(e) => {
                      e.preventDefault(); // Prevent input blur
                      setIsFocused(false);
                      router.push(`/company/${encodeURIComponent(company.name)}`);
                    }}
                    className="w-full text-left px-6 py-4 hover:bg-black/5 transition-colors flex items-center justify-between group"
                  >
                    <div>
                      <div className="font-medium text-foreground">{company.name}</div>
                      <div className="text-sm text-muted-foreground mt-1 font-mono">{company.cin}</div>
                    </div>
                    <ArrowRight className="w-5 h-5 text-accent opacity-0 group-hover:opacity-100 transition-opacity -translate-x-4 group-hover:translate-x-0" />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <div className="p-6 text-center text-muted-foreground">
              No companies found matching "{query}"
            </div>
          )}
        </div>
      )}
    </div>
  )
}
