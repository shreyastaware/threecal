import { IntegrationsPage } from "@/features/dashboard/pages/integrations-page";

export default async function IntegrationsRoute({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  // OAuth callbacks redirect here with ?connected=<provider> or ?error=<code>.
  const { connected, error } = await searchParams;
  return (
    <IntegrationsPage
      connected={typeof connected === "string" ? connected : null}
      error={typeof error === "string" ? error : null}
    />
  );
}
