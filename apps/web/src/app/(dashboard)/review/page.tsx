import type { Metadata } from "next";

import { ReviewScreen } from "@/features/review/components/review-screen";

export const metadata: Metadata = { title: "Review Queue" };

export default function ReviewPage() {
  return <ReviewScreen />;
}
