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
  /** false = modo está no catálogo (ex.: foco_c2 da 2S) mas a rubrica
   *  ainda não tem schema/prompt em código. Backend bloqueia ativação;
   *  frontend desabilita opção no dropdown. */
  disponivel_para_ativacao: boolean;
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

/** Resumo curto de uma tentativa anterior do aluno na mesma atividade
 *  (M9.6, 2026-04-29). Frontend renderiza no expansor "Ver tentativas
 *  anteriores"; clicar em uma carrega `?envio_id=xxx` no detalhe. */
export interface TentativaResumo {
  envio_id: string;
  tentativa_n: number;
  /** ISO UTC. UI converte pra BRT pra exibição. */
  enviado_em: string;
  nota_total: number | null;
  /** Preview ~120 chars do texto transcrito. `null` se sem OCR. */
  texto_curto: string | null;
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
  /** URL relativa pro proxy frontend (`/api/portal/...`) que serve a
   *  foto autenticada via JWT-cookie. `null` se não há envio ou
   *  arquivo. NÃO é mais path absoluto do filesystem do backend
   *  (mudança do M9.3, 2026-04-29 — fix tela individual). */
  foto_url: string | null;
  /** Status diagnóstico da foto. Usado pra mostrar mensagem específica
   *  quando foto_url é null. Valores:
   *    "ok" — foto carrega normalmente
   *    "no_envio" — aluno não enviou redação
   *    "not_persisted" — envio existe mas bot não salvou foto_path
   *    "file_missing" — path no DB mas arquivo sumiu do servidor */
  foto_status: "ok" | "no_envio" | "not_persisted" | "file_missing";
  foto_hash: string | null;
  texto_transcrito: string | null;
  nota_total: number | null;
  faixas: FaixaQualitativa[];
  /** Análise da redação (M9.4, antes "audit_pedagogico"). Estrutura
   *  discreta com pontos fortes, pontos fracos, padrão de falha e
   *  transferência. `prosa_completa` é fallback pra outputs legacy
   *  monolíticos. UI mostra estrutura nova quando pontos_fortes ou
   *  pontos_fracos populados; senão mostra prosa_completa. */
  analise_da_redacao: {
    pontos_fortes: string[];
    pontos_fracos: string[];
    padrao_falha: string | null;
    transferencia: string | null;
    prosa_completa: string | null;
  };
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
  /** M9.6 (2026-04-29): suporte a múltiplas tentativas. Por padrão
   *  carrega a tentativa mais recente; `?envio_id=xxx` no detalhe_envio
   *  troca pra uma específica. Pré-M9.6 sempre `tentativa_n=1`,
   *  `tentativa_total=1`, `tentativas_anteriores=[]` — backward-compat.
   *  `envio_id` é null quando aluno não enviou nada ainda. */
  envio_id: string | null;
  tentativa_n: number;
  tentativa_total: number;
  tentativas_anteriores: TentativaResumo[];
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
// M9.7 — Perfil do aluno (drill-down completo da turma)
// Espelha schemas em
// `redato_backend/portal/portal_api.py::AlunoPerfilResponse`.
// ──────────────────────────────────────────────────────────────────────

/** Tendência calculada comparando média das últimas 3 com média das 3
 *  anteriores. `dados_insuficientes` quando aluno tem < 6 envios com
 *  nota válida — ruído alto domina diferenças pequenas. */
export type AlunoTendencia =
  | "subindo"
  | "caindo"
  | "estavel"
  | "dados_insuficientes";

export type CompetenciaKey = "c1" | "c2" | "c3" | "c4" | "c5";

export interface AlunoPerfilResumo {
  id: string;
  nome: string;
  telefone_mascarado: string;
  entrou_em: string;  // ISO UTC
  ativo: boolean;
}

export interface AlunoPerfilStats {
  total_envios: number;
  envios_com_nota: number;
  /** Envios cujo redato_output falhou ou não tem nota_total —
   *  candidatos a reprocessar via POST /portal/envios/{id}/reprocessar. */
  envios_com_problema: number;
  /** Média de nota_total entre envios com nota. `null` se 0 envios
   *  com nota. */
  media_geral: number | null;
  /** Médias por competência. `null` pra competência sem dados (ex.:
   *  aluno só fez foco_c2 → c1, c3, c4, c5 ficam null). */
  medias_cN: Record<CompetenciaKey, number | null>;
  tendencia: AlunoTendencia;
  /** Competência com maior média (ex.: "C2"). `null` se sem dados. */
  ponto_forte: string | null;
  /** Competência com menor média. `null` se sem dados. */
  ponto_fraco: string | null;
}

export interface AlunoPerfilEnvio {
  id: string;            // envio_id (pra reprocessar)
  atividade_id: string;
  atividade_codigo: string;   // ex.: "RJ1·OF14·MF"
  atividade_titulo: string;
  oficina_numero: number;
  modo_correcao: string;
  criado_em: string;     // ISO UTC; UI converte pra BRT
  nota_total: number | null;
  notas_cN: Record<CompetenciaKey, number | null>;
  tem_feedback: boolean;
  /** True se redato_output null/error/sem nota — botão Reprocessar
   *  aparece. */
  tem_problema: boolean;
}

export interface AlunoPerfil {
  aluno: AlunoPerfilResumo;
  stats: AlunoPerfilStats;
  /** Ordenado por `criado_em` desc (mais recente em cima). */
  envios: AlunoPerfilEnvio[];
  /** Último envio do aluno com diagnóstico cognitivo (Fase 3).
   *  `null` se aluno não tem nenhum envio diagnosticado — UI mostra
   *  estado vazio no bloco "Mapa cognitivo". */
  diagnostico_recente: DiagnosticoRecente | null;
}

// ──────────────────────────────────────────────────────────────────────
// Fase 3 — Visualização do diagnóstico cognitivo
// Espelha schemas em `redato_backend/portal/portal_api.py`:
//   DiagnosticoRecente, DiagnosticoVersaoProfessor,
//   DiagnosticoVersaoAluno, DiagnosticoMeta, DiagnosticoOficinaSugerida.
// ──────────────────────────────────────────────────────────────────────

/** Status de cada um dos 40 descritores observáveis pra um envio
 *  específico. Inferido pelo pipeline GPT-4.1 (Fase 2). */
export type DiagnosticoStatus = "dominio" | "lacuna" | "incerto";

/** Confiança do LLM no status atribuído. Alta = 2+ evidências claras;
 *  baixa = texto curto ou sinal ambíguo. */
export type DiagnosticoConfianca = "alta" | "media" | "baixa";

export interface DiagnosticoDescritor {
  id: string;            // ex.: "C5.001"
  status: DiagnosticoStatus;
  /** Trechos LITERAIS do texto da redação. Máx 3. Pode estar vazia
   *  pra `incerto` quando não há sinal suficiente. */
  evidencias: string[];
  confianca: DiagnosticoConfianca;
  /** Fix Fase 3: nome curto do YAML pra heatmap mostrar texto
   *  legível (não só ID). */
  nome: string;
  competencia: string;        // "C1".."C5"
  categoria_inep: string;     // "Desvios gramaticais"
}

/** Card de lacuna prioritária com 3 seções (fix Fase 3 #3): o que
 *  é + evidência + como trabalhar. Pré-resolvido no backend pra
 *  frontend só renderizar. */
export interface DiagnosticoLacunaEnriquecida {
  id: string;
  nome: string;
  competencia: string;
  status: DiagnosticoStatus;
  confianca: DiagnosticoConfianca;
  evidencias: string[];
  /** 1-2 frases iniciais da definição YAML (~150 chars). */
  definicao_curta: string;
  /** 1-2 frases acionáveis: como o professor trabalha a lacuna. */
  sugestao_pedagogica: string;
}

export interface DiagnosticoMeta {
  id: string;            // "M1", "M2", ...
  competencia: string;   // "C1".."C5"
  titulo: string;
  descricao: string;
}

export interface DiagnosticoOficinaSugerida {
  codigo: string;        // ex.: "RJ2·OF12·MF"
  titulo: string;
  modo_correcao: string;
  oficina_numero: number;
  /** Por que essa oficina foi sugerida (ex.: "Trabalha proposta de
   *  intervenção (C5)"). */
  razao: string;
}

export interface DiagnosticoVersaoProfessor {
  /** 40 entries — uma por descritor do YAML, enriquecidas com
   *  nome+competencia+categoria_inep pro heatmap mostrar nome legível. */
  descritores: DiagnosticoDescritor[];
  /** Top 5 IDs com diversidade forçada (max 2 por competência —
   *  fix Fase 3 #2). */
  lacunas_prioritarias: string[];
  /** Mesmo top 5 mas pré-resolvido com nome+definicao_curta+sugestao
   *  pedagógica. Frontend renderiza cards 3 seções direto. */
  lacunas_enriquecidas: DiagnosticoLacunaEnriquecida[];
  resumo_qualitativo: string;
  recomendacao_breve: string;
  oficinas_sugeridas: DiagnosticoOficinaSugerida[];
}

export interface DiagnosticoVersaoAluno {
  /** 0-5 metas em linguagem motivacional. Versão simplificada — sem
   *  status, lacunas, evidências (decisão Daniel). */
  metas: DiagnosticoMeta[];
}

export interface DiagnosticoRecente {
  envio_id: string;
  /** ISO UTC do envio que produziu este diagnóstico. */
  criado_em: string;
  /** Modelo usado (ex.: "gpt-4.1-2025-04-14"). `null` em payloads
   *  legacy sem campo `modelo_usado`. */
  modelo: string | null;
  professor: DiagnosticoVersaoProfessor;
  aluno: DiagnosticoVersaoAluno;
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

// ──────────────────────────────────────────────────────────────────────
// Fase 2 — Jogo "Redação em Jogo"
// Espelha schemas em `redato_backend/portal/jogo_api.py`.
// ──────────────────────────────────────────────────────────────────────

export type StatusPartida =
  | "aguardando_cartas"
  | "aguardando_reescritas"
  | "concluida";

export interface MinideckResumo {
  tema: string;          // slug snake_case (saude_mental, ...)
  nome_humano: string;   // "Saúde Mental"
  serie: string | null;  // "2S"
  descricao: string | null;
  total_cartas: number;  // ~104 quando completo
}

/** Status da reescrita pra um aluno em uma partida (Fase 2 passo 6).
 *  Populado em `PartidaResumo.alunos[]` (dashboard); em
 *  `PartidaDetail.alunos[]` fica null porque já tem `reescritas[]`
 *  separado. */
export type ReescritaStatus =
  | "pendente"          // aluno ainda não enviou
  | "em_avaliacao"      // bot persistiu mas Claude falhou
  | "avaliada";         // reescrita + redato_output presentes

export interface AlunoResumoPartida {
  aluno_turma_id: string;
  nome: string;
  reescrita_status?: ReescritaStatus | null;
}

export interface TentativaReescritaResumo {
  id: string;
  aluno_turma_id: string;
  aluno_nome: string;
  tem_redato_output: boolean;
  enviado_em: string;  // ISO UTC
}

export interface PartidaResumo {
  id: string;
  atividade_id: string;
  tema: string;
  nome_humano_tema: string;
  grupo_codigo: string;
  alunos: AlunoResumoPartida[];
  prazo_reescrita: string;  // ISO UTC
  status_partida: StatusPartida;
  n_reescritas: number;
  n_alunos: number;
  created_at: string;
}

export interface PartidaDetail {
  id: string;
  atividade_id: string;
  tema: string;
  nome_humano_tema: string;
  grupo_codigo: string;
  alunos: AlunoResumoPartida[];
  cartas_escolhidas: string[];   // codes E##/P##/etc — vazia até bot popular
  texto_montado: string;          // vazio até bot popular
  prazo_reescrita: string;
  status_partida: StatusPartida;
  reescritas: TentativaReescritaResumo[];
  created_at: string;
}

export interface PartidaCreatePayload {
  atividade_id: string;
  tema: string;
  grupo_codigo: string;
  alunos_turma_ids: string[];
  prazo_reescrita: string;  // ISO 8601 com offset (BRT)
}

export interface PartidaUpdatePayload {
  grupo_codigo?: string;
  alunos_turma_ids?: string[];
  prazo_reescrita?: string;
}

export interface PartidaCreateResponse {
  id: string;
  partida: PartidaDetail;
}

// ──────────────────────────────────────────────────────────────────────
// Fase 2 passo 6 — detalhe de reescrita (UI do professor)
// Espelha schemas em
// `redato_backend/portal/jogo_api.py::ReescritaDetail`.
// ──────────────────────────────────────────────────────────────────────

/** Carta escolhida pelo grupo. `secao` e `cor` populados apenas pra
 *  estruturais (tipo='ESTRUTURAL'); cartas de lacuna (PROBLEMA,
 *  REPERTORIO, etc.) têm null nesses campos. */
export interface CartaEscolhidaDetail {
  codigo: string;
  tipo:
    | "ESTRUTURAL"
    | "PROBLEMA"
    | "REPERTORIO"
    | "PALAVRA_CHAVE"
    | "AGENTE"
    | "ACAO"
    | "MEIO"
    | "FIM";
  conteudo: string;
  secao: string | null;  // só pra ESTRUTURAL
  cor: string | null;    // só pra ESTRUTURAL — AZUL/AMARELO/VERDE/LARANJA
}

/** Notas + métricas + flags + feedback do redato_output do
 *  jogo_redacao. Forma do JSONB persistido em reescrita.redato_output.
 *  Pode ser null se Claude falhou no bot — UI mostra estado pendente. */
export interface JogoRedatoOutput {
  modo: "jogo_redacao";
  tema_minideck: string;
  notas_enem: {
    c1: number;
    c2: number;
    c3: number;
    c4: number;
    c5: number;
  };
  nota_total_enem: number;
  transformacao_cartas: number;     // 0-100, decisão G.1.6
  sugestoes_cartas_alternativas: Array<{
    codigo_original: string;
    codigo_sugerido: string;
    motivo: string;
  }>;
  flags: {
    copia_literal_das_cartas: boolean;
    cartas_mal_articuladas: boolean;
    fuga_do_tema_do_minideck: boolean;
    tipo_textual_inadequado: boolean;
    desrespeito_direitos_humanos: boolean;
  };
  feedback_aluno: {
    acertos: string[];
    ajustes: string[];
  };
  feedback_professor: {
    pontos_fortes: string[];
    pontos_fracos: string[];
    padrao_falha: string;
    transferencia_competencia: string;
  };
  _mission?: {
    mode: string;
    model?: string;
    [k: string]: unknown;
  };
}

/** GET /portal/partidas/{id}/reescritas/{aluno_turma_id} */
export interface ReescritaDetail {
  partida: {
    id: string;
    atividade_id: string;
    atividade_nome: string;        // ex.: "OF13 — Jogo de Redação"
    tema: string;                  // slug snake_case
    nome_humano_tema: string;      // ex.: "Saúde Mental"
    grupo_codigo: string;
    prazo_reescrita: string;       // ISO UTC
  };
  aluno: AlunoResumoPartida;
  cartas_escolhidas: CartaEscolhidaDetail[];
  texto_montado: string;
  reescrita: {
    id: string;
    enviado_em: string;            // ISO UTC; UI converte pra BRT
    texto: string;
    /** null se bot persistiu mas Claude falhou (timeout/erro). UI
     *  trata como "avaliação pendente". */
    redato_output: JogoRedatoOutput | null;
    elapsed_ms: number | null;
  };
}
