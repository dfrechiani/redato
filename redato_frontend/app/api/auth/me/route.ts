import { NextResponse } from "next/server";

import { fetchBackend } from "@/lib/api";
import { clearSessionCookies, getSessionToken } from "@/lib/auth-server";
import { ApiError, type AuthenticatedUser } from "@/types/api";

export async function GET(): Promise<NextResponse> {
  const token = getSessionToken();
  if (!token) {
    return NextResponse.json(
      { detail: "Não autenticado" },
      { status: 401 },
    );
  }

  try {
    const me = await fetchBackend<AuthenticatedUser>("/auth/me", {
      bearer: token,
    });
    return NextResponse.json(me);
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
