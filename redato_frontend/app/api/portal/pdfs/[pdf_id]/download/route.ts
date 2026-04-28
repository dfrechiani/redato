/**
 * Proxy /api/portal/pdfs/{id}/download — streaming binário.
 *
 * Diferente do catch-all `/api/portal/[...path]` que parseia JSON,
 * este proxy preserva o body como bytes e copia content-type +
 * content-disposition do backend. Necessário pra que o browser baixe
 * o arquivo com nome correto.
 */

import { NextResponse, type NextRequest } from "next/server";

import { API_BASE } from "@/lib/env";
import { getSessionToken } from "@/lib/auth-server";

export async function GET(
  _req: NextRequest,
  { params }: { params: { pdf_id: string } },
): Promise<NextResponse | Response> {
  const token = getSessionToken();
  if (!token) {
    return NextResponse.json({ detail: "Não autenticado" }, { status: 401 });
  }

  const upstream = await fetch(
    `${API_BASE}/portal/pdfs/${params.pdf_id}/download`,
    {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    },
  );

  if (!upstream.ok) {
    let detail = `Erro ${upstream.status}`;
    try {
      const j = await upstream.json();
      detail = j.detail ?? detail;
    } catch {
      /* não-JSON */
    }
    return NextResponse.json({ detail }, { status: upstream.status });
  }

  const headers = new Headers();
  const ct = upstream.headers.get("content-type") ?? "application/pdf";
  headers.set("content-type", ct);
  const cd = upstream.headers.get("content-disposition");
  if (cd) headers.set("content-disposition", cd);

  return new Response(upstream.body, { status: 200, headers });
}
