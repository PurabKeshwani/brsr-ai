import { api } from "@/lib/api"
import { HomeClient } from "@/components/HomeClient"

export default async function Home() {
  const companies = await api.listCompanies().catch(() => [])
  return <HomeClient companies={companies} />
}
