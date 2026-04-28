/**
 * Tipos do portal (M6) — espelham os Pydantic schemas em
 * `redato_backend/portal/portal_api.py`.
 */

export type AtividadeStatus = "agendada" | "ativa" | "encerrada";

export interface Missao {
  id: string;
  codigo: string;
  serie: string;
  oficina_numero: number;
  titulo: string;
  modo_correcao: string;
}

export interface TurmaListItem {
  id: string;
  codigo: string;
  serie: string;
  codigo_join: string;
  ano_letivo: number;
  ativa: boolean;
  n_alunos: number;
  n_atividades_ativas: number;
  n_atividades_encerradas: number;
  professor_id: string;
  professor_nome: string;
}

export interface AlunoTurma {
  id: string;
  nome: string;
  telefone_mascarado: string;
  vinculado_em: string;
  ativo: boolean;
  n_envios: number;
}

export interface AtividadeListItem {
  id: string;
  missao_id: string;
  missao_codigo: string;
  missao_titulo: string;
  oficina_numero: number;
  modo_correcao: string;
  data_inicio: string;
  data_fim: string;
  status: AtividadeStatus;
  n_envios: number;
  notificacao_enviada_em: string | null;
}

export interface TurmaDetail {
  id: string;
  codigo: string;
  serie: string;
  codigo_join: string;
  ano_letivo: number;
  ativa: boolean;
  professor_id: string;
  professor_nome: string;
  escola_id: string;
  escola_nome: string;
  pode_criar_atividade: boolean;
  alunos: AlunoTurma[];
  atividades: AtividadeListItem[];
}

export interface CriarAtividadeRequest {
  turma_id: string;
  missao_id: string;
  data_inicio: string; // ISO 8601
  data_fim: string;
  notificar_alunos: boolean;
  confirmar_duplicata?: boolean;
}

export interface CriarAtividadeResponse {
  id: string | null;
  duplicate_warning: boolean;
  duplicata_atividade_id: string | null;
  notificacao_disparada: boolean;
  notificacao_enviadas: number;
}

export interface PatchAtividadeRequest {
  data_inicio?: string;
  data_fim?: string;
}

export interface EnvioListItem {
  aluno_turma_id: string;
  aluno_nome: string;
  envio_id: string | null;
  enviado_em: string | null;
  nota_total: number | null;
  faixa: string;
  tem_feedback: boolean;
}

export type DistribuicaoNotas = Record<string, number>;

export interface AtividadeDetail {
  id: string;
  turma_id: string;
  turma_codigo: string;
  turma_serie: string;
  escola_nome: string;
  professor_nome: string;
  missao_id: string;
  missao_codigo: string;
  missao_titulo: string;
  oficina_numero: number;
  modo_correcao: string;
  data_inicio: string;
  data_fim: string;
  status: AtividadeStatus;
  notificacao_enviada_em: string | null;
  pode_editar: boolean;
  n_alunos_total: number;
  n_enviados: number;
  n_pendentes: number;
  distribuicao: DistribuicaoNotas;
  top_detectores: Array<{ detector: string; ocorrencias: number }>;
  envios: EnvioListItem[];
}

export interface FaixaQualitativa {
  competencia: string;
  nota: number | null;
  faixa: string;
}

export interface EnvioFeedback {
  atividade_id: string;
  missao_codigo: string;
  missao_titulo: string;
  oficina_numero: number;
  modo_correcao: string;
  aluno_id: string;
  aluno_nome: string;
  enviado_em: string | null;
  foto_path: string | null;
  foto_hash: string | null;
  texto_transcrito: string | null;
  nota_total: number | null;
  faixas: FaixaQualitativa[];
  audit_pedagogico: string | null;
  detectores: Array<{
    detector: string;
    codigo?: string;
    nome?: string;
    categoria?: string;
    severidade?: string;
    canonical?: boolean;
    detalhe?: string | null;
  }>;
  ocr_quality_issues: string[];
  raw_output: Record<string, unknown> | null;
}

// ──────────────────────────────────────────────────────────────────────
// M7 — Dashboards
// ──────────────────────────────────────────────────────────────────────

export type ModoBucket = "foco" | "completo";

export interface TopDetector {
  codigo: string;
  nome: string;
  contagem: number;
}

export interface AlunoEmRisco {
  aluno_id: string;
  nome: string;
  n_missoes_baixa: number;
  ultima_nota: number | null;
}

export interface EvolucaoPonto {
  atividade_id: string;
  missao_codigo: string;
  missao_titulo: string;
  modo: string;
  data: string;
  nota_media: number;
  n_envios: number;
}

export interface DistribuicaoPorModo {
  foco: Record<string, number>;
  completo: Record<string, number>;
}

export interface TurmaDashboard {
  turma: { id: string; codigo: string; n_alunos_ativos: number };
  atividades_total: number;
  atividades_ativas: number;
  atividades_encerradas: number;
  distribuicao_notas: DistribuicaoPorModo;
  top_detectores: TopDetector[];
  outros_detectores: number;
  alunos_em_risco: AlunoEmRisco[];
  evolucao_turma: EvolucaoPonto[];
  n_envios_total: number;
}

export interface TurmaResumoEscola {
  turma_id: string;
  codigo: string;
  serie: string;
  professor_nome: string;
  media_geral: number | null;
  n_atividades: number;
  n_em_risco: number;
}

export interface ComparacaoTurma {
  turma_codigo: string;
  turma_id: string;
  media: number;
  n_envios: number;
}

export interface EscolaDashboard {
  escola: {
    id: string;
    nome: string;
    n_turmas: number;
    n_alunos_ativos: number;
  };
  turmas_resumo: TurmaResumoEscola[];
  distribuicao_notas_escola: DistribuicaoPorModo;
  top_detectores_escola: TopDetector[];
  outros_detectores_escola: number;
  alunos_em_risco_escola: AlunoEmRisco[];
  evolucao_escola: EvolucaoPonto[];
  comparacao_turmas: ComparacaoTurma[];
}

export interface EvolucaoEnvio {
  atividade_id: string;
  missao_codigo: string;
  missao_titulo: string;
  oficina_numero: number;
  modo: string;
  data: string;
  nota: number | null;
  faixa: string;
  detectores: string[];
}

export interface EvolucaoChartPonto {
  data: string;
  nota: number;
  missao_codigo: string;
}

export interface MissaoPendente {
  atividade_id: string;
  missao_codigo: string;
  missao_titulo: string;
  oficina_numero: number;
  modo_correcao: string;
  data_fim: string;
  status: AtividadeStatus;
}

export interface AlunoEvolucao {
  aluno: { id: string; nome: string };
  envios: EvolucaoEnvio[];
  evolucao_chart: EvolucaoChartPonto[];
  n_missoes_realizadas: number;
  missoes_pendentes: MissaoPendente[];
}

// ──────────────────────────────────────────────────────────────────────
// M8 — PDF
// ──────────────────────────────────────────────────────────────────────

export type PdfTipo =
  | "dashboard_turma"
  | "dashboard_escola"
  | "evolucao_aluno"
  | "atividade_detalhe";

export interface GerarPdfRequest {
  periodo_inicio?: string | null;
  periodo_fim?: string | null;
}

export interface GerarPdfResponse {
  pdf_id: string;
  download_url: string;
  tamanho_bytes: number;
}

export interface PdfHistoricoItem {
  id: string;
  tipo: PdfTipo;
  escopo_id: string;
  gerado_em: string;
  gerado_por_user_id: string;
  tamanho_bytes: number;
  download_url: string;
}
