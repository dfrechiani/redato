"""Testes da persistência + endpoint POST /portal/envios/{id}/diagnosticar.

Padrão: smoke estrutural via inspect.getsource + schema validation.
E2E completo (auth + DB Postgres + chamada real OpenAI) fica em
`scripts/test_m6_gestao.py` separado — aqui valida invariantes do
código (auth correto, não-bloqueante, schema da resposta).
"""
from __future__ import annotations


# ──────────────────────────────────────────────────────────────────────
# 1. persistir_diagnostico — não levanta em qualquer falha
# ──────────────────────────────────────────────────────────────────────

def test_persistir_diagnostico_nao_levanta_em_qualquer_caso():
    """Defesa em profundidade: persistir nunca propaga exceção pro
    caller. Retorna False em falha (caller já trata diagnostico como
    operação não-bloqueante)."""
    import inspect
    from redato_backend.diagnostico import persistencia
    src = inspect.getsource(persistencia.persistir_diagnostico_envio)
    # Try/except cobrindo o body inteiro
    assert "try:" in src
    assert "except Exception:" in src
    # Loga via exception (stack trace) em vez de silenciar
    assert "logger.exception" in src
    # Retorna bool — caller checa `if ok:` em vez de exceção
    assert "return True" in src and "return False" in src


def test_diagnosticar_e_persistir_respeita_flag_habilitado():
    """Se REDATO_DIAGNOSTICO_HABILITADO=false, não chama OpenAI nem
    persiste — retorna None curto-circuitando."""
    import inspect
    from redato_backend.diagnostico import persistencia
    src = inspect.getsource(persistencia.diagnosticar_e_persistir_envio)
    assert "diagnostico_habilitado()" in src
    assert "return None" in src


# ──────────────────────────────────────────────────────────────────────
# 2. Pipeline correção: diagnóstico não bloqueia
# ──────────────────────────────────────────────────────────────────────

def test_pipeline_correcao_falha_diagnostico_nao_bloqueia():
    """bot.py: chamada ao diagnóstico ENVOLVIDA por try/except — falha
    NÃO derruba a entrega da correção ao aluno."""
    import inspect
    from redato_backend.whatsapp import bot
    src = inspect.getsource(bot)
    # Bloco do diagnóstico precisa estar presente
    assert "diagnosticar_e_persistir_envio" in src
    # Em try/except defensivo, log via logger.exception
    assert "diagnostico cognitivo falhou" in src.lower() or \
           "diagnostico cognitivo falhou" in src
    # Roda APÓS criar_interaction_e_envio_postgres (precisa do envio_id)
    idx_postgres = src.find("criar_interaction_e_envio_postgres")
    idx_diag = src.find("diagnosticar_e_persistir_envio")
    assert idx_postgres >= 0 and idx_diag >= 0
    assert idx_diag > idx_postgres, (
        "Diagnóstico deve rodar APÓS criar_interaction_e_envio_postgres "
        "(precisa do envio_id pra UPDATE)"
    )


# ──────────────────────────────────────────────────────────────────────
# 3. Schema do response do endpoint
# ──────────────────────────────────────────────────────────────────────

def test_diagnosticar_envio_response_aceita_sucesso():
    from redato_backend.portal.portal_api import DiagnosticarEnvioResponse
    r = DiagnosticarEnvioResponse(
        ok=True,
        diagnostico={
            "schema_version": "1.0",
            "modelo_usado": "gpt-4.1-2025-04-14",
            "descritores": [],
            "lacunas_prioritarias": [],
            "resumo_qualitativo": "x" * 30,
            "recomendacao_breve": "y" * 20,
        },
    )
    assert r.ok is True
    assert r.error is None
    assert r.diagnostico is not None


def test_diagnosticar_envio_response_aceita_falha_estruturada():
    from redato_backend.portal.portal_api import DiagnosticarEnvioResponse
    r = DiagnosticarEnvioResponse(
        ok=False,
        error="inferência retornou None — ver logs",
    )
    assert r.ok is False
    assert "logs" in r.error
    assert r.diagnostico is None


# ──────────────────────────────────────────────────────────────────────
# 4. Endpoint: invariantes de auth e validações
# ──────────────────────────────────────────────────────────────────────

def test_endpoint_rediagnosticar_professor_da_turma_200():
    """Endpoint usa _check_permission_atividade — concede acesso ao
    professor responsável OU ao coordenador da escola (mesmo padrão
    do reprocessar_envio)."""
    import inspect
    from redato_backend.portal import portal_api
    src = inspect.getsource(portal_api.diagnosticar_envio)
    assert "_check_permission_atividade(auth, envio.atividade_id)" in src


def test_endpoint_rediagnosticar_outro_professor_403():
    """`_check_permission_atividade` levanta 403 quando o caller não
    é prof da turma nem coordenador da escola. Endpoint não pode
    by-passar essa checagem com role-only."""
    import inspect
    from redato_backend.portal import portal_api
    src = inspect.getsource(portal_api.diagnosticar_envio)
    # Não pode usar uma checagem mais frouxa
    assert "can_view_dashboard_escola(auth," not in src or \
           "_check_permission_atividade" in src
    # E não pode skipar auth
    assert "Depends(get_current_user)" in src


def test_endpoint_rediagnosticar_envio_inexistente_404():
    """Envio inexistente → 404 (antes mesmo do _check_permission)."""
    import inspect
    from redato_backend.portal import portal_api
    src = inspect.getsource(portal_api.diagnosticar_envio)
    # Padrão: session.get retorna None pra UUID que não existe
    assert "envio = session.get(Envio, envio_id)" in src
    assert "404" in src


def test_endpoint_rediagnosticar_sem_texto_400():
    """Envio sem texto OCR-ado → 400 (não dá pra rodar diagnóstico
    sem texto, igual o reprocessar_envio)."""
    import inspect
    from redato_backend.portal import portal_api
    src = inspect.getsource(portal_api.diagnosticar_envio)
    assert "texto_transcrito" in src
    assert "400" in src
