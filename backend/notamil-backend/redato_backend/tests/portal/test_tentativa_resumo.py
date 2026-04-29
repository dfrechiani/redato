"""Testes do schema `TentativaResumo` (M9.6).

Schema usado em `EnvioFeedbackResponse.tentativas_anteriores`. Cobre:
- Validação de campos obrigatórios
- texto_curto opcional (None quando OCR falhou)
- envio_id como UUID-string

Endpoint `detalhe_envio` em si tem cobertura de smoke em
`backend/notamil-backend/scripts/test_m6_gestao.py` (requer Postgres).
Este arquivo testa só o schema isolado, sem DB.
"""
from __future__ import annotations


def test_tentativa_resumo_schema_aceita_campos_minimos():
    from redato_backend.portal.portal_api import TentativaResumo
    t = TentativaResumo(
        envio_id="aaaa-bbbb-cccc-dddd-eeeeffff",
        tentativa_n=2,
        enviado_em="2026-04-29T16:45:00+00:00",
        nota_total=720,
        texto_curto="Era uma vez um tema...",
    )
    assert t.tentativa_n == 2
    assert t.nota_total == 720


def test_tentativa_resumo_aceita_nota_e_texto_none():
    """Casos reais: tentativa que falhou no OCR (sem texto), ou que
    foi enviada mas Claude ainda não retornou nota (queue cheia)."""
    from redato_backend.portal.portal_api import TentativaResumo
    t = TentativaResumo(
        envio_id="aaaa", tentativa_n=1,
        enviado_em="2026-04-29T16:45:00+00:00",
        nota_total=None, texto_curto=None,
    )
    assert t.nota_total is None
    assert t.texto_curto is None


def test_envio_feedback_response_default_inclui_campos_m96():
    """Backward-compat: response sem tentativas explícitas usa defaults
    (1 de 1, lista vazia). Garante que clientes velhos que não pediram
    `?envio_id=` continuam recebendo dados sensatos."""
    from redato_backend.portal.portal_api import EnvioFeedbackResponse
    r = EnvioFeedbackResponse(
        atividade_id="aaa", missao_codigo="X", missao_titulo="Y",
        oficina_numero=1, modo_correcao="completo",
        aluno_id="aaa", aluno_nome="Fulano",
        enviado_em=None, foto_url=None, foto_status="no_envio",
        foto_hash=None, texto_transcrito=None, nota_total=None,
        faixas=[], analise_da_redacao={}, detectores=[],
        ocr_quality_issues=[], raw_output=None,
    )
    # Defaults M9.6
    assert r.envio_id is None
    assert r.tentativa_n == 1
    assert r.tentativa_total == 1
    assert r.tentativas_anteriores == []


def test_envio_feedback_response_aceita_lista_de_tentativas_anteriores():
    """Caso real do M9.6: aluno enviou 3 vezes. Tela renderiza atual
    + 2 anteriores. Schema serializa corretamente."""
    from redato_backend.portal.portal_api import (
        EnvioFeedbackResponse, TentativaResumo,
    )
    anteriores = [
        TentativaResumo(
            envio_id="t2", tentativa_n=2,
            enviado_em="2026-04-28T13:00:00+00:00",
            nota_total=680, texto_curto="Tentativa 2…",
        ),
        TentativaResumo(
            envio_id="t1", tentativa_n=1,
            enviado_em="2026-04-27T13:00:00+00:00",
            nota_total=600, texto_curto="Primeira versão…",
        ),
    ]
    r = EnvioFeedbackResponse(
        atividade_id="aaa", missao_codigo="X", missao_titulo="Y",
        oficina_numero=1, modo_correcao="completo",
        aluno_id="aaa", aluno_nome="Fulano",
        enviado_em="2026-04-29T13:00:00+00:00",
        foto_url=None, foto_status="ok", foto_hash=None,
        texto_transcrito=None, nota_total=720,
        faixas=[], analise_da_redacao={}, detectores=[],
        ocr_quality_issues=[], raw_output=None,
        envio_id="t3", tentativa_n=3, tentativa_total=3,
        tentativas_anteriores=anteriores,
    )
    assert r.tentativa_total == 3
    assert len(r.tentativas_anteriores) == 2
    # Backend ordena desc — t2 (mais recente das anteriores) primeiro
    assert r.tentativas_anteriores[0].tentativa_n == 2
    assert r.tentativas_anteriores[1].tentativa_n == 1
