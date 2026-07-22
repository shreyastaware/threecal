import { Suspense } from "react";

import { DashboardPage } from "@/features/dashboard/pages/dashboard-page";

export default function DashboardRoute() {
  return <Suspense fallback={<main className="dashboard-loading">Opening your workspace</main>}><DashboardPage /></Suspense>;
}
