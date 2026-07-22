import { Suspense } from "react";

import { BillingPage } from "@/features/dashboard/pages/billing-page";

export default function BillingRoute() {
  return <Suspense fallback={<main className="dashboard-loading">Loading billing</main>}><BillingPage /></Suspense>;
}
