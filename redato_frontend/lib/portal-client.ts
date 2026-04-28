"use client";

/**
 * Cliente HTTP do /api/portal/* (browser → proxy local).
 *
 * Em qualquer 401, dispara redirect duro pro /login (sessão invalidada,
 * token revogado, ou cookie expirado).
 */

import { ApiError, type ApiErrorBody } from "@/types/api";
import type {
  AlunoEvolucao,
  AtividadeDetail,
  AtividadeListItem,
  CriarAtividadeRequest,
  CriarAtividadeResponse,
  EnvioFeedback,
  EscolaDashboard,
  Missao,
  PatchAtividadeRequest,
  TurmaDashboard,
  TurmaDetail,
  TurmaListItem,
} from "@/types/portal";

interface FetchOpts {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
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
      throw new ApiError(resp.status, "Resposta inesperada");
    }
  }

  if (!resp.ok) {
    const detail = (data as ApiErrorBody | undefined)?.detail
      ?? `Erro ${resp.status}`;
    // /perfil/mudar-senha pode devolver 401 quando a senha atual está
    // errada — isso NÃO é "sessão expirada", então não redirecionamos.
    const isMudarSenha = path.endsWith("/mudar-senha");
    if (resp.status === 401 && !isMudarSenha && typeof window !== "undefined") {
      const from = encodeURIComponent(window.location.pathname);
      window.location.href = `/login?from=${from}`;
    }
    throw new ApiError(resp.status, detail);
  }
  return data as T;
}

// ──────────────────────────────────────────────────────────────────────
// Missões
// ──────────────────────────────────────────────────────────────────────

export async function listarMissoes(serie?: string): Promise<Missao[]> {
  // Filtro opcional por série (1S/2S/3S). Frontend usa pra restringir
  // dropdown do AtivarMissaoModal à série da turma — turma 1S não vê
  // missões 2S/3S e vice-versa.
  const qs = serie ? `?serie=${encodeURIComponent(serie)}` : "";
  return fetchJson<Missao[]>(`/api/portal/missoes${qs}`);
}

// ──────────────────────────────────────────────────────────────────────
// Turmas
// ──────────────────────────────────────────────────────────────────────

export async function listarTurmas(): Promise<TurmaListItem[]> {
  return fetchJson<TurmaListItem[]>("/api/portal/turmas");
}

export async function detalheTurma(turmaId: string): Promise<TurmaDetail> {
  return fetchJson<TurmaDetail>(`/api/portal/turmas/${turmaId}`);
}

export async function inativarAluno(
  turmaId: string,
  alunoId: string,
  ativo: boolean,
): Promise<void> {
  await fetchJson<void>(
    `/api/portal/turmas/${turmaId}/alunos/${alunoId}`,
    { method: "PATCH", body: { ativo } },
  );
}

// ──────────────────────────────────────────────────────────────────────
// Atividades
// ──────────────────────────────────────────────────────────────────────

export async function criarAtividade(
  body: CriarAtividadeRequest,
): Promise<CriarAtividadeResponse> {
  return fetchJson<CriarAtividadeResponse>("/api/portal/atividades", {
    method: "POST",
    body,
  });
}

export async function detalheAtividade(
  atividadeId: string,
): Promise<AtividadeDetail> {
  return fetchJson<AtividadeDetail>(`/api/portal/atividades/${atividadeId}`);
}

export async function patchAtividade(
  atividadeId: string,
  body: PatchAtividadeRequest,
): Promise<AtividadeListItem> {
  return fetchJson<AtividadeListItem>(
    `/api/portal/atividades/${atividadeId}`,
    { method: "PATCH", body },
  );
}

export async function encerrarAtividade(
  atividadeId: string,
): Promise<AtividadeListItem> {
  return fetchJson<AtividadeListItem>(
    `/api/portal/atividades/${atividadeId}/encerrar`,
    { method: "POST" },
  );
}

export async function notificarAtividade(
  atividadeId: string,
): Promise<{ enviadas: number; ja_notificada_em: string | null }> {
  return fetchJson(
    `/api/portal/atividades/${atividadeId}/notificar`,
    { method: "POST" },
  );
}

export async function envioFeedback(
  atividadeId: string,
  alunoTurmaId: string,
): Promise<EnvioFeedback> {
  return fetchJson<EnvioFeedback>(
    `/api/portal/atividades/${atividadeId}/envios/${alunoTurmaId}`,
  );
}

// ──────────────────────────────────────────────────────────────────────
// Dashboards (M7)
// ──────────────────────────────────────────────────────────────────────

export async function dashboardTurma(
  turmaId: string,
): Promise<TurmaDashboard> {
  return fetchJson<TurmaDashboard>(`/api/portal/turmas/${turmaId}/dashboard`);
}

export async function dashboardEscola(
  escolaId: string,
): Promise<EscolaDashboard> {
  return fetchJson<EscolaDashboard>(`/api/portal/escolas/${escolaId}/dashboard`);
}

export async function evolucaoAluno(
  turmaId: string,
  alunoTurmaId: string,
): Promise<AlunoEvolucao> {
  return fetchJson<AlunoEvolucao>(
    `/api/portal/turmas/${turmaId}/alunos/${alunoTurmaId}/evolucao`,
  );
}

// ──────────────────────────────────────────────────────────────────────
// PDFs (M8)
// ──────────────────────────────────────────────────────────────────────

import type {
  GerarPdfRequest,
  GerarPdfResponse,
  PdfHistoricoItem,
  PdfTipo,
} from "@/types/portal";

export async function gerarPdfDashboardTurma(
  turmaId: string,
  body: GerarPdfRequest = {},
): Promise<GerarPdfResponse> {
  return fetchJson<GerarPdfResponse>(
    `/api/portal/pdfs/dashboard-turma/${turmaId}`,
    { method: "POST", body },
  );
}

export async function gerarPdfDashboardEscola(
  escolaId: string,
  body: GerarPdfRequest = {},
): Promise<GerarPdfResponse> {
  return fetchJson<GerarPdfResponse>(
    `/api/portal/pdfs/dashboard-escola/${escolaId}`,
    { method: "POST", body },
  );
}

export async function gerarPdfEvolucaoAluno(
  turmaId: string,
  alunoTurmaId: string,
  body: GerarPdfRequest = {},
): Promise<GerarPdfResponse> {
  return fetchJson<GerarPdfResponse>(
    `/api/portal/pdfs/evolucao-aluno/${turmaId}/${alunoTurmaId}`,
    { method: "POST", body },
  );
}

export async function listarPdfsHistorico(
  filtros: { tipo?: PdfTipo; escopo_id?: string; limit?: number } = {},
): Promise<PdfHistoricoItem[]> {
  const qs = new URLSearchParams();
  if (filtros.tipo) qs.set("tipo", filtros.tipo);
  if (filtros.escopo_id) qs.set("escopo_id", filtros.escopo_id);
  if (filtros.limit) qs.set("limit", String(filtros.limit));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return fetchJson<PdfHistoricoItem[]>(`/api/portal/pdfs/historico${suffix}`);
}

/** Caminho local pra abrir o PDF via proxy do Next.js (anexa cookie). */
export function pdfDownloadUrl(pdfId: string): string {
  return `/api/portal/pdfs/${pdfId}/download`;
}

// ──────────────────────────────────────────────────────────────────────
// Perfil
// ──────────────────────────────────────────────────────────────────────

export async function mudarSenha(
  senha_atual: string,
  senha_nova: string,
): Promise<void> {
  await fetchJson<void>("/api/auth/perfil/mudar-senha", {
    method: "POST",
    body: { senha_atual, senha_nova },
  });
}

export async function sairTodasSessoes(): Promise<void> {
  await fetchJson<void>("/api/auth/perfil/sair-todas-sessoes", {
    method: "POST",
  });
}

// ──────────────────────────────────────────────────────────────────────
// Helpers de formatação re-exportados pra compat
// ──────────────────────────────────────────────────────────────────────
// Os helpers vivem em `lib/format.ts` (sem "use client") pra serem
// importáveis também em Server Components. Re-exportamos aqui pra que
// callers existentes não precisem ajustar imports.

export { formatDateInput, formatPrazo, formatPrazoCurto } from "./format";
