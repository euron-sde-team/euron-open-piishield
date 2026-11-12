"use client";

import { RotateCwIcon } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  React.useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-3 bg-background px-6 text-center">
      <h1 className="text-2xl font-semibold text-foreground">Something went wrong</h1>
      <p className="max-w-sm text-sm text-muted-foreground">
        An unexpected error stopped this page from loading. Retry, and if it keeps happening, check the browser
        console for details.
      </p>
      <Button onClick={reset}>
        <RotateCwIcon />
        Retry
      </Button>
    </div>
  );
}
