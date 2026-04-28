"use client";

/**
 * Wrapper client-side: chama as rotas locais `/api/auth/*` (proxy).
 *
 * O JWT NÃO é manipulado aqui — vive em cookie httpOnly. Erros 401
 * disparam logout local + redirect pra /login.
 */

import { ApiError, type ApiErrorBody } from "@/types/api";
import type {
  AuthenticatedUser,
  PrimeiroAcessoValidarResponse,
} from "@/types/api";

interface FetchOpts {
  method?: "GET" | "POST";
  body?: unknown;
}

async function fetchJson<T>(path: string, opts: FetchOpts = {}): Promise<T> {
  const { method = "GET", body } = opts;

  const init: RequestInit = {
    method,
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    credentials: "same-origin",
  };
  if (body !== undefined) init.body = JSON.stringify(body);

  let resp: Response;
  try {
    resp = await fetch(path, init);
  } catch (err) {
    throw new ApiError(0, `Falha de rede: ${(err as Error).message}`);
  }

  if (resp.status === 204) return undefined as T;

  let data: unknown;
  const text = await resp.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      throw new ApiError(resp.status, "Resposta inesperada do servidor");
    }
  }

  if (!resp.ok) {
    const detail = (data as ApiErrorBody | undefined)?.detail
      ?? `Erro ${resp.status}`;
    throw new ApiError(resp.status, detail);
  }
  return data as T;
}

// ──────────────────────────────────────────────────────────────────────
// Auth API (proxy local)
// ──────────────────────────────────────────────────────────────────────

export async function login(
  email: string,
  senha: string,
  lembrar_de_mim: boolean,
): Promise<AuthenticatedUser> {
  return fetchJson<AuthenticatedUser>("/api/auth/login", {
    method: "POST",
    body: { email, senha, lembrar_de_mim },
  });
}

export async function logout(): Promise<void> {
  await fetchJson<void>("/api/auth/logout", { method: "POST" });
}

export async function me(): Promise<AuthenticatedUser> {
  return fetchJson<AuthenticatedUser>("/api/auth/me");
}

export async function resetSolicitar(email: string): Promise<void> {
  await fetchJson<void>("/api/auth/reset-password/solicitar", {
    method: "POST",
    body: { email },
  });
}

export async function resetConfirmar(
  token: string,
  senha_nova: string,
): Promise<void> {
  await fetchJson<void>("/api/auth/reset-password/confirmar", {
    method: "POST",
    body: { token, senha_nova },
  });
}

export async function primeiroAcessoValidar(
  token: string,
): Promise<PrimeiroAcessoValidarResponse> {
  return fetchJson<PrimeiroAcessoValidarResponse>(
    "/api/auth/primeiro-acesso/validar",
    { method: "POST", body: { token } },
  );
}

export async function primeiroAcessoDefinir(
  token: string,
  senha: string,
): Promise<void> {
  await fetchJson<void>("/api/auth/primeiro-acesso/definir-senha", {
    method: "POST",
    body: { token, senha },
  });
}

// ──────────────────────────────────────────────────────────────────────
// Validação local de senha (antes de chamar backend)
// ──────────────────────────────────────────────────────────────────────

/**
 * Mesma regra que `validate_senha` do backend: 8+ chars, 1 letra, 1 número.
 * Devolve `null` se OK ou string de erro pra exibir.
 */
export function validarSenhaLocal(senha: string): string | null {
  if (senha.length < 8) return "Senha precisa ter pelo menos 8 caracteres.";
  if (!/[A-Za-z]/.test(senha)) return "Senha precisa ter pelo menos 1 letra.";
  if (!/[0-9]/.test(senha)) return "Senha precisa ter pelo menos 1 número.";
  return null;
}
