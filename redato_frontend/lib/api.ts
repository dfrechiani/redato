/**
 * HTTP client (server-side helpers).
 *
 * Esses helpers SÓ rodam em route handlers Next.js (server). O JWT vive em
 * cookie httpOnly — nunca em memória do browser.
 *
 * Cliente (componentes 'use client') deve chamar `/api/auth/*` (proxy local)
 * usando `fetchJsonClient` em `lib/auth-client.ts`. Nunca chama o backend
 * direto, pra que o cookie httpOnly seja anexado pelo browser e o token
 * inserido pelo route handler.
 */

import { ApiError, type ApiErrorBody } from "@/types/api";
import { API_BASE } from "./env";

interface FetchOpts {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  bearer?: string;
  headers?: Record<string, string>;
}

/**
 * Server-side: chama backend FastAPI direto. Usado por route handlers
 * Next.js ao fazer proxy.
 */
export async function fetchBackend<T>(
  path: string,
  opts: FetchOpts = {},
): Promise<T> {
  const { method = "GET", body, bearer, headers = {} } = opts;
  const url = `${API_BASE}${path}`;

  const init: RequestInit = {
    method,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(bearer ? { Authorization: `Bearer ${bearer}` } : {}),
      ...headers,
    },
    cache: "no-store",
  };

  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }

  let resp: Response;
  try {
    resp = await fetch(url, init);
  } catch (err) {
    throw new ApiError(0, `Falha de rede: ${(err as Error).message}`);
  }

  // 204 No Content
  if (resp.status === 204) {
    return undefined as T;
  }

  let data: unknown;
  const text = await resp.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      // Resposta não-JSON (HTML de erro do proxy reverso, etc.)
      throw new ApiError(resp.status, `Resposta inesperada: ${text.slice(0, 100)}`);
    }
  }

  if (!resp.ok) {
    const detail = (data as ApiErrorBody | undefined)?.detail
      ?? `Erro ${resp.status}`;
    throw new ApiError(resp.status, detail);
  }

  return data as T;
}
