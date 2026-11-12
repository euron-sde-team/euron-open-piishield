import type { Metadata } from "next";

import { KeysScreen } from "@/features/keys/components/keys-screen";

export const metadata: Metadata = { title: "API Keys" };

export default function KeysPage() {
  return <KeysScreen />;
}
