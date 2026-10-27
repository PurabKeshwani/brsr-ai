import { api } from "@/lib/api"
import { CompaniesGrid } from "@/components/CompaniesGrid"

export default async function CompaniesPage() {
  const companies = await api.listCompanies().catch(() => [])

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

        {companies.length > 0 ? (
          <CompaniesGrid companies={companies} />
        ) : (
          <div className="text-center py-24">
            <p className="text-muted-foreground">No companies found. Make sure the backend is running.</p>
          </div>
        )}
      </div>
    </div>
  )
}
