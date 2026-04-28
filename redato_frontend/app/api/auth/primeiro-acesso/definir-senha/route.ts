import { NextResponse } from "next/server";

import { fetchBackend } from "@/lib/api";
import {
  ApiError,
  type PrimeiroAcessoDefinirRequest,
  type PrimeiroAcessoDefinirResponse,
} from "@/types/api";

export async function POST(req: Request): Promise<NextResponse> {
  let body: PrimeiroAcessoDefinirRequest;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ detail: "Payload inválido" }, { status: 400 });
  }
  try {
    const resp = await fetchBackend<PrimeiroAcessoDefinirResponse>(
      "/auth/primeiro-acesso/definir-senha",
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
