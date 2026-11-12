"use client";

import { useMutation } from "@tanstack/react-query";

import { parseApiError } from "@/lib/api/errors";
import { getAuthToken } from "@/lib/auth-store";

export interface UploadedDocument {
  /** The protected file's bytes, in the SAME format as the upload (never a JSON report). */
  blob: Blob;
  filename: string;
  contentType: string;
}

/**
 * On success the real API (documents/router.py) returns the protected file's raw
 * bytes directly, with a Content-Disposition filename, never a JSON findings report:
 * this bypasses the typed openapi-fetch client (which assumes a JSON body) and posts
 * the FormData directly. Only a non-2xx response is ever JSON (FastAPI's own error
 * envelope), so the body is read as JSON on failure and as a Blob on success, never
 * both; calling response.json() unconditionally would throw on every successful
 * upload and silently discard the protected file (the first version of this function
 * did exactly that).
 */
async function uploadDocument(projectId: string, file: File): Promise<UploadedDocument> {
  const form = new FormData();
  form.append("file", file);
  const token = getAuthToken();
  let response: Response;
  try {
    response = await fetch(`/api/v1/documents?project_id=${encodeURIComponent(projectId)}`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      body: form,
    });
  } catch {
    throw parseApiError(0, null);
  }
  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    throw parseApiError(response.status, body);
  }
  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") ?? "";
  const filenameMatch = /filename="?([^";]+)"?/.exec(disposition);
  return {
    blob,
    filename: filenameMatch?.[1] ?? `protected_${file.name}`,
    contentType: response.headers.get("content-type") ?? blob.type,
  };
}

export function useUploadDocument() {
  return useMutation({
    mutationFn: ({ projectId, file }: { projectId: string; file: File }) => uploadDocument(projectId, file),
  });
}
