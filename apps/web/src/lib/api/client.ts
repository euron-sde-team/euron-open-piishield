import createClient, { type Middleware } from "openapi-fetch";

import { ApiError, parseApiError } from "./errors";
import type { paths } from "./schema";
import { getAuthToken } from "../auth-store";

/**
 * Requests that must NOT carry a bearer token: logging in or signing up is how a
 * token is obtained in the first place.
 */
const PUBLIC_PATHS = new Set(["/api/v1/auth/login", "/api/v1/auth/signup"]);

const auth: Middleware = {
  onRequest({ request, schemaPath }) {
    if (PUBLIC_PATHS.has(schemaPath)) return request;
    const token = getAuthToken();
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
};

/**
 * Typed client for the PIIShield API. Same origin: Next rewrites /api/v1 to the API
 * service, so this works unchanged in dev and in the container.
 */
export const api = createClient<paths>({ baseUrl: "" });
api.use(auth);

interface FetchResult<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

/** Await an openapi-fetch call and return its data, or throw an ApiError built from the envelope. */
export async function unwrap<T>(call: Promise<FetchResult<T>>): Promise<T> {
  let result: FetchResult<T>;
  try {
    result = await call;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw parseApiError(0, null);
  }
  if (!result.response.ok) {
    throw parseApiError(result.response.status, result.error);
  }
  return result.data as T;
}
