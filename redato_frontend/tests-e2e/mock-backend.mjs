/**
 * Mock backend pra Playwright (M5 + M6). Imita os endpoints relevantes
 * com respostas canónicas. NÃO valida JWT real — qualquer Bearer não-vazio
 * é aceito.
 *
 * Tokens reservados pra cobrir branches de erro:
 * - "TOKEN_EXPIRADO" → 410
 * - "TOKEN_INVALIDO" → 404
 * - "TOKEN_OK"       → 200
 *
 * Credenciais:
 * - prof@demo.redato / senha123 → professor (escola A)
 * - coord@demo.redato / senha123 → coordenador (escola A)
 * - inativo@demo.redato → 403
 *
 * Estado in-memory pra suportar fluxos de M6 (criar atividade,
 * encerrar, inativar aluno). Reset entre testes não é automático —
 * cada teste é responsável por preparar o estado que precisa.
 */
import { createServer } from "node:http";

const PORT = Number(process.env.MOCK_PORT ?? 8091);

const PROF = {
  id: "11111111-1111-1111-1111-111111111111",
  nome: "Maria Professora",
  email: "prof@demo.redato",
  papel: "professor",
  escola_id: "99999999-9999-9999-9999-999999999999",
  escola_nome: "Colégio Estadual Rui Barbosa",
};

const COORD = {
  id: "22222222-2222-2222-2222-222222222222",
  nome: "Carla Coordenadora",
  email: "coord@demo.redato",
  papel: "coordenador",
  escola_id: "99999999-9999-9999-9999-999999999999",
  escola_nome: "Colégio Estadual Rui Barbosa",
};

const MISSOES = [
  { id: "m1", codigo: "RJ1·OF10·MF", serie: "1S", oficina_numero: 10, titulo: "Jogo Dissertativo", modo_correcao: "foco_c3" },
  { id: "m2", codigo: "RJ1·OF11·MF", serie: "1S", oficina_numero: 11, titulo: "Conectivos Argumentativos", modo_correcao: "foco_c4" },
  { id: "m3", codigo: "RJ1·OF12·MF", serie: "1S", oficina_numero: 12, titulo: "Leilão de Soluções", modo_correcao: "foco_c5" },
  { id: "m4", codigo: "RJ1·OF13·MF", serie: "1S", oficina_numero: 13, titulo: "Construindo Argumentos", modo_correcao: "completo_parcial" },
  { id: "m5", codigo: "RJ1·OF14·MF", serie: "1S", oficina_numero: 14, titulo: "Jogo de Redação", modo_correcao: "completo" },
];

const TURMA_PROF = {
  id: "t-prof-1",
  codigo: "1A",
  serie: "1S",
  codigo_join: "TURMA-DEMO-1A-2026",
  ano_letivo: 2026,
  ativa: true,
  professor_id: PROF.id,
  professor_nome: PROF.nome,
  escola_id: PROF.escola_id,
  escola_nome: PROF.escola_nome,
};

const TURMA_OUTRA = {
  id: "t-outra",
  codigo: "1B",
  serie: "1S",
  codigo_join: "TURMA-DEMO-1B-2026",
  ano_letivo: 2026,
  ativa: true,
  professor_id: "33333333-3333-3333-3333-333333333333",
  professor_nome: "Outro Professor",
  escola_id: PROF.escola_id,
  escola_nome: PROF.escola_nome,
};

const ALUNOS = [
  {
    id: "a1", nome: "Ana Aluna",
    telefone_mascarado: "+5511999998***",
    vinculado_em: new Date().toISOString(),
    ativo: true, n_envios: 1,
  },
  {
    id: "a2", nome: "Bruno Aluno",
    telefone_mascarado: "+5511988887***",
    vinculado_em: new Date().toISOString(),
    ativo: true, n_envios: 0,
  },
];

// Estado mutável pra testes M6
const state = {
  atividades: new Map(), // id → atividade obj
  alunosInativos: new Set(), // ids
  /** atividades existentes pra detectar duplicata: turma_id+missao_id */
  duplicateMap: new Map(),
};

function _fakeAtividade({ id, turma_id, missao_id, data_inicio, data_fim }) {
  const m = MISSOES.find((m) => m.id === missao_id) ?? MISSOES[0];
  const inicio = new Date(data_inicio);
  const fim = new Date(data_fim);
  const agora = new Date();
  const status =
    agora < inicio ? "agendada"
    : agora > fim ? "encerrada" : "ativa";
  return {
    id,
    turma_id,
    missao_id,
    missao_codigo: m.codigo,
    missao_titulo: m.titulo,
    oficina_numero: m.oficina_numero,
    data_inicio: inicio.toISOString(),
    data_fim: fim.toISOString(),
    status,
    n_envios: 1,
    notificacao_enviada_em: null,
    modo_correcao: m.modo_correcao,
  };
}

const ATIVIDADE_BASE = _fakeAtividade({
  id: "atv-1",
  turma_id: TURMA_PROF.id,
  missao_id: "m1",
  data_inicio: new Date(Date.now() - 3600 * 1000).toISOString(),
  data_fim: new Date(Date.now() + 7 * 24 * 3600 * 1000).toISOString(),
});
state.atividades.set(ATIVIDADE_BASE.id, ATIVIDADE_BASE);
state.duplicateMap.set(`${TURMA_PROF.id}|m1`, ATIVIDADE_BASE.id);

function readJson(req) {
  return new Promise((resolve) => {
    let data = "";
    req.on("data", (c) => (data += c));
    req.on("end", () => {
      try {
        resolve(data ? JSON.parse(data) : {});
      } catch {
        resolve({});
      }
    });
  });
}

function send(res, status, body, extraHeaders = {}) {
  res.writeHead(status, {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    ...extraHeaders,
  });
  res.end(JSON.stringify(body));
}

function userByBearer(req) {
  const auth = req.headers.authorization;
  if (!auth || !auth.startsWith("Bearer ")) return null;
  const token = auth.slice("Bearer ".length);
  if (token.startsWith("coord-")) return COORD;
  return PROF; // default
}

function turmasParaUser(user) {
  // Prof vê só a sua. Coord vê as duas da escola.
  if (user.papel === "professor") return [TURMA_PROF];
  return [TURMA_PROF, TURMA_OUTRA];
}

function turmaListItem(t) {
  return {
    id: t.id, codigo: t.codigo, serie: t.serie,
    codigo_join: t.codigo_join,
    ano_letivo: t.ano_letivo, ativa: t.ativa,
    n_alunos: ALUNOS.filter((a) => !state.alunosInativos.has(a.id)).length,
    n_atividades_ativas: Array.from(state.atividades.values())
      .filter((a) => a.turma_id === t.id && a.status === "ativa").length,
    n_atividades_encerradas: Array.from(state.atividades.values())
      .filter((a) => a.turma_id === t.id && a.status === "encerrada").length,
    professor_id: t.professor_id,
    professor_nome: t.professor_nome,
  };
}

function atividadeDetailFor(atv, user) {
  const aluno_envios = ALUNOS
    .filter((a) => !state.alunosInativos.has(a.id))
    .map((a) => {
      const envio = a.id === "a1";
      return {
        aluno_turma_id: a.id,
        aluno_nome: a.nome,
        envio_id: envio ? "e1" : null,
        enviado_em: envio ? new Date().toISOString() : null,
        nota_total: envio ? 720 : null,
        faixa: envio ? "601-800" : "sem_nota",
        tem_feedback: envio,
      };
    });
  const missao = MISSOES.find((m) => m.id === atv.missao_id) ?? MISSOES[0];
  return {
    id: atv.id,
    turma_id: atv.turma_id,
    turma_codigo: TURMA_PROF.codigo,
    turma_serie: TURMA_PROF.serie,
    escola_nome: TURMA_PROF.escola_nome,
    professor_nome: TURMA_PROF.professor_nome,
    missao_id: atv.missao_id,
    missao_codigo: atv.missao_codigo,
    missao_titulo: atv.missao_titulo,
    oficina_numero: missao.oficina_numero,
    modo_correcao: atv.modo_correcao,
    data_inicio: atv.data_inicio,
    data_fim: atv.data_fim,
    status: atv.status,
    notificacao_enviada_em: atv.notificacao_enviada_em,
    pode_editar: user.papel === "professor",
    n_alunos_total: aluno_envios.length,
    n_enviados: aluno_envios.filter((e) => e.enviado_em).length,
    n_pendentes: aluno_envios.filter((e) => !e.enviado_em).length,
    distribuicao: { "0-200": 0, "201-400": 0, "401-600": 0, "601-800": 1, "801-1000": 0, sem_nota: 0 },
    top_detectores: [{ detector: "flag_repeticao_lexical", ocorrencias: 1 }],
    envios: aluno_envios,
  };
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const path = url.pathname;
  const method = req.method;

  if (method === "OPTIONS") {
    res.writeHead(204, {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, PATCH, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
    });
    return res.end();
  }

  // ── AUTH ────────────────────────────────────────────────────────────
  if (method === "POST" && path === "/auth/login") {
    const body = await readJson(req);
    if (body.email === "inativo@demo.redato") {
      return send(res, 403, { detail: "Usuário inativo" });
    }
    if (body.email === "prof@demo.redato" && body.senha === "senha123") {
      return send(res, 200, {
        access_token: "prof-jwt-" + Date.now(),
        token_type: "bearer",
        expires_in: body.lembrar_de_mim ? 30 * 24 * 3600 : 8 * 3600,
        papel: "professor", nome: PROF.nome, escola_id: PROF.escola_id,
      });
    }
    if (body.email === "coord@demo.redato" && body.senha === "senha123") {
      return send(res, 200, {
        access_token: "coord-jwt-" + Date.now(),
        token_type: "bearer",
        expires_in: 8 * 3600,
        papel: "coordenador", nome: COORD.nome, escola_id: COORD.escola_id,
      });
    }
    return send(res, 401, { detail: "Email ou senha inválidos" });
  }

  if (method === "GET" && path === "/auth/me") {
    const user = userByBearer(req);
    if (!user) return send(res, 401, { detail: "Não autenticado" });
    return send(res, 200, user);
  }

  if (method === "POST" && path === "/auth/logout") {
    return send(res, 200, { sucesso: true });
  }

  if (method === "POST" && path === "/auth/perfil/mudar-senha") {
    const body = await readJson(req);
    if (!userByBearer(req)) return send(res, 401, { detail: "Não autenticado" });
    if (body.senha_atual !== "senha123") {
      return send(res, 401, { detail: "Senha atual incorreta" });
    }
    if (!body.senha_nova || body.senha_nova.length < 8) {
      return send(res, 400, { detail: "Senha fraca: precisa 8+" });
    }
    return send(res, 200, { sucesso: true });
  }

  if (method === "POST" && path === "/auth/perfil/sair-todas-sessoes") {
    if (!userByBearer(req)) return send(res, 401, { detail: "Não autenticado" });
    return send(res, 200, { sucesso: true });
  }

  if (method === "POST" && path === "/auth/primeiro-acesso/validar") {
    const body = await readJson(req);
    if (body.token === "TOKEN_EXPIRADO") return send(res, 410, { detail: "Token expirado" });
    if (body.token === "TOKEN_INVALIDO") return send(res, 404, { detail: "Token não encontrado" });
    return send(res, 200, {
      valido: true, email: PROF.email, nome: PROF.nome,
      papel: PROF.papel, escola_nome: PROF.escola_nome,
    });
  }

  if (method === "POST" && path === "/auth/primeiro-acesso/definir-senha") {
    const body = await readJson(req);
    if (body.token === "TOKEN_EXPIRADO") return send(res, 410, { detail: "Token expirado" });
    return send(res, 200, { sucesso: true, redirect_to: "/auth/login" });
  }

  if (method === "POST" && path === "/auth/reset-password/solicitar") {
    return send(res, 200, { sucesso: true });
  }

  if (method === "POST" && path === "/auth/reset-password/confirmar") {
    const body = await readJson(req);
    if (body.token === "TOKEN_EXPIRADO") return send(res, 410, { detail: "Token expirado" });
    return send(res, 200, { sucesso: true });
  }

  // ── PORTAL M6 ───────────────────────────────────────────────────────
  const user = userByBearer(req);
  if (path.startsWith("/portal")) {
    if (!user) return send(res, 401, { detail: "Não autenticado" });
  }

  if (method === "GET" && path === "/portal/missoes") {
    return send(res, 200, MISSOES);
  }

  if (method === "GET" && path === "/portal/turmas") {
    return send(res, 200, turmasParaUser(user).map(turmaListItem));
  }

  // /portal/turmas/{id}
  let m = path.match(/^\/portal\/turmas\/([^/]+)$/);
  if (m && method === "GET") {
    // Turma "vazia" pra testes de estado vazio (M7)
    if (m[1] === "t-vazia") {
      return send(res, 200, {
        id: "t-vazia", codigo: "1Z", serie: "1S",
        codigo_join: "TURMA-DEMO-1Z-2026", ano_letivo: 2026, ativa: true,
        professor_id: PROF.id, professor_nome: PROF.nome,
        escola_id: PROF.escola_id, escola_nome: PROF.escola_nome,
        pode_criar_atividade: user.papel === "professor",
        alunos: [], atividades: [],
      });
    }
    const t = [TURMA_PROF, TURMA_OUTRA].find((x) => x.id === m[1]);
    if (!t) return send(res, 404, { detail: "Turma não encontrada" });
    if (user.papel === "professor" && t.professor_id !== user.id) {
      return send(res, 403, { detail: "Sem permissão" });
    }
    const ats = Array.from(state.atividades.values())
      .filter((a) => a.turma_id === t.id);
    return send(res, 200, {
      ...t,
      pode_criar_atividade: user.papel === "professor" && t.professor_id === user.id,
      alunos: ALUNOS.map((a) => ({
        ...a,
        ativo: !state.alunosInativos.has(a.id),
      })).filter((a) => a.ativo),
      atividades: ats,
    });
  }

  // PATCH /portal/turmas/{turma_id}/alunos/{aluno_id}
  m = path.match(/^\/portal\/turmas\/([^/]+)\/alunos\/([^/]+)$/);
  if (m && method === "PATCH") {
    if (user.papel !== "professor") return send(res, 403, { detail: "Sem permissão" });
    const body = await readJson(req);
    if (body.ativo === false) state.alunosInativos.add(m[2]);
    else state.alunosInativos.delete(m[2]);
    return send(res, 200, { sucesso: true, ativo: body.ativo });
  }

  if (method === "POST" && path === "/portal/atividades") {
    const body = await readJson(req);
    if (user.papel !== "professor") return send(res, 403, { detail: "Apenas professor" });
    if (!body.confirmar_duplicata && state.duplicateMap.has(`${body.turma_id}|${body.missao_id}`)) {
      return send(res, 200, {
        id: null,
        duplicate_warning: true,
        duplicata_atividade_id: state.duplicateMap.get(`${body.turma_id}|${body.missao_id}`),
        notificacao_disparada: false, notificacao_enviadas: 0,
      });
    }
    const novo = _fakeAtividade({
      id: "atv-" + Date.now(),
      turma_id: body.turma_id, missao_id: body.missao_id,
      data_inicio: body.data_inicio, data_fim: body.data_fim,
    });
    state.atividades.set(novo.id, novo);
    state.duplicateMap.set(`${body.turma_id}|${body.missao_id}`, novo.id);
    return send(res, 200, {
      id: novo.id, duplicate_warning: false,
      duplicata_atividade_id: null,
      notificacao_disparada: !!body.notificar_alunos,
      notificacao_enviadas: body.notificar_alunos ? 2 : 0,
    });
  }

  // /portal/atividades/{id}
  m = path.match(/^\/portal\/atividades\/([^/]+)$/);
  if (m && method === "GET") {
    const atv = state.atividades.get(m[1]);
    if (!atv) return send(res, 404, { detail: "Atividade não encontrada" });
    return send(res, 200, atividadeDetailFor(atv, user));
  }
  if (m && method === "PATCH") {
    if (user.papel !== "professor") return send(res, 403, { detail: "Sem permissão" });
    const atv = state.atividades.get(m[1]);
    if (!atv) return send(res, 404, { detail: "Atividade não encontrada" });
    const body = await readJson(req);
    if (body.data_inicio) atv.data_inicio = body.data_inicio;
    if (body.data_fim) atv.data_fim = body.data_fim;
    const ini = new Date(atv.data_inicio);
    const fim = new Date(atv.data_fim);
    const agora = new Date();
    atv.status = agora < ini ? "agendada" : agora > fim ? "encerrada" : "ativa";
    return send(res, 200, atv);
  }

  // /portal/atividades/{id}/encerrar
  m = path.match(/^\/portal\/atividades\/([^/]+)\/encerrar$/);
  if (m && method === "POST") {
    if (user.papel !== "professor") return send(res, 403, { detail: "Sem permissão" });
    const atv = state.atividades.get(m[1]);
    if (!atv) return send(res, 404, { detail: "Atividade não encontrada" });
    atv.data_fim = new Date().toISOString();
    atv.status = "encerrada";
    return send(res, 200, atv);
  }

  // ── M7: dashboards ──────────────────────────────────────────────
  m = path.match(/^\/portal\/turmas\/([^/]+)\/dashboard$/);
  if (m && method === "GET") {
    const turma_id = m[1];
    if (turma_id === "t-vazia") {
      return send(res, 200, {
        turma: { id: turma_id, codigo: "1Z", n_alunos_ativos: 0 },
        atividades_total: 0, atividades_ativas: 0, atividades_encerradas: 0,
        distribuicao_notas: {
          foco: { "0-40":0,"41-80":0,"81-120":0,"121-160":0,"161-200":0 },
          completo: { "0-200":0,"201-400":0,"401-600":0,"601-800":0,"801-1000":0 },
        },
        top_detectores: [],
        outros_detectores: 0,
        alunos_em_risco: [],
        evolucao_turma: [],
        n_envios_total: 0,
      });
    }
    return send(res, 200, {
      turma: { id: turma_id, codigo: "1A", n_alunos_ativos: 3 },
      atividades_total: 4,
      atividades_ativas: 2,
      atividades_encerradas: 2,
      distribuicao_notas: {
        foco: { "0-40":0,"41-80":1,"81-120":0,"121-160":1,"161-200":1 },
        completo: { "0-200":0,"201-400":1,"401-600":0,"601-800":2,"801-1000":1 },
      },
      top_detectores: [
        { codigo: "proposta_vaga", nome: "Proposta de intervenção vaga", contagem: 4 },
        { codigo: "repeticao_lexical", nome: "Repetição lexical", contagem: 3 },
        { codigo: "andaime_copiado", nome: "Andaime copiado do enunciado", contagem: 1 },
      ],
      outros_detectores: 2,
      alunos_em_risco: [
        { aluno_id: "a1", nome: "Ana Aluna", n_missoes_baixa: 3, ultima_nota: 320 },
      ],
      evolucao_turma: [
        { atividade_id: "a1", missao_codigo: "RJ1·OF10·MF",
          missao_titulo: "Jogo Dissertativo", oficina_numero: 10, modo: "foco_c3",
          data: "2026-04-01T10:00:00Z", nota_media: 110, n_envios: 3 },
        { atividade_id: "a2", missao_codigo: "RJ1·OF11·MF",
          missao_titulo: "Conectivos Argumentativos", oficina_numero: 11, modo: "foco_c4",
          data: "2026-04-08T10:00:00Z", nota_media: 130, n_envios: 3 },
        { atividade_id: "a3", missao_codigo: "RJ1·OF14·MF",
          missao_titulo: "Jogo de Redação", oficina_numero: 14, modo: "completo",
          data: "2026-04-15T10:00:00Z", nota_media: 640, n_envios: 4 },
      ],
      n_envios_total: 10,
    });
  }

  m = path.match(/^\/portal\/escolas\/([^/]+)\/dashboard$/);
  if (m && method === "GET") {
    if (user.papel !== "coordenador") {
      return send(res, 403, { detail: "Apenas coordenador" });
    }
    return send(res, 200, {
      escola: { id: m[1], nome: "Colégio Estadual Rui Barbosa",
                n_turmas: 2, n_alunos_ativos: 60 },
      turmas_resumo: [
        { turma_id: "t-prof-1", codigo: "1A", serie: "1S",
          professor_nome: "Maria Professora", media_geral: 612,
          n_atividades: 4, n_em_risco: 1 },
        { turma_id: "t-outra", codigo: "1B", serie: "1S",
          professor_nome: "Outro Professor", media_geral: 580,
          n_atividades: 3, n_em_risco: 2 },
      ],
      distribuicao_notas_escola: {
        foco: { "0-40":0,"41-80":2,"81-120":1,"121-160":3,"161-200":2 },
        completo: { "0-200":0,"201-400":2,"401-600":4,"601-800":5,"801-1000":2 },
      },
      top_detectores_escola: [
        { codigo: "proposta_vaga", nome: "Proposta de intervenção vaga", contagem: 8 },
        { codigo: "repeticao_lexical", nome: "Repetição lexical", contagem: 5 },
      ],
      outros_detectores_escola: 3,
      alunos_em_risco_escola: [
        { aluno_id: "a1", nome: "Ana Aluna", n_missoes_baixa: 3, ultima_nota: 320 },
        { aluno_id: "a3", nome: "Carlos Aluno", n_missoes_baixa: 2, ultima_nota: 380 },
      ],
      evolucao_escola: [
        { atividade_id: "x1", missao_codigo: "RJ1·OF10·MF",
          missao_titulo: "Jogo Dissertativo", oficina_numero: 10, modo: "foco_c3",
          data: "2026-04-01T10:00:00Z", nota_media: 105, n_envios: 6 },
        { atividade_id: "x2", missao_codigo: "RJ1·OF11·MF",
          missao_titulo: "Conectivos Argumentativos", oficina_numero: 11, modo: "foco_c4",
          data: "2026-04-08T10:00:00Z", nota_media: 125, n_envios: 6 },
        { atividade_id: "x3", missao_codigo: "RJ1·OF14·MF",
          missao_titulo: "Jogo de Redação", oficina_numero: 14, modo: "completo",
          data: "2026-04-15T10:00:00Z", nota_media: 615, n_envios: 8 },
      ],
      comparacao_turmas: [
        { turma_codigo: "1A", turma_id: "t-prof-1", media: 612, n_envios: 10 },
        { turma_codigo: "1B", turma_id: "t-outra", media: 580, n_envios: 7 },
      ],
    });
  }

  m = path.match(/^\/portal\/turmas\/([^/]+)\/alunos\/([^/]+)\/evolucao$/);
  if (m && method === "GET") {
    const turma_id = m[1];
    const aluno_id = m[2];
    const semEnvios = aluno_id === "a-pendente";
    return send(res, 200, {
      aluno: { id: aluno_id, nome: aluno_id === "a-pendente" ? "Cíntia Aluna" : "Ana Aluna" },
      envios: semEnvios ? [] : [
        { atividade_id: "atv-1", missao_codigo: "RJ1·OF10·MF",
          missao_titulo: "Jogo Dissertativo", oficina_numero: 10, modo: "foco_c3",
          data: "2026-04-01T10:00:00Z", nota: 60, faixa: "Insuficiente",
          detectores: ["Proposta de intervenção vaga", "Repetição lexical"] },
        { atividade_id: "atv-2", missao_codigo: "RJ1·OF14·MF",
          missao_titulo: "Jogo de Redação", oficina_numero: 14, modo: "completo",
          data: "2026-04-15T10:00:00Z", nota: 320, faixa: "Insuficiente",
          detectores: ["Proposta de intervenção vaga"] },
      ],
      evolucao_chart: semEnvios ? [] : [
        { data: "2026-04-01T10:00:00Z", nota: 60, missao_codigo: "RJ1·OF10·MF" },
        { data: "2026-04-15T10:00:00Z", nota: 320, missao_codigo: "RJ1·OF14·MF" },
      ],
      n_missoes_realizadas: semEnvios ? 0 : 2,
      missoes_pendentes: semEnvios
        ? [
            { atividade_id: "atv-3", missao_codigo: "RJ1·OF11·MF",
              missao_titulo: "Conectivos Argumentativos",
              oficina_numero: 11, modo_correcao: "foco_c4",
              data_fim: "2026-05-01T23:59:00Z", status: "ativa" },
            { atividade_id: "atv-4", missao_codigo: "RJ1·OF12·MF",
              missao_titulo: "Leilão de Soluções",
              oficina_numero: 12, modo_correcao: "foco_c5",
              data_fim: "2026-05-08T23:59:00Z", status: "ativa" },
          ]
        : [
            { atividade_id: "atv-3", missao_codigo: "RJ1·OF11·MF",
              missao_titulo: "Conectivos Argumentativos",
              oficina_numero: 11, modo_correcao: "foco_c4",
              data_fim: "2026-05-01T23:59:00Z", status: "ativa" },
          ],
    });
  }

  // /portal/atividades/{id}/envios/{aluno_id}
  m = path.match(/^\/portal\/atividades\/([^/]+)\/envios\/([^/]+)$/);
  if (m && method === "GET") {
    const atv = state.atividades.get(m[1]);
    if (!atv) return send(res, 404, { detail: "Atividade não encontrada" });
    const aluno = ALUNOS.find((a) => a.id === m[2]);
    if (!aluno) return send(res, 404, { detail: "Aluno não encontrado" });
    const temEnvio = aluno.id === "a1";
    return send(res, 200, {
      atividade_id: atv.id,
      missao_codigo: atv.missao_codigo,
      missao_titulo: atv.missao_titulo,
      oficina_numero: atv.oficina_numero ?? 0,
      modo_correcao: atv.modo_correcao ?? "",
      aluno_id: aluno.id, aluno_nome: aluno.nome,
      enviado_em: temEnvio ? new Date().toISOString() : null,
      foto_path: temEnvio ? "https://placehold.co/600x800.jpg" : null,
      foto_hash: temEnvio ? "abc123" : null,
      texto_transcrito: temEnvio
        ? "Texto transcrito da redação..."
        : null,
      nota_total: temEnvio ? 720 : null,
      faixas: temEnvio ? [
        { competencia: "C1", nota: 160, faixa: "Excelente" },
        { competencia: "C2", nota: 160, faixa: "Excelente" },
        { competencia: "C3", nota: 120, faixa: "Bom" },
        { competencia: "C4", nota: 160, faixa: "Excelente" },
        { competencia: "C5", nota: 120, faixa: "Bom" },
      ] : [],
      audit_pedagogico: temEnvio
        ? "Texto coeso, boa argumentação. Atenção à C3."
        : null,
      detectores: temEnvio
        ? [{ detector: "flag_repeticao_lexical", detalhe: "palavra 'então' 5x" }]
        : [],
      ocr_quality_issues: [],
      raw_output: null,
    });
  }

  // ── M8: PDF + email + triggers + health full ───────────────────────
  if (method === "POST" && path.startsWith("/portal/pdfs/dashboard-turma/")) {
    if (!user) return send(res, 401, { detail: "Não autenticado" });
    const turma_id = path.split("/").pop();
    const pdf_id = `pdf-turma-${turma_id}-${Date.now()}`;
    state.pdfs = state.pdfs || new Map();
    state.pdfs.set(pdf_id, {
      id: pdf_id, tipo: "dashboard_turma", escopo_id: turma_id,
      gerado_por_user_id: user.id, gerado_em: new Date().toISOString(),
      tamanho_bytes: 4321,
    });
    return send(res, 200, {
      pdf_id, download_url: `/portal/pdfs/${pdf_id}/download`,
      tamanho_bytes: 4321,
    });
  }
  if (method === "POST" && path.startsWith("/portal/pdfs/dashboard-escola/")) {
    if (!user) return send(res, 401, { detail: "Não autenticado" });
    if (user.papel !== "coordenador") {
      return send(res, 403, { detail: "Apenas coordenador" });
    }
    const escola_id = path.split("/").pop();
    const pdf_id = `pdf-escola-${escola_id}-${Date.now()}`;
    state.pdfs = state.pdfs || new Map();
    state.pdfs.set(pdf_id, {
      id: pdf_id, tipo: "dashboard_escola", escopo_id: escola_id,
      gerado_por_user_id: user.id, gerado_em: new Date().toISOString(),
      tamanho_bytes: 5432,
    });
    return send(res, 200, {
      pdf_id, download_url: `/portal/pdfs/${pdf_id}/download`,
      tamanho_bytes: 5432,
    });
  }
  m = path.match(/^\/portal\/pdfs\/evolucao-aluno\/([^/]+)\/([^/]+)$/);
  if (m && method === "POST") {
    if (!user) return send(res, 401, { detail: "Não autenticado" });
    const pdf_id = `pdf-aluno-${m[2]}-${Date.now()}`;
    state.pdfs = state.pdfs || new Map();
    state.pdfs.set(pdf_id, {
      id: pdf_id, tipo: "evolucao_aluno", escopo_id: m[2],
      gerado_por_user_id: user.id, gerado_em: new Date().toISOString(),
      tamanho_bytes: 3210,
    });
    return send(res, 200, {
      pdf_id, download_url: `/portal/pdfs/${pdf_id}/download`,
      tamanho_bytes: 3210,
    });
  }
  m = path.match(/^\/portal\/pdfs\/([^/]+)\/download$/);
  if (m && method === "GET") {
    if (!user) return send(res, 401, { detail: "Não autenticado" });
    const pdf_id = m[1];
    const FAKE_PDF = Buffer.concat([
      Buffer.from("%PDF-1.4\n"),
      Buffer.from("1 0 obj\n<<>>\nendobj\n%%EOF\n"),
    ]);
    res.writeHead(200, {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="redato_${pdf_id}.pdf"`,
      "Access-Control-Allow-Origin": "*",
    });
    return res.end(FAKE_PDF);
  }
  if (method === "GET" && path === "/portal/pdfs/historico") {
    if (!user) return send(res, 401, { detail: "Não autenticado" });
    state.pdfs = state.pdfs || new Map();
    const tipo = url.searchParams.get("tipo");
    const escopo_id = url.searchParams.get("escopo_id");
    let lista = Array.from(state.pdfs.values());
    if (tipo) lista = lista.filter((p) => p.tipo === tipo);
    if (escopo_id) lista = lista.filter((p) => p.escopo_id === escopo_id);
    lista.sort((a, b) =>
      a.gerado_em > b.gerado_em ? -1 : 1,
    );
    return send(res, 200, lista.map((p) => ({
      ...p,
      download_url: `/portal/pdfs/${p.id}/download`,
    })));
  }

  if (method === "GET" && path === "/admin/health/full") {
    return send(res, 200, {
      status: "ok",
      checks: {
        db_ping: true,
        admin_token: true,
        sendgrid_configured: false,
        twilio_configured: false,
        database_url_set: true,
        jwt_secret_set: true,
        storage_pdfs_writable: true,
        storage_pdfs_path: "/tmp/mock-pdfs",
      },
    });
  }

  send(res, 404, { detail: `Mock: rota não implementada — ${method} ${path}` });
});

server.listen(PORT, () => {
  console.log(`[mock-backend] M5+M6 listening on :${PORT}`);
});
