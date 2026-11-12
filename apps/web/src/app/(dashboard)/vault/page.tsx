import type { Metadata } from "next";

import { VaultScreen } from "@/features/vault/components/vault-screen";

export const metadata: Metadata = { title: "Token Vault" };

export default function VaultPage() {
  return <VaultScreen />;
}
