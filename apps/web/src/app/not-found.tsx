import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-3 bg-background px-6 text-center">
      <h1 className="text-2xl font-semibold text-foreground">Page not found</h1>
      <p className="max-w-sm text-sm text-muted-foreground">
        The page you are looking for does not exist, or has moved.
      </p>
      <Link href="/" className="text-sm font-medium text-primary hover:underline">
        Back to Overview
      </Link>
    </div>
  );
}
