/**
 * Proxy /api/auth/perfil/* → backend /auth/perfil/*. Cookie httpOnly de
 * sessão é usado pro Bearer.
 *
 * Métodos suportados:
 * - POST: mudar-senha, sair-todas-sessoes
 * - PATCH: telefone (M10 — vincular telefone WhatsApp)
 * - DELETE: telefone (M10 — desvincular)
 *
 * Caso especial: sair-todas-sessoes (POST) invalida tokens emitidos
 * antes do horário do POST. Aqui no proxy também limpamos o cookie
 * local — o token atual foi invalidado server-side e a próxima
 * request /auth/me daria 401.
 *
 * Bug fix 02/05/2026: PATCH e DELETE estavam ausentes desse proxy,
 * resultado era 405 Method Not Allowed quando portal tentava
 * vincular telefone. Next.js App Router precisa de export por
 * método HTTP — não há fallback genérico.
 */

import { NextResponse, type NextRequest } from "next/server";

import { fetchBackend } from "@/lib/api";
import { clearSessionCookies, getSessionToken } from "@/lib/auth-server";
import { ApiError } from "@/types/api";


type Method = "POST" | "PATCH" | "DELETE";

async function proxy(
  req: NextRequest,
  params: { path: string[] },
  method: Method,
): Promise<NextResponse> {
  const token = getSessionToken();
  if (!token) {
    return NextResponse.json({ detail: "Não autenticado" }, { status: 401 });
  }

  const subpath = (params.path || []).join("/");
  const target = `/auth/perfil/${subpath}`;

  // DELETE convencionalmente sem body — mas se vier, repassa.
  let body: unknown = undefined;
  const text = await req.text();
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      return NextResponse.json({ detail: "Payload inválido" }, { status: 400 });
    }
  }

  try {
    const data = await fetchBackend<unknown>(target, {
      method,
      bearer: token,
      body: body !== undefined ? body : (method === "POST" ? {} : undefined),
    });
    // sair-todas-sessoes invalida sessão atual também
    if (method === "POST" && subpath === "sair-todas-sessoes") {
      clearSessionCookies();
    }
    // DELETE → 204 No Content sem body
    if (method === "DELETE") {
      return new NextResponse(null, { status: 204 });
    }
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


export async function POST(
  req: NextRequest,
  { params }: { params: { path: string[] } },
): Promise<NextResponse> {
  return proxy(req, params, "POST");
}


export async function PATCH(
  req: NextRequest,
  { params }: { params: { path: string[] } },
): Promise<NextResponse> {
  return proxy(req, params, "PATCH");
}


export async function DELETE(
  req: NextRequest,
  { params }: { params: { path: string[] } },
): Promise<NextResponse> {
  return proxy(req, params, "DELETE");
}
