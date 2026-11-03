import { CompanyWorkspace } from "@/components/workspace/CompanyWorkspace";
export default async function CompanyPage({
  params,
}: {
  params: Promise<{ name: string }>;
}) {
  const { name } = await params;
  // This Next.js release retains URL escapes in dynamic route params.
  let decoded = name;
  try {
    decoded = decodeURIComponent(name);
  } catch {
    /* Retain literal percent characters. */
  }
  return <CompanyWorkspace name={decoded} />;
}
