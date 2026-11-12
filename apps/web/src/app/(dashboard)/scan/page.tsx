import type { Metadata } from "next";

import { ScanScreen } from "@/features/scan/components/scan-screen";

export const metadata: Metadata = { title: "Scan Center" };

export default function ScanPage() {
  return <ScanScreen />;
}
