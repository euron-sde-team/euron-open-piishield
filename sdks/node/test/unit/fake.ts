/** A fake fetch: routes by method and path, records every request. */

export const BASE = "http://piishield.test";
export const API_KEY = "pii_" + "k".repeat(10) + "_" + "s".repeat(30);
export const PROJECT_ID = "83bf425d-2fe8-4a56-8845-70ba8ea89211";

export interface Recorded {
  method: string;
  path: string;
  query: URLSearchParams;
  headers: Record<string, string>;
  body: string;
}

type Handler = (req: Recorded) => Response | Promise<Response>;

export class FakeApi {
  calls: Recorded[] = [];
  routes = new Map<string, Handler[]>();

  on(method: string, path: string, ...handlers: Handler[]): this {
    this.routes.set(`${method} ${path}`, handlers);
    return this;
  }

  count(method: string, path: string): number {
    return this.calls.filter((c) => c.method === method && c.path === path).length;
  }

  last(method: string, path: string): Recorded {
    const found = this.calls.filter((c) => c.method === method && c.path === path).at(-1);
    if (!found) throw new Error(`no recorded call for ${method} ${path}`);
    return found;
  }

  fetch = async (input: string, init: RequestInit): Promise<Response> => {
    const url = new URL(input);
    const headers: Record<string, string> = {};
    for (const [k, v] of Object.entries((init.headers ?? {}) as Record<string, string>)) {
      headers[k.toLowerCase()] = v;
    }
    const req: Recorded = {
      method: init.method ?? "GET",
      path: url.pathname,
      query: url.searchParams,
      headers,
      body: typeof init.body === "string" ? init.body : "",
    };
    this.calls.push(req);
    const handlers = this.routes.get(`${req.method} ${req.path}`);
    if (!handlers?.length) return json(404, { error: { code: "not_found", message: req.path } });
    const handler = handlers.length > 1 ? handlers.shift()! : handlers[0]!;
    return handler(req);
  };
}

export function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

export function errorBody(code: string, message = "error", details: Record<string, unknown> = {}) {
  return { error: { code, type: "some_error", message, details } };
}

export function finding(category: string, start: number, end: number, confidence = 0.9, extra: Record<string, unknown> = {}) {
  return {
    category,
    start,
    end,
    confidence,
    checksum_valid: null,
    recognizer: `${category}_recognizer`,
    method: "full_mask",
    placeholder: null,
    in_review: false,
    ...extra,
  };
}

/** Matches detectors.schemas.ScanResultOut: no `protected`/`scope_id`, unlike
 * protectTextResponse (the /api/v1/detectors/scan route this backs never protects
 * anything). */
export function scanResponse(findingsList: Record<string, unknown>[] = [], reviewCount = 0): Record<string, unknown> {
  return { findings: findingsList, review_count: reviewCount };
}

export function protectTextResponse(
  protected_: string,
  findingsList: Record<string, unknown>[] = [],
  extra: Record<string, unknown> = {},
): Record<string, unknown> {
  return { protected: protected_, findings: findingsList, review_count: 0, scope_id: "scope-1", ...extra };
}
