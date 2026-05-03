"""Testes do payload diagnostico_recente no endpoint perfil_aluno (Fase 3).

Padrão dos tests do portal: schema validation + smoke estrutural via
inspect.getsource. E2E completo (auth + DB Postgres + FT/GPT real)
fica em scripts/test_m6_gestao.py.

Cobre:
1. Schema dos novos models (DiagnosticoRecente, etc.)
2. _build_diagnostico_recente: estrutura crítica
3. AlunoPerfilResponse aceita diagnostico_recente=None
4. AlunoPerfilResponse aceita versão completa
5. Versão professor preserva 40 descritores
6. Versão aluno só tem metas (sem dados crus)
7. Bot integration: metas_msg flui pra _build_messages_pos_correcao
"""
from __future__ import annotations


# ──────────────────────────────────────────────────────────────────────
# 1. Schema validation
# ──────────────────────────────────────────────────────────────────────

def test_perfil_aluno_response_aceita_diagnostico_recente_none():
    """Aluno sem envio diagnosticado → diagnostico_recente=None."""
    from redato_backend.portal.portal_api import (
        AlunoPerfilResponse, AlunoPerfilResumo, AlunoPerfilStats,
    )
    r = AlunoPerfilResponse(
        aluno=AlunoPerfilResumo(
            id="x", nome="A", telefone_mascarado="+55***",
            entrou_em="2026-01-01T00:00:00+00:00", ativo=True,
        ),
        stats=AlunoPerfilStats(
            total_envios=0, envios_com_nota=0, envios_com_problema=0,
            media_geral=None,
            medias_cN={"c1": None, "c2": None, "c3": None, "c4": None, "c5": None},
            tendencia="dados_insuficientes",
            ponto_forte=None, ponto_fraco=None,
        ),
        envios=[],
        diagnostico_recente=None,
    )
    assert r.diagnostico_recente is None


def test_perfil_aluno_response_aceita_diagnostico_completo():
    """Versão professor + versão aluno, ambos populados.
    Schema atualizado no fix Fase 3 (descritores enriquecidos +
    lacunas_enriquecidas com 3 seções)."""
    from redato_backend.portal.portal_api import (
        AlunoPerfilResponse, AlunoPerfilResumo, AlunoPerfilStats,
        DiagnosticoRecente, DiagnosticoVersaoProfessor,
        DiagnosticoVersaoAluno, DiagnosticoMeta,
        DiagnosticoOficinaSugerida,
        DiagnosticoDescritorEnriquecido,
        DiagnosticoLacunaEnriquecida,
    )
    diag = DiagnosticoRecente(
        envio_id="env-uuid",
        criado_em="2026-05-03T15:05:00+00:00",
        modelo="gpt-4.1-2025-04-14",
        professor=DiagnosticoVersaoProfessor(
            descritores=[
                DiagnosticoDescritorEnriquecido(
                    id="C1.001", status="dominio",
                    evidencias=[], confianca="alta",
                    nome="Estrutura sintática",
                    competencia="C1",
                    categoria_inep="Estrutura sintática",
                ),
            ],
            lacunas_prioritarias=["C5.001"],
            lacunas_enriquecidas=[
                DiagnosticoLacunaEnriquecida(
                    id="C5.001",
                    nome="Agente",
                    competencia="C5",
                    status="lacuna",
                    confianca="alta",
                    evidencias=["Não há proposta com agente nomeado."],
                    definicao_curta="A proposta nomeia QUEM vai executar...",
                    sugestao_pedagogica="Mostre exemplos de propostas com...",
                ),
            ],
            resumo_qualitativo="Aluno X demonstra Y.",
            recomendacao_breve="Reforço Z.",
            oficinas_sugeridas=[
                DiagnosticoOficinaSugerida(
                    codigo="RJ2·OF12·MF", titulo="Leilão",
                    modo_correcao="foco_c5", oficina_numero=12,
                    razao="Trabalha proposta de intervenção (C5)",
                ),
            ],
        ),
        aluno=DiagnosticoVersaoAluno(
            metas=[
                DiagnosticoMeta(
                    id="M1", competencia="C5",
                    titulo="Construa propostas com agente nomeado",
                    descricao="Quem vai executar?",
                ),
            ],
        ),
    )
    r = AlunoPerfilResponse(
        aluno=AlunoPerfilResumo(
            id="x", nome="A", telefone_mascarado="+55***",
            entrou_em="2026-01-01T00:00:00+00:00", ativo=True,
        ),
        stats=AlunoPerfilStats(
            total_envios=1, envios_com_nota=1, envios_com_problema=0,
            media_geral=720,
            medias_cN={"c1": 160, "c2": 160, "c3": 160, "c4": 160, "c5": 80},
            tendencia="dados_insuficientes",
            ponto_forte="C1", ponto_fraco="C5",
        ),
        envios=[],
        diagnostico_recente=diag,
    )
    assert r.diagnostico_recente is not None
    assert r.diagnostico_recente.envio_id == "env-uuid"
    assert r.diagnostico_recente.modelo == "gpt-4.1-2025-04-14"
    # Versão professor preserva descritores enriquecidos + lacunas + oficinas
    assert len(r.diagnostico_recente.professor.lacunas_prioritarias) == 1
    assert len(r.diagnostico_recente.professor.lacunas_enriquecidas) == 1
    assert r.diagnostico_recente.professor.lacunas_enriquecidas[0].nome == "Agente"
    assert len(r.diagnostico_recente.professor.oficinas_sugeridas) == 1
    # Descritor enriquecido tem nome legível pra heatmap
    assert r.diagnostico_recente.professor.descritores[0].nome == "Estrutura sintática"
    # Versão aluno só metas
    assert len(r.diagnostico_recente.aluno.metas) == 1
    assert r.diagnostico_recente.aluno.metas[0].competencia == "C5"


def test_perfil_aluno_lacunas_enriquecidas():
    """Cada lacuna prioritária deve ter nome_curto + definicao_curta
    + sugestao_pedagogica preenchidos. Smoke estrutural."""
    from redato_backend.portal.portal_api import DiagnosticoLacunaEnriquecida
    lac = DiagnosticoLacunaEnriquecida(
        id="C5.001",
        nome="Agente",
        competencia="C5",
        status="lacuna",
        confianca="alta",
        evidencias=["trecho da redação"],
        definicao_curta="A proposta nomeia QUEM vai executar.",
        sugestao_pedagogica="Mostre exemplos de propostas com agentes.",
    )
    # 3 seções dos cards: o que é (definicao_curta) + evidência +
    # como trabalhar (sugestao_pedagogica)
    assert len(lac.definicao_curta) > 0
    assert len(lac.evidencias) > 0
    assert len(lac.sugestao_pedagogica) > 0


# ──────────────────────────────────────────────────────────────────────
# 2. Estrutura crítica do _build_diagnostico_recente
# ──────────────────────────────────────────────────────────────────────

def test_build_diagnostico_recente_filtra_envio_diagnosticado():
    """Helper deve filtrar envios COM diagnostico IS NOT NULL — não
    pega o último envio se ele estiver com diagnostico=NULL."""
    import inspect
    from redato_backend.portal import portal_api
    src = inspect.getsource(portal_api._build_diagnostico_recente)
    assert "Envio.diagnostico.isnot(None)" in src, (
        "Query deve filtrar por diagnostico IS NOT NULL"
    )
    # Ordem desc por enviado_em (último envio diagnosticado)
    assert "Envio.enviado_em.desc()" in src
    assert ".limit(1)" in src


def test_build_diagnostico_recente_filtra_turma():
    """JOIN com Atividade pra garantir envio é da turma do perfil
    (defesa em profundidade contra cross-turma)."""
    import inspect
    from redato_backend.portal import portal_api
    src = inspect.getsource(portal_api._build_diagnostico_recente)
    assert "Atividade.turma_id == turma.id" in src
    assert "Atividade.deleted_at.is_(None)" in src


def test_build_diagnostico_recente_chama_metas_e_sugestoes():
    """Helper monta versão aluno (metas) + versão professor (sugestões).
    Confirma chamadas aos módulos da Fase 3."""
    import inspect
    from redato_backend.portal import portal_api
    src = inspect.getsource(portal_api._build_diagnostico_recente)
    assert "gerar_metas_aluno" in src
    assert "sugerir_oficinas" in src


def test_build_diagnostico_recente_passa_serie_da_turma():
    """sugerir_oficinas precisa da série pra filtrar catálogo —
    helper deve passar `turma.serie`, não hardcoded."""
    import inspect
    from redato_backend.portal import portal_api
    src = inspect.getsource(portal_api._build_diagnostico_recente)
    assert "serie_aluno=turma.serie" in src


# ──────────────────────────────────────────────────────────────────────
# 3. Bot integration — metas fluem pro WhatsApp
# ──────────────────────────────────────────────────────────────────────

def test_bot_metas_msg_anexada_se_diagnostico_ok():
    """bot.py: quando diagnosticar_e_persistir_envio retorna dict,
    bot renderiza metas e passa metas_msg pro _build_messages_pos_correcao."""
    import inspect
    from redato_backend.whatsapp import bot
    src = inspect.getsource(bot._process_photo)
    # Captura return value do helper (não descarta)
    assert "diagnostico_dict = diagnosticar_e_persistir_envio" in src
    # Renderiza metas APENAS se diagnostico_dict não-None
    assert "if diagnostico_dict is not None:" in src
    assert "render_metas_whatsapp(metas)" in src
    # E passa pra _build_messages_pos_correcao via kwarg novo
    assert "metas_msg=metas_msg" in src


def test_build_messages_pos_correcao_anexa_metas_no_fim():
    """Metas devem vir como ÚLTIMA mensagem da sequência, depois do
    feedback INEP. Ordem importa pedagogicamente — feedback motiva
    as metas, não o contrário."""
    from redato_backend.whatsapp.bot import _build_messages_pos_correcao
    msgs = _build_messages_pos_correcao(
        resposta="📊 Feedback INEP aqui",
        skip_duplicate_check=False,
        postgres_falhou=False,
        tentativa_n=1,
        metas_msg="🎯 Suas metas aqui",
    )
    assert len(msgs) == 2
    assert msgs[0].text == "📊 Feedback INEP aqui"
    assert msgs[1].text == "🎯 Suas metas aqui"


def test_build_messages_pos_correcao_sem_metas_pre_fase3():
    """metas_msg=None preserva comportamento antigo (1 chunk só)."""
    from redato_backend.whatsapp.bot import _build_messages_pos_correcao
    msgs = _build_messages_pos_correcao(
        resposta="Feedback",
        skip_duplicate_check=False,
        postgres_falhou=False,
        tentativa_n=1,
        metas_msg=None,
    )
    assert len(msgs) == 1
    assert msgs[0].text == "Feedback"


def test_build_messages_pos_correcao_metas_apos_ack_tentativa():
    """Sequência completa: ack tentativa + feedback + metas (3 chunks)."""
    from redato_backend.whatsapp.bot import _build_messages_pos_correcao
    msgs = _build_messages_pos_correcao(
        resposta="Feedback",
        skip_duplicate_check=True,
        postgres_falhou=False,
        tentativa_n=2,
        metas_msg="🎯 Metas",
    )
    assert len(msgs) == 3
    assert "Tentativa 2" in msgs[0].text
    assert msgs[1].text == "Feedback"
    assert msgs[2].text == "🎯 Metas"
