/**
 * Tipos compartilhados com o backend M3 (FastAPI / Pydantic).
 *
 * Mantidos manualmente — quando o backend mudar contratos, atualize aqui.
 * Erros vêm sempre como `{ detail: string }` (FastAPI default).
 */

export type Papel = "coordenador" | "professor";

export interface AuthenticatedUser {
  id: string;
  nome: string;
  email: string;
  papel: Papel;
  escola_id: string;
  escola_nome: string;
}

// POST /auth/login
export interface LoginRequest {
  email: string;
  senha: string;
  lembrar_de_mim: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number; // segundos
  papel: Papel;
  nome: string;
  escola_id: string;
}

// POST /auth/primeiro-acesso/validar
export interface PrimeiroAcessoValidarRequest {
  token: string;
}

export interface PrimeiroAcessoValidarResponse {
  valido: boolean;
  email: string | null;
  nome: string | null;
  papel: Papel | null;
  escola_nome: string | null;
}

// POST /auth/primeiro-acesso/definir-senha
export interface PrimeiroAcessoDefinirRequest {
  token: string;
  senha: string;
}

export interface PrimeiroAcessoDefinirResponse {
  sucesso: boolean;
  redirect_to: string;
}

// POST /auth/reset-password/solicitar
export interface ResetSolicitarRequest {
  email: string;
}

// POST /auth/reset-password/confirmar
export interface ResetConfirmarRequest {
  token: string;
  senha_nova: string;
}

// Erro do FastAPI
export interface ApiErrorBody {
  detail: string;
}

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
    this.name = "ApiError";
  }
}
