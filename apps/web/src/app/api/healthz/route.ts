import { NextResponse } from "next/server";

/**
 * The web server's own liveness probe, separate from the API's /healthz that Next
 * proxies through rewrites(). The Dockerfile healthcheck fetches this exact path
 * (http://127.0.0.1:$PORT/api/healthz) and expects 200. An actual route handler file
 * here takes precedence over the /api/v1/:path* rewrite rule (which does not match
 * this path anyway), so the rewrite can never intercept it.
 */
export function GET() {
  return NextResponse.json({ status: "ok" }, { status: 200 });
}
