import { NextResponse } from "next/server";

import { fetchBackend } from "@/lib/api";
import {
  maxAgeFromLembrar,
  setSessionCookies,
} from "@/lib/auth-server";
import { ApiError } from "@/types/api";
import type {
  AuthenticatedUser,
  LoginRequest,
  LoginResponse,
} from "@/types/api";

export async function POST(req: Request): Promise<NextResponse> {
  let body: LoginRequest;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ detail: "Payload inválido" }, { status: 400 });
  }

  if (!body.email || !body.senha) {
    return NextResponse.json(
      { detail: "Email e senha obrigatórios" },
      { status: 400 },
    );
  }

  let resp: LoginResponse;
  try {
    resp = await fetchBackend<LoginResponse>("/auth/login", {
      method: "POST",
      body,
    });
  } catch (err) {
    const e = err as ApiError;
    return NextResponse.json(
      { detail: e.detail || "Erro ao autenticar" },
      { status: e.status || 500 },
    );
  }

  const me = await fetchBackend<AuthenticatedUser>("/auth/me", {
    bearer: resp.access_token,
  });

  setSessionCookies(resp.access_token, me, {
    maxAgeSeconds: maxAgeFromLembrar(body.lembrar_de_mim),
  });

  return NextResponse.json(me, { status: 200 });
}
