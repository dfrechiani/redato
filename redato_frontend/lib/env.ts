/**
 * Variáveis de ambiente. Tudo em um lugar pra fácil auditoria.
 *
 * - `API_BASE`: URL do backend FastAPI (server-side e client-side).
 * - `SESSION_COOKIE`: nome do cookie httpOnly que guarda o JWT.
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8091";

export const SESSION_COOKIE =
  process.env.REDATO_SESSION_COOKIE ?? "redato_session";

export const SESSION_USER_COOKIE = `${SESSION_COOKIE}_user`;
