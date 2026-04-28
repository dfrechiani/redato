/**
 * Proxy /api/auth/perfil/* → backend /auth/perfil/*. Cookie httpOnly de
 * sessão é usado pro Bearer.
 *
 * Casos:
 * - mudar-senha: senha_atual + senha_nova
 * - sair-todas-sessoes: invalida tokens emitidos antes do horário do
 *   POST. Aqui no proxy também limpamos o cookie local — o token atual
 *   foi invalidado server-side e a próxima request /auth/me daria 401.
 */

import { NextResponse, type NextRequest } from "next/server";

import { fetchBackend } from "@/lib/api";
import { clearSessionCookies, getSessionToken } from "@/lib/auth-server";
import { ApiError } from "@/types/api";

export async function POST(
  req: NextRequest,
  { params }: { params: { path: string[] } },
): Promise<NextResponse> {
  const token = getSessionToken();
  if (!token) {
    return NextResponse.json({ detail: "Não autenticado" }, { status: 401 });
  }

  const subpath = (params.path || []).join("/");
  const target = `/auth/perfil/${subpath}`;

  let body: unknown = {};
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
      method: "POST",
      bearer: token,
      body,
    });
    // sair-todas-sessoes invalida sessão atual também
    if (subpath === "sair-todas-sessoes") {
      clearSessionCookies();
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
