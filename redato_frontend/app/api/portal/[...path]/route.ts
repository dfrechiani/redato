/**
 * Proxy genérico /api/portal/* → backend /portal/*. Usa o cookie httpOnly
 * de sessão pra anexar o Bearer.
 *
 * GET / POST / PATCH / DELETE são todos suportados. Em 401, limpa cookies
 * (token revogado / sessão invalidada por /sair-todas-sessoes).
 */

import { NextResponse, type NextRequest } from "next/server";

import { fetchBackend } from "@/lib/api";
import { clearSessionCookies, getSessionToken } from "@/lib/auth-server";
import { ApiError } from "@/types/api";

type Method = "GET" | "POST" | "PATCH" | "DELETE";

async function handle(
  req: NextRequest,
  { params }: { params: { path: string[] } },
  method: Method,
): Promise<NextResponse> {
  const token = getSessionToken();
  if (!token) {
    return NextResponse.json(
      { detail: "Não autenticado" },
      { status: 401 },
    );
  }

  const subpath = (params.path || []).join("/");
  const search = req.nextUrl.search;
  const target = `/portal/${subpath}${search}`;

  let body: unknown = undefined;
  if (method !== "GET" && method !== "DELETE") {
    const text = await req.text();
    if (text) {
      try {
        body = JSON.parse(text);
      } catch {
        return NextResponse.json(
          { detail: "Payload inválido" },
          { status: 400 },
        );
      }
    }
  }

  try {
    const data = await fetchBackend<unknown>(target, {
      method,
      bearer: token,
      body,
    });
    return NextResponse.json(data ?? {});
  } catch (err) {
    const e = err as ApiError;
    if (e.status === 401) {
      clearSessionCookies();
    }
    return NextResponse.json(
      { detail: e.detail || "Erro" },
      { status: e.status || 500 },
    );
  }
}

export async function GET(req: NextRequest, ctx: { params: { path: string[] } }) {
  return handle(req, ctx, "GET");
}
export async function POST(req: NextRequest, ctx: { params: { path: string[] } }) {
  return handle(req, ctx, "POST");
}
export async function PATCH(req: NextRequest, ctx: { params: { path: string[] } }) {
  return handle(req, ctx, "PATCH");
}
export async function DELETE(req: NextRequest, ctx: { params: { path: string[] } }) {
  return handle(req, ctx, "DELETE");
}
