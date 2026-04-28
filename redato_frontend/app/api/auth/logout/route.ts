import { NextResponse } from "next/server";

import { fetchBackend } from "@/lib/api";
import { clearSessionCookies, getSessionToken } from "@/lib/auth-server";

export async function POST(): Promise<NextResponse> {
  const token = getSessionToken();
  if (token) {
    try {
      await fetchBackend<{ sucesso: boolean }>("/auth/logout", {
        method: "POST",
        bearer: token,
      });
    } catch {
      // Token já expirou ou backend offline — limpa cookie local mesmo assim.
    }
  }
  clearSessionCookies();
  return NextResponse.json({ sucesso: true });
}
