/**
 * Proxy específico pra foto da redação (binário).
 *
 * O proxy genérico em `app/api/portal/[...path]/route.ts` só
 * suporta JSON via `NextResponse.json()` e o `fetchBackend` exige
 * Content-Type application/json. Pra arquivos (jpg/png/webp) precisa
 * passthrough do body bruto + headers de content-type/length.
 *
 * Esta rota:
 * 1. Pega o JWT do cookie httpOnly (via auth-server)
 * 2. Faz fetch direto pro backend `/portal/atividades/.../foto`
 * 3. Retorna a Response do backend praticamente intacta — só
 *    troca os headers que importam pra browser cachear/exibir
 *
 * Em 401 limpa cookies (mesmo padrão do proxy genérico).
 */

import { NextResponse, type NextRequest } from "next/server";

import { clearSessionCookies, getSessionToken } from "@/lib/auth-server";
import { API_BASE } from "@/lib/env";

interface Params {
  atividade_id: string;
  aluno_id: string;
}

export async function GET(
  _req: NextRequest,
  { params }: { params: Params },
): Promise<Response> {
  const token = getSessionToken();
  if (!token) {
    return NextResponse.json(
      { detail: "Não autenticado" },
      { status: 401 },
    );
  }

  const url =
    `${API_BASE}/portal/atividades/${encodeURIComponent(params.atividade_id)}` +
    `/envios/${encodeURIComponent(params.aluno_id)}/foto`;

  let upstream: Response;
  try {
    upstream = await fetch(url, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
  } catch (err) {
    return NextResponse.json(
      { detail: `Falha de rede: ${(err as Error).message}` },
      { status: 502 },
    );
  }

  if (upstream.status === 401) {
    clearSessionCookies();
    return NextResponse.json(
      { detail: "Sessão expirada" },
      { status: 401 },
    );
  }

  // Erros não-OK: tenta repassar JSON do FastAPI (detalhe legível).
  if (!upstream.ok) {
    let detail = `Erro ${upstream.status}`;
    try {
      const body = await upstream.json();
      if (body && typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // 410, 502, etc. sem corpo — usa default
    }
    return NextResponse.json(
      { detail },
      { status: upstream.status },
    );
  }

  // Passthrough do binário. Preserva content-type detectado pelo
  // backend (image/jpeg, image/png, etc.) pra browser exibir <img>
  // corretamente.
  const contentType =
    upstream.headers.get("content-type") ?? "application/octet-stream";
  const buffer = await upstream.arrayBuffer();
  return new Response(buffer, {
    status: 200,
    headers: {
      "content-type": contentType,
      // Cache curto — foto não muda mas evita stale durante deploys
      // ou re-envio do aluno. Browser revalida a cada 5 min.
      "cache-control": "private, max-age=300",
    },
  });
}
