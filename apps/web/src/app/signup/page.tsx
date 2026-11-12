import type { Metadata } from "next";

import { SignupScreen } from "@/features/auth/components/signup-screen";

export const metadata: Metadata = { title: "Create organisation" };

export default function SignupPage() {
  return <SignupScreen />;
}
