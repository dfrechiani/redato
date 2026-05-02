"""Testes do endpoint POST /portal/envios/{envio_id}/reprocessar.

Padrão dos tests do portal: schema validation + smoke estrutural via
inspect.getsource. E2E completo (com DB Postgres real) está em
`scripts/test_m6_gestao.py` separado.

Cobre:
1. Schema do response (`ReprocessarEnvioResponse`)
2. Estrutura crítica do endpoint preservada em refactors:
   - usa `_check_permission_atividade` (auth)
   - levanta 400 se interaction sem texto
   - resolve_mode pra rotear FT/Claude vs grade_mission
   - persiste em `interaction.redato_output` (não cria nova tentativa)
   - retorna ok=False sem 500 em pipeline failure
3. Helper `reprocessarEnvio` no portal-client (frontend) — confere que
   função existe + assinatura.
"""
from __future__ import annotations


# ──────────────────────────────────────────────────────────────────────
# 1. Schema validation
# ──────────────────────────────────────────────────────────────────────

def test_reprocessar_envio_response_aceita_sucesso():
    """Resposta de sucesso: ok=True, error=None, redato_output dict."""
    from redato_backend.portal.portal_api import ReprocessarEnvioResponse
    r = ReprocessarEnvioResponse(
        ok=True,
        redato_output={"c1_audit": {"nota": 160}, "nota_total": 800},
    )
    assert r.ok is True
    assert r.error is None
    assert r.redato_output is not None
    assert r.redato_output["nota_total"] == 800


def test_reprocessar_envio_response_aceita_falha_estruturada():
    """Resposta de falha: ok=False com error e redato_output={"error":...}.
    Status HTTP é 200 (corpo conta a falha) — caller diferencia via `ok`."""
    from redato_backend.portal.portal_api import ReprocessarEnvioResponse
    r = ReprocessarEnvioResponse(
        ok=False,
        error="OpenAIFTGradingError: timeout",
        redato_output={"error": "OpenAIFTGradingError: timeout"},
    )
    assert r.ok is False
    assert "timeout" in r.error
    assert r.redato_output is not None


def test_reprocessar_envio_response_aceita_minimo():
    """Apenas `ok` é obrigatório — resto opcional."""
    from redato_backend.portal.portal_api import ReprocessarEnvioResponse
    r = ReprocessarEnvioResponse(ok=True)
    assert r.ok is True
    assert r.error is None
    assert r.redato_output is None


# ──────────────────────────────────────────────────────────────────────
# 2. Estrutura do endpoint preservada (smoke contra refactors)
# ──────────────────────────────────────────────────────────────────────

def test_reprocessar_envio_chama_check_permission_atividade():
    """Refactor não pode remover a verificação de permissão.
    Endpoint usa `_check_permission_atividade(auth, envio.atividade_id)`
    pra rejeitar professor de outra turma com 403."""
    import inspect
    from redato_backend.portal.portal_api import reprocessar_envio

    src = inspect.getsource(reprocessar_envio)
    assert "_check_permission_atividade" in src, (
        "endpoint perdeu o check de permissão — qualquer professor "
        "logado pode reprocessar envios de outras turmas"
    )


def test_reprocessar_envio_valida_texto_transcrito():
    """Sem `texto_transcrito` na Interaction não há o que corrigir.
    Endpoint deve responder 400 com mensagem orientando o professor."""
    import inspect
    from redato_backend.portal.portal_api import reprocessar_envio

    src = inspect.getsource(reprocessar_envio)
    # Levanta 400 quando texto ausente
    assert "HTTP_400_BAD_REQUEST" in src
    # Mensagem menciona OCR/transcrição (orientação ao professor)
    assert "OCR" in src or "transcri" in src.lower()


def test_reprocessar_envio_usa_resolve_mode_pra_rotear():
    """Roteamento FT/Claude (OF14) vs grade_mission (Foco/Parcial)
    é decidido por `resolve_mode(activity_id)`. Endpoint reusa
    a infra do bot — não duplica lógica."""
    import inspect
    from redato_backend.portal.portal_api import reprocessar_envio

    src = inspect.getsource(reprocessar_envio)
    assert "resolve_mode" in src
    assert "_claude_grade_essay" in src
    assert "grade_mission" in src
    assert "COMPLETO_INTEGRAL" in src


def test_reprocessar_envio_pipeline_falha_retorna_ok_false():
    """Pipeline pode falhar (timeout, parser, etc.). Endpoint deve
    capturar e retornar ok=False — NÃO levantar 500. Corpo do erro
    é persistido em redato_output igual o bot faz."""
    import inspect
    from redato_backend.portal.portal_api import reprocessar_envio

    src = inspect.getsource(reprocessar_envio)
    # Tem try/except envolvendo o pipeline
    assert "except Exception" in src
    # Retorna ReprocessarEnvioResponse com ok=False (não raise)
    assert "ok=False" in src
    # Persiste erro estruturado pra debug + UI mostrar mensagem
    assert "json.dumps" in src
    # Loga stack trace via logger.exception (visibilidade Railway)
    assert "logger.exception" in src


def test_reprocessar_envio_persiste_em_interaction_nao_envio():
    """`redato_output` está em `interactions`, não em `envios`.
    Endpoint atualiza `interaction.redato_output` da MESMA tentativa
    (não cria nova `tentativa_n` — é correção da existente).
    Refactor que mover essa logic pode quebrar M9.6."""
    import inspect
    from redato_backend.portal.portal_api import reprocessar_envio

    src = inspect.getsource(reprocessar_envio)
    # Atualiza interaction.redato_output diretamente
    assert "interaction.redato_output" in src
    # NÃO chama criar_interaction_e_envio_postgres (que cria nova
    # tentativa) — só UPDATE
    assert "criar_interaction_e_envio_postgres" not in src


# ──────────────────────────────────────────────────────────────────────
# 3. Sanity do helper frontend (existe em portal-client.ts?)
# ──────────────────────────────────────────────────────────────────────

def test_portal_client_tem_helper_reprocessar():
    """Smoke: helper `reprocessarEnvio` existe em
    `redato_frontend/lib/portal-client.ts` com URL correta. Detecta
    refactor que esqueça de atualizar o caller."""
    from pathlib import Path
    repo = Path(__file__).resolve().parents[5]
    cli = repo / "redato_frontend" / "lib" / "portal-client.ts"
    assert cli.exists(), f"portal-client.ts não encontrado em {cli}"
    src = cli.read_text(encoding="utf-8")
    assert "reprocessarEnvio" in src, (
        "helper reprocessarEnvio sumiu de portal-client.ts"
    )
    assert "/portal/envios/" in src and "/reprocessar" in src, (
        "URL do endpoint mudou — frontend não vai bater com backend"
    )
    # Method POST (não GET)
    assert 'method: "POST"' in src
