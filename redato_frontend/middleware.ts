import { NextResponse, type NextRequest } from "next/server";

import { SESSION_COOKIE } from "@/lib/env";

/**
 * Rotas públicas (sem auth). Tudo o mais exige cookie de sessão.
 */
const PUBLIC_PATHS = [
  "/login",
  "/primeiro-acesso",
  "/reset-password",
];

function isPublic(pathname: string): boolean {
  return PUBLIC_PATHS.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`),
  );
}

export function middleware(req: NextRequest): NextResponse {
  const { pathname, search } = req.nextUrl;

  // Esses paths já são filtrados pelo matcher, mas guardamos defensivamente.
  if (
    pathname.startsWith("/_next")
    || pathname.startsWith("/api")
    || pathname.startsWith("/favicon")
    || pathname === "/robots.txt"
  ) {
    return NextResponse.next();
  }

  const hasSession = Boolean(req.cookies.get(SESSION_COOKIE)?.value);

  // Autenticado tentando ir pra /login → manda pra home.
  if (hasSession && pathname === "/login") {
    return NextResponse.redirect(new URL("/", req.url));
  }

  if (isPublic(pathname)) {
    return NextResponse.next();
  }

  if (!hasSession) {
    const url = new URL("/login", req.url);
    url.searchParams.set("from", pathname + (search || ""));
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    // Tudo exceto _next/, /api, arquivos estáticos.
    "/((?!_next/static|_next/image|favicon.ico|robots.txt|api/).*)",
  ],
};
