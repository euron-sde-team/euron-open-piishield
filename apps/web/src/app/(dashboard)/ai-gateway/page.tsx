import type { Metadata } from "next";

import { AiGatewayScreen } from "@/features/ai-gateway/components/ai-gateway-screen";

export const metadata: Metadata = { title: "AI Gateway" };

export default function AiGatewayPage() {
  return <AiGatewayScreen />;
}
