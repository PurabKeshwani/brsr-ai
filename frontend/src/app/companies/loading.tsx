import { Card } from "@/components/ui/card"

export default function Loading() {
  return (
    <div className="min-h-screen py-24 px-6">
      <div className="max-w-6xl mx-auto">
        <header className="mb-16">
          <h1 className="text-5xl font-medium tracking-tight mb-4">
            Monitored <span className="font-serif italic text-muted-foreground">Companies</span>
          </h1>
          <p className="text-xl text-muted-foreground max-w-2xl">
            Select a company to view its detailed BRSR analysis, including multi-year trends, consistency checks, and greenwashing signals.
          </p>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {Array.from({ length: 9 }).map((_, i) => (
            <Card key={i} className="h-full flex flex-col relative overflow-hidden p-6 glass-panel opacity-50">
              <div className="mb-8 animate-pulse">
                <div className="w-24 h-5 rounded-full bg-white/10 mb-4" />
                <div className="w-3/4 h-8 rounded-lg bg-white/10" />
              </div>
              <div className="mt-auto pt-6 border-t border-border/50 flex items-center justify-between animate-pulse">
                <div className="w-16 h-4 bg-white/5 rounded" />
                <div className="w-12 h-4 bg-white/10 rounded" />
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  )
}
