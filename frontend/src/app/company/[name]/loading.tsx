import { Card } from "@/components/ui/card"

export default function Loading() {
  return (
    <div className="min-h-screen">
      {/* Header Skeleton */}
      <header className="pt-24 pb-16 px-6 bg-card/50 border-b border-border/50">
        <div className="max-w-6xl mx-auto animate-pulse">
          <div className="w-32 h-4 bg-white/10 rounded mb-8" />
          <div className="w-2/3 md:w-1/2 h-16 md:h-20 bg-white/10 rounded-xl mb-8" />
          
          <div className="flex flex-wrap gap-6">
            <div className="w-32 h-9 bg-white/5 border border-white/10 rounded-full" />
            <div className="w-32 h-9 bg-white/5 border border-white/10 rounded-full" />
            <div className="w-32 h-9 bg-white/5 border border-white/10 rounded-full" />
          </div>
        </div>
      </header>

      {/* Content Skeleton */}
      <main className="max-w-6xl mx-auto px-6 py-12 space-y-12">
        <section className="py-12">
          <div className="w-48 h-8 bg-white/10 rounded-lg mb-8 animate-pulse" />
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <Card key={i} className="p-5 glass-panel h-32 opacity-50 animate-pulse" />
            ))}
          </div>
        </section>
        
        <section className="py-12 border-t border-border/50">
          <div className="w-48 h-8 bg-white/10 rounded-lg mb-8 animate-pulse" />
          <Card className="p-8 glass-panel h-64 opacity-50 animate-pulse" />
        </section>
      </main>
    </div>
  )
}
