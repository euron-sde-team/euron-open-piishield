import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

import { OWNER } from "./helpers";

/**
 * Sign in once through the real API and write a Playwright storageState seeding the
 * dashboard's two localStorage keys (zustand persist: "piishield.auth" holds the bearer
 * token and user, "piishield.project" holds the selected project), so every suite opens
 * the dashboard already signed in. PIIShield has no session cookie: every call after
 * login carries `Authorization: Bearer <token>`, so there is no cookie to capture, only
 * localStorage for the ORIGIN the dashboard actually runs on.
 */
export default async function globalSetup(): Promise<void> {
  const webURL = process.env.WEB_URL || "http://localhost:5510";
  const apiURL = process.env.API_URL || "http://localhost:5530";

  const loginResp = await fetch(`${apiURL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(OWNER),
  });
  if (!loginResp.ok) {
    throw new Error(`demo sign-in failed (${loginResp.status}): run make demo first`);
  }
  const session = (await loginResp.json()) as { token: string; user: unknown };

  const projectsResp = await fetch(`${apiURL}/api/v1/projects`, {
    headers: { authorization: `Bearer ${session.token}` },
  });
  if (!projectsResp.ok) throw new Error(`listing projects failed (${projectsResp.status})`);
  const projects = (await projectsResp.json()) as { id: string }[];
  if (!projects.length) throw new Error("the demo has no projects: run make demo");

  const origin = new URL(webURL).origin;
  const storageState = {
    cookies: [],
    origins: [
      {
        origin,
        localStorage: [
          {
            name: "piishield.auth",
            value: JSON.stringify({ state: { token: session.token, user: session.user }, version: 1 }),
          },
          {
            name: "piishield.project",
            value: JSON.stringify({ state: { selectedProjectId: projects[0]!.id }, version: 1 }),
          },
        ],
      },
    ],
  };

  const authDir = path.resolve(".auth");
  await mkdir(authDir, { recursive: true });
  await writeFile(path.join(authDir, "owner.json"), JSON.stringify(storageState, null, 2));
}
