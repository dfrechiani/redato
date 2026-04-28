import { NextResponse } from "next/server";

import { fetchBackend } from "@/lib/api";
import { ApiError, type ResetSolicitarRequest } from "@/types/api";

export async function POST(req: Request): Promise<NextResponse> {
  let body: ResetSolicitarRequest;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ detail: "Payload inválido" }, { status: 400 });
  }
  try {
    const resp = await fetchBackend<{ sucesso: boolean }>(
      "/auth/reset-password/solicitar",
      { method: "POST", body },
    );
    return NextResponse.json(resp);
  } catch (err) {
    const e = err as ApiError;
    return NextResponse.json(
      { detail: e.detail || "Erro" },
      { status: e.status || 500 },
    );
  }
}
