import type { Metadata } from "next";

import { OverviewScreen } from "@/features/reports/components/overview-screen";

export const metadata: Metadata = { title: "Overview" };

export default function OverviewPage() {
  return <OverviewScreen />;
}
