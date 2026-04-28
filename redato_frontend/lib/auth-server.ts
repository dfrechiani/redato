/**
 * Helpers server-side de auth: cookie do JWT + chamadas autenticadas.
 *
 * O JWT é guardado num cookie httpOnly (não acessível por JS). Apenas
 * route handlers e Server Components/Middleware leem ele.
 */

import type { ResponseCookie } from "next/dist/compiled/@edge-runtime/cookies";
import { cookies } from "next/headers";

import type { AuthenticatedUser } from "@/types/api";
import { SESSION_COOKIE, SESSION_USER_COOKIE } from "./env";

const SESSION_DEFAULT_MAX_AGE = 8 * 60 * 60; // 8h
const SESSION_REMEMBER_MAX_AGE = 30 * 24 * 60 * 60; // 30 dias

interface CookieAttrs {
  maxAgeSeconds: number;
}

function baseCookieAttrs(maxAgeSeconds: number): Partial<ResponseCookie> {
  return {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: maxAgeSeconds,
  };
}

/**
 * Salva token + user info em cookies. O user cookie NÃO é httpOnly pra
 * permitir leitura otimista no client (não confia, só pra renderizar).
 * Validação real continua via /api/auth/me.
 */
export function setSessionCookies(
  token: string,
  user: AuthenticatedUser,
  attrs: CookieAttrs,
): void {
  const jar = cookies();
  jar.set(SESSION_COOKIE, token, baseCookieAttrs(attrs.maxAgeSeconds));
  jar.set(SESSION_USER_COOKIE, JSON.stringify(user), {
    ...baseCookieAttrs(attrs.maxAgeSeconds),
    httpOnly: false, // legível pelo client pra renderizar nome
  });
}

export function clearSessionCookies(): void {
  const jar = cookies();
  jar.delete(SESSION_COOKIE);
  jar.delete(SESSION_USER_COOKIE);
}

export function getSessionToken(): string | undefined {
  return cookies().get(SESSION_COOKIE)?.value;
}

export function getSessionUserOptional(): AuthenticatedUser | null {
  const raw = cookies().get(SESSION_USER_COOKIE)?.value;
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthenticatedUser;
  } catch {
    return null;
  }
}

export function maxAgeFromLembrar(lembrar_de_mim: boolean): number {
  return lembrar_de_mim ? SESSION_REMEMBER_MAX_AGE : SESSION_DEFAULT_MAX_AGE;
}
