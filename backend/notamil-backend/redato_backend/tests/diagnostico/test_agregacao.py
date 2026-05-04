"""Testes da agregação de diagnóstico cognitivo por turma (Fase 4).

Estratégia:
- Helpers puros (calcular_top_lacunas, _agregar_por_descritor,
  _agregar_por_competencia, _gerar_resumo_executivo) testados sem DB
- agregar_diagnosticos_turma com session SQLAlchemy mockada
- Endpoint via inspect.getsource (auth, validação, smoke)

Cobre:
1. Top lacunas: threshold 30%, max 10, ordenação desc
2. Agregação: 25 alunos, zero alunos, metade diagnosticada
3. Endpoint: 200/403/404, aluno sem diagnóstico não conta
4. Resumo executivo: 3 alertas / sem lacunas
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock
import uuid


# ──────────────────────────────────────────────────────────────────────
# Helpers — fakes
# ──────────────────────────────────────────────────────────────────────

def _fake_diagnostico(
    *, lacunas: List[str] = None,
    incertos: List[str] = None,
    dominios: List[str] = None,
) -> Dict[str, Any]:
    """Constrói diagnóstico Fase 2 mínimo com 40 descritores
    classificados (default: tudo 'incerto')."""
    from redato_backend.diagnostico import load_descritores
    descs = load_descritores(force_reload=True)
    lacunas = set(lacunas or [])
    incertos = set(incertos or [])
    dominios = set(dominios or [])
    entries = []
    for d in descs:
        if d.id in lacunas:
            status = "lacuna"
        elif d.id in dominios:
            status = "dominio"
        elif d.id in incertos:
            status = "incerto"
        else:
            status = "incerto"  # default
        entries.append({
            "id": d.id, "status": status,
            "evidencias": [], "confianca": "media",
        })
    return {"descritores": entries, "lacunas_prioritarias": list(lacunas)[:5]}


def _fake_envio(aluno_id: uuid.UUID, diag: Dict[str, Any], when=None):
    e = MagicMock()
    e.id = uuid.uuid4()
    e.aluno_turma_id = aluno_id
    e.enviado_em = when or datetime.now(timezone.utc)
    e.diagnostico = diag
    return e


def _fake_aluno(aluno_id: uuid.UUID, ativo: bool = True):
    a = MagicMock()
    a.id = aluno_id
    a.ativo = ativo
    return a


def _make_session(alunos_ativos: List[Any], envios_diag: List[Any]):
    """Mock SQLAlchemy session: primeira query devolve alunos ativos,
    segunda devolve envios com diagnostico."""
    chamadas = {"n": 0}
    session = MagicMock()
    def fake_execute(stmt):
        chamadas["n"] += 1
        result = MagicMock()
        scalars = MagicMock()
        if chamadas["n"] == 1:
            scalars.all = MagicMock(return_value=alunos_ativos)
        else:
            scalars.all = MagicMock(return_value=envios_diag)
        result.scalars = MagicMock(return_value=scalars)
        return result
    session.execute = MagicMock(side_effect=fake_execute)
    return session


# ──────────────────────────────────────────────────────────────────────
# 1. calcular_top_lacunas — threshold + max + ordenação
# ──────────────────────────────────────────────────────────────────────

def test_calcular_top_lacunas_aplica_threshold():
    """Lacunas com <30% alunos NÃO entram no top (filtra ruído de
    turma pequena)."""
    from redato_backend.diagnostico.agregacao import calcular_top_lacunas
    agregado = [
        {
            "id": "C1.005", "competencia": "C1", "nome": "Concordância",
            "percent_lacuna": 67.0, "alunos_com_lacuna": 12,
            "sugestao_pedagogica": "x", "definicao_curta": "y",
        },
        {
            "id": "C2.005", "competencia": "C2", "nome": "Repertório",
            "percent_lacuna": 25.0, "alunos_com_lacuna": 5,  # ABAIXO threshold
            "sugestao_pedagogica": "x", "definicao_curta": "y",
        },
        {
            "id": "C3.001", "competencia": "C3", "nome": "Tese",
            "percent_lacuna": 30.0, "alunos_com_lacuna": 6,  # NO threshold (entra)
            "sugestao_pedagogica": "x", "definicao_curta": "y",
        },
    ]
    top = calcular_top_lacunas(agregado)
    ids = [t["id"] for t in top]
    assert "C1.005" in ids
    assert "C3.001" in ids
    assert "C2.005" not in ids  # filtrada (25 < 30)


def test_calcular_top_lacunas_max_10():
    """Cap de 10 mesmo se houver 20 descritores acima do threshold."""
    from redato_backend.diagnostico.agregacao import calcular_top_lacunas
    agregado = [
        {
            "id": f"C1.{i:03d}", "competencia": "C1",
            "nome": f"Desc {i}", "percent_lacuna": 50.0 + i,
            "alunos_com_lacuna": 10,
            "sugestao_pedagogica": "x", "definicao_curta": "y",
        }
        for i in range(1, 21)
    ]
    top = calcular_top_lacunas(agregado)
    assert len(top) == 10


def test_calcular_top_lacunas_ordena_por_percent_desc():
    """Ordenação: maior % primeiro. Empate aceita qualquer ordem."""
    from redato_backend.diagnostico.agregacao import calcular_top_lacunas
    agregado = [
        {"id": "C1.001", "competencia": "C1", "nome": "A",
         "percent_lacuna": 35.0, "alunos_com_lacuna": 3,
         "sugestao_pedagogica": "x", "definicao_curta": "y"},
        {"id": "C1.002", "competencia": "C1", "nome": "B",
         "percent_lacuna": 80.0, "alunos_com_lacuna": 7,
         "sugestao_pedagogica": "x", "definicao_curta": "y"},
        {"id": "C1.003", "competencia": "C1", "nome": "C",
         "percent_lacuna": 50.0, "alunos_com_lacuna": 5,
         "sugestao_pedagogica": "x", "definicao_curta": "y"},
    ]
    top = calcular_top_lacunas(agregado)
    assert [t["percent_lacuna"] for t in top] == [80.0, 50.0, 35.0]


# ──────────────────────────────────────────────────────────────────────
# 2. agregar_diagnosticos_turma — cenários
# ──────────────────────────────────────────────────────────────────────

def test_agregar_diagnosticos_turma_zero_alunos():
    """Turma sem alunos ativos → estrutura vazia + resumo de espera."""
    from redato_backend.diagnostico.agregacao import (
        agregar_diagnosticos_turma,
    )
    session = _make_session([], [])
    result = agregar_diagnosticos_turma(
        turma_id=uuid.uuid4(),
        turma_codigo="1A",
        turma_serie="1S",
        db_session=session,
    )
    assert result["turma"]["total_alunos"] == 0
    assert result["turma"]["alunos_com_diagnostico"] == 0
    # 40 descritores ainda aparecem no agregado (com contagem 0)
    assert len(result["agregado_por_descritor"]) == 40
    # Top lacunas vazio (sem dados)
    assert result["top_lacunas"] == []
    # Resumo é mensagem de espera
    assert "Aguardando" in result["resumo_executivo"]


def test_agregar_diagnosticos_turma_25_alunos():
    """25 alunos diagnosticados, 12 com lacuna em C1.005 → 48% no
    agregado."""
    from redato_backend.diagnostico.agregacao import (
        agregar_diagnosticos_turma,
    )
    alunos = [_fake_aluno(uuid.uuid4()) for _ in range(25)]
    # 12 alunos com lacuna em C1.005, 13 sem
    envios = []
    for i, a in enumerate(alunos):
        if i < 12:
            diag = _fake_diagnostico(lacunas=["C1.005"])
        else:
            diag = _fake_diagnostico(dominios=["C1.005"])
        envios.append(_fake_envio(a.id, diag))

    session = _make_session(alunos, envios)
    result = agregar_diagnosticos_turma(
        turma_id=uuid.uuid4(), turma_codigo="2B",
        turma_serie="2S", db_session=session,
    )
    assert result["turma"]["total_alunos"] == 25
    assert result["turma"]["alunos_com_diagnostico"] == 25
    # C1.005: 12/25 = 48%
    c1005 = next(d for d in result["agregado_por_descritor"] if d["id"] == "C1.005")
    assert c1005["alunos_com_lacuna"] == 12
    assert c1005["percent_lacuna"] == 48.0


def test_agregar_diagnosticos_turma_metade_diagnosticada():
    """25 alunos ativos mas só 10 com diagnóstico → 40% cobertura
    (claramente <50% pra triggerar aviso). Agregado calcula sobre 10."""
    from redato_backend.diagnostico.agregacao import (
        agregar_diagnosticos_turma,
    )
    alunos = [_fake_aluno(uuid.uuid4()) for _ in range(25)]
    # Só 10 primeiros têm envio com diagnóstico — 10/25 = 40%
    envios = [
        _fake_envio(a.id, _fake_diagnostico(lacunas=["C5.001"]))
        for a in alunos[:10]
    ]
    session = _make_session(alunos, envios)
    result = agregar_diagnosticos_turma(
        turma_id=uuid.uuid4(), turma_codigo="3C",
        turma_serie="3S", db_session=session,
    )
    assert result["turma"]["total_alunos"] == 25
    assert result["turma"]["alunos_com_diagnostico"] == 10
    assert result["turma"]["alunos_sem_diagnostico"] == 15
    # C5.001: 10/10 = 100% (denominador são os DIAGNOSTICADOS)
    c5001 = next(d for d in result["agregado_por_descritor"] if d["id"] == "C5.001")
    assert c5001["percent_lacuna"] == 100.0
    # Aviso de cobertura aparece no resumo (40% < threshold 50%)
    assert "abaixo de 50%" in result["resumo_executivo"] \
        or "Cobertura" in result["resumo_executivo"]


# ──────────────────────────────────────────────────────────────────────
# 3. Resumo executivo — template
# ──────────────────────────────────────────────────────────────────────

def test_resumo_executivo_template_3_alertas():
    """Top 3 lacunas mencionadas na frase de pontos críticos."""
    from redato_backend.diagnostico.agregacao import _gerar_resumo_executivo
    top_lacunas = [
        {"id": "C5.001", "nome": "Agente", "competencia": "C5",
         "percent_lacuna": 80.0, "qtd_alunos": 16,
         "sugestao_pedagogica": "x", "definicao_curta": "y"},
        {"id": "C5.002", "nome": "Ação", "competencia": "C5",
         "percent_lacuna": 70.0, "qtd_alunos": 14,
         "sugestao_pedagogica": "x", "definicao_curta": "y"},
        {"id": "C3.004", "nome": "Profundidade", "competencia": "C3",
         "percent_lacuna": 60.0, "qtd_alunos": 12,
         "sugestao_pedagogica": "x", "definicao_curta": "y"},
    ]
    resumo = _gerar_resumo_executivo(
        turma_codigo="1A",
        n_alunos_diagnosticados=20, n_alunos_total=20,
        agregado_por_competencia=[
            {"competencia": "C1", "percent_dominio_medio": 70.0,
             "percent_lacuna_medio": 10.0, "descritores_em_alerta": []},
            {"competencia": "C5", "percent_dominio_medio": 10.0,
             "percent_lacuna_medio": 60.0, "descritores_em_alerta": ["C5.001"]},
            {"competencia": "C2", "percent_dominio_medio": 50.0,
             "percent_lacuna_medio": 25.0, "descritores_em_alerta": []},
            {"competencia": "C3", "percent_dominio_medio": 40.0,
             "percent_lacuna_medio": 30.0, "descritores_em_alerta": []},
            {"competencia": "C4", "percent_dominio_medio": 50.0,
             "percent_lacuna_medio": 25.0, "descritores_em_alerta": []},
        ],
        top_lacunas=top_lacunas,
    )
    # Forte em C1 mencionado (norma culta)
    assert "norma culta" in resumo
    # Top 3 lacunas mencionadas
    assert "Agente" in resumo
    assert "Ação" in resumo
    assert "Profundidade" in resumo
    # Recomendação acionável
    assert "Recomenda-se" in resumo


def test_resumo_executivo_template_turma_sem_lacunas():
    """Sem descritor crítico → mensagem positiva."""
    from redato_backend.diagnostico.agregacao import _gerar_resumo_executivo
    resumo = _gerar_resumo_executivo(
        turma_codigo="1A",
        n_alunos_diagnosticados=15, n_alunos_total=20,
        agregado_por_competencia=[
            {"competencia": comp, "percent_dominio_medio": 70.0,
             "percent_lacuna_medio": 10.0, "descritores_em_alerta": []}
            for comp in ("C1", "C2", "C3", "C4", "C5")
        ],
        top_lacunas=[],
    )
    assert "Nenhum descritor crítico" in resumo or "sem concentração" in resumo


def test_resumo_executivo_zero_diagnosticados():
    """Sem diagnóstico ainda → mensagem de espera."""
    from redato_backend.diagnostico.agregacao import _gerar_resumo_executivo
    resumo = _gerar_resumo_executivo(
        turma_codigo="1A",
        n_alunos_diagnosticados=0, n_alunos_total=20,
        agregado_por_competencia=[],
        top_lacunas=[],
    )
    assert "Aguardando" in resumo


# ──────────────────────────────────────────────────────────────────────
# 4. Endpoint — invariantes de auth e schema
# ──────────────────────────────────────────────────────────────────────

def test_endpoint_agregado_professor_da_turma_200():
    """Endpoint usa _check_view_turma — concede a prof da turma OU
    coordenador da escola."""
    import inspect
    from redato_backend.portal import portal_api
    src = inspect.getsource(portal_api.diagnostico_agregado_turma)
    assert "_check_view_turma(auth, turma)" in src


def test_endpoint_agregado_outro_professor_403():
    """Não pode bypassar checagem com role-only ou pular auth."""
    import inspect
    from redato_backend.portal import portal_api
    src = inspect.getsource(portal_api.diagnostico_agregado_turma)
    # Não usa permissão mais frouxa
    assert "can_create_atividade" not in src
    # Auth obrigatória
    assert "Depends(get_current_user)" in src


def test_endpoint_agregado_turma_inexistente_404():
    """_get_turma_or_404 levanta antes de qualquer agregação."""
    import inspect
    from redato_backend.portal import portal_api
    src = inspect.getsource(portal_api.diagnostico_agregado_turma)
    assert "_get_turma_or_404(session, turma_id)" in src


def test_endpoint_agregado_aluno_sem_diagnostico_nao_conta():
    """agregar_diagnosticos_turma filtra Envio.diagnostico.isnot(None)
    — alunos sem diagnóstico não inflam denominador."""
    import inspect
    from redato_backend.diagnostico import agregacao
    src = inspect.getsource(agregacao._coletar_diagnosticos_da_turma)
    assert "Envio.diagnostico.isnot(None)" in src


# ──────────────────────────────────────────────────────────────────────
# 5. Schema response
# ──────────────────────────────────────────────────────────────────────

def test_diagnostico_agregado_response_aceita_payload():
    """DiagnosticoAgregadoResponse aceita estrutura completa.
    Atualizado em 2026-05-04 (proposta D): payload exige campo
    `narrativa` adicional pra storytelling acionável."""
    from redato_backend.portal.portal_api import (
        DiagnosticoAgregadoResponse,
        DiagnosticoTurmaResumoTurma,
        DiagnosticoTurmaPorDescritor,
        DiagnosticoTurmaPorCompetencia,
        DiagnosticoTurmaTopLacuna,
        DiagnosticoNarrativaTurma,
    )
    r = DiagnosticoAgregadoResponse(
        turma=DiagnosticoTurmaResumoTurma(
            id="x", codigo="1A", serie="1S",
            total_alunos=25, alunos_com_diagnostico=18,
            alunos_sem_diagnostico=7,
        ),
        atualizado_em="2026-05-03T22:00:00+00:00",
        agregado_por_descritor=[
            DiagnosticoTurmaPorDescritor(
                id="C1.005", competencia="C1", nome="Concordância",
                categoria_inep="Desvios gramaticais",
                alunos_com_lacuna=12, alunos_com_incerto=3,
                alunos_com_dominio=3,
                percent_lacuna=66.7, percent_dominio=16.7,
                definicao_curta="d", sugestao_pedagogica="s",
            ),
        ],
        agregado_por_competencia=[
            DiagnosticoTurmaPorCompetencia(
                competencia="C1", percent_dominio_medio=45.0,
                percent_lacuna_medio=35.0,
                descritores_em_alerta=["C1.005"],
            ),
        ],
        top_lacunas=[
            DiagnosticoTurmaTopLacuna(
                id="C1.005", competencia="C1", nome="Concordância",
                percent_lacuna=66.7, qtd_alunos=12,
                sugestao_pedagogica="s", definicao_curta="d",
                oficinas_sugeridas=[],
            ),
        ],
        resumo_executivo="A turma 1A...",
        narrativa=DiagnosticoNarrativaTurma(
            narrativa_principal="Dos 18 alunos da turma 1A...",
            acoes_agora=[],
            acoes_semana=[],
            acoes_mes=[],
        ),
    )
    assert r.turma.alunos_com_diagnostico == 18
    assert r.top_lacunas[0].percent_lacuna == 66.7
    assert r.narrativa.narrativa_principal.startswith("Dos")
