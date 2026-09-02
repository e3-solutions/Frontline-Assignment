import { DashboardClient } from "@/src/components/dashboard/DashboardClient";
import { createSupabaseServerClient } from "@/src/db/server";
import { createDashboardBusinessService } from "@/src/services/dashboard";

export default async function Home() {
  const client = await createSupabaseServerClient();
  const dashboardService = createDashboardBusinessService(client);
  const { loads, calls, emails, summary } = await dashboardService.fetchAll();

  return <DashboardClient loads={loads} calls={calls} emails={emails} summary={summary} />;
}
