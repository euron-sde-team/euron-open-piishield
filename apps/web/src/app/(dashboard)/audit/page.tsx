import type { Metadata } from "next";

import { AuditScreen } from "@/features/audit/components/audit-screen";

export const metadata: Metadata = { title: "Audit Log" };

export default function AuditPage() {
  return <AuditScreen />;
}
