import type { Metadata } from "next";

import { DatabaseScanScreen } from "@/features/database-scan/components/database-scan-screen";

export const metadata: Metadata = { title: "Database Scan" };

export default function DatabaseScanPage() {
  return <DatabaseScanScreen />;
}
