"""Testes do endpoint GET /portal/turmas/{turma_id}/alunos/{aluno_turma_id}/perfil.

Padrão dos tests do portal: schema validation + helpers determinísticos
+ smoke estrutural via inspect.getsource. E2E completo (auth + DB
Postgres) está em `scripts/test_m6_gestao.py` separado.

Cobre:
1. Schema da resposta (`AlunoPerfilResponse` + sub-schemas)
2. Helpers puros (sem DB):
   - `_calc_tendencia` — subindo / caindo / estavel / dados_insuficientes
   - `_calc_medias_cN` — foco contribui só pra C focada, completo pra todas
   - `_ponto_forte_fraco` — max/min entre médias preenchidas
   - `_envio_tem_problema` — null / error / nota_total ausente
   - `_envio_tem_feedback` — analise_da_redacao populada
   - `_mascarar_telefone` — mantém prefixo, mascara últimos 3
3. Estrutura crítica do endpoint:
   - Usa `_check_view_turma` (auth: prof da turma OU coordenador)
   - 404 se aluno.turma_id != turma_id
   - Resposta com stats + envios ordenados desc
"""
from __future__ import annotations


# ──────────────────────────────────────────────────────────────────────
# 1. Schema validation
# ──────────────────────────────────────────────────────────────────────

def test_perfil_aluno_response_aceita_payload_completo():
    from redato_backend.portal.portal_api import (
        AlunoPerfilResponse,
        AlunoPerfilResumo,
        AlunoPerfilStats,
        AlunoPerfilEnvio,
    )
    r = AlunoPerfilResponse(
        aluno=AlunoPerfilResumo(
            id="aluno-uuid",
            nome="Daniel Frechiani",
            telefone_mascarado="+556196668***",
            entrou_em="2026-04-30T10:00:00+00:00",
            ativo=True,
        ),
        stats=AlunoPerfilStats(
            total_envios=5,
            envios_com_nota=4,
            envios_com_problema=1,
            media_geral=720,
            medias_cN={"c1": 140, "c2": 160, "c3": 140, "c4": 140, "c5": 140},
            tendencia="subindo",
            ponto_forte="C2",
            ponto_fraco="C1",
        ),
        envios=[
            AlunoPerfilEnvio(
                id="envio-uuid",
                atividade_id="ativ-uuid",
                atividade_codigo="RJ1·OF14·MF",
                atividade_titulo="Jogo de Redação",
                oficina_numero=14,
                modo_correcao="completo",
                criado_em="2026-05-02T15:48:00+00:00",
                nota_total=720,
                notas_cN={"c1": 140, "c2": 160, "c3": 140, "c4": 140, "c5": 140},
                tem_feedback=True,
                tem_problema=False,
            ),
        ],
    )
    assert r.stats.media_geral == 720
    assert r.stats.ponto_forte == "C2"
    assert r.stats.ponto_fraco == "C1"
    assert r.envios[0].atividade_codigo == "RJ1·OF14·MF"


def test_perfil_aluno_response_aceita_estado_vazio():
    """Aluno sem envios: stats com zeros/None, envios=[]."""
    from redato_backend.portal.portal_api import (
        AlunoPerfilResponse,
        AlunoPerfilResumo,
        AlunoPerfilStats,
    )
    r = AlunoPerfilResponse(
        aluno=AlunoPerfilResumo(
            id="aluno-uuid",
            nome="Aluno Novo",
            telefone_mascarado="+5511999998***",
            entrou_em="2026-05-01T10:00:00+00:00",
            ativo=True,
        ),
        stats=AlunoPerfilStats(
            total_envios=0,
            envios_com_nota=0,
            envios_com_problema=0,
            media_geral=None,
            medias_cN={"c1": None, "c2": None, "c3": None,
                       "c4": None, "c5": None},
            tendencia="dados_insuficientes",
            ponto_forte=None,
            ponto_fraco=None,
        ),
        envios=[],
    )
    assert r.stats.total_envios == 0
    assert r.stats.media_geral is None
    assert r.envios == []


# ──────────────────────────────────────────────────────────────────────
# 2. Helpers puros — _calc_tendencia
# ──────────────────────────────────────────────────────────────────────

def test_perfil_aluno_calcula_tendencia_subindo():
    """Últimas 3 médias > 30 acima das 3 anteriores → subindo."""
    from redato_backend.portal.portal_api import _calc_tendencia
    # Ordem ASC: prev3 média 600, last3 média 700 → diff +100
    notas = [580, 600, 620, 680, 700, 720]
    assert _calc_tendencia(notas) == "subindo"


def test_perfil_aluno_calcula_tendencia_caindo():
    """Últimas 3 médias > 30 abaixo das 3 anteriores → caindo."""
    from redato_backend.portal.portal_api import _calc_tendencia
    notas = [780, 760, 740, 660, 640, 620]  # diff -100
    assert _calc_tendencia(notas) == "caindo"


def test_perfil_aluno_calcula_tendencia_estavel():
    """Diferença ≤ 30 (em valor absoluto) → estavel."""
    from redato_backend.portal.portal_api import _calc_tendencia
    # prev3 média 700, last3 média 720 → diff +20 (dentro do ruído)
    notas = [680, 700, 720, 700, 720, 740]
    assert _calc_tendencia(notas) == "estavel"


def test_perfil_aluno_dados_insuficientes_pra_tendencia():
    """< 6 envios com nota → dados_insuficientes."""
    from redato_backend.portal.portal_api import _calc_tendencia
    assert _calc_tendencia([]) == "dados_insuficientes"
    assert _calc_tendencia([700]) == "dados_insuficientes"
    assert _calc_tendencia([700, 720, 740, 760, 780]) == "dados_insuficientes"
    # Nones não contam pro mínimo de 6 — aluno com 8 envios mas só 4
    # com nota fica "dados_insuficientes".
    assert _calc_tendencia(
        [700, None, 720, None, 740, None, 760, None]
    ) == "dados_insuficientes"


# ──────────────────────────────────────────────────────────────────────
# 3. Helpers puros — _calc_medias_cN + _ponto_forte_fraco
# ──────────────────────────────────────────────────────────────────────

def test_perfil_aluno_ponto_forte_e_fraco():
    """Calcula médias C1-C5 a partir dos redato_outputs e identifica
    competência mais alta (forte) e mais baixa (fraca)."""
    from redato_backend.portal.portal_api import (
        _calc_medias_cN, _ponto_forte_fraco,
    )
    # Mistura modos:
    # - foco_c2 com nota_c2_enem=160 → contribui só pra c2
    # - completo (OF14) com c{N}_audit.nota → contribui pros 5
    # - completo_parcial com notas_enem dict → contribui pros 5
    redatos = [
        {"modo": "foco_c2", "nota_c2_enem": 160},
        {
            "modo": "completo",
            "c1_audit": {"nota": 100},
            "c2_audit": {"nota": 160},
            "c3_audit": {"nota": 120},
            "c4_audit": {"nota": 140},
            "c5_audit": {"nota": 140},
        },
        {
            "modo": "completo_parcial",
            "notas_enem": {
                "c1": 80, "c2": 160, "c3": 140, "c4": 140, "c5": 140,
            },
        },
    ]
    medias = _calc_medias_cN(redatos)
    # c1: (100+80)/2 = 90 (foco_c2 não contribui pra c1)
    # c2: (160+160+160)/3 = 160
    # c3: (120+140)/2 = 130
    # c4: (140+140)/2 = 140
    # c5: (140+140)/2 = 140
    assert medias["c1"] == 90
    assert medias["c2"] == 160
    assert medias["c3"] == 130
    assert medias["c4"] == 140
    assert medias["c5"] == 140

    forte, fraco = _ponto_forte_fraco(medias)
    assert forte == "C2"  # 160 — maior
    assert fraco == "C1"  # 90 — menor


def test_perfil_aluno_ponto_forte_fraco_sem_dados():
    """Sem competências avaliadas → forte e fraco = None."""
    from redato_backend.portal.portal_api import _ponto_forte_fraco
    forte, fraco = _ponto_forte_fraco({
        "c1": None, "c2": None, "c3": None, "c4": None, "c5": None,
    })
    assert forte is None
    assert fraco is None


def test_perfil_aluno_medias_cN_sem_envios():
    """Lista vazia / Nones → todas competências None."""
    from redato_backend.portal.portal_api import _calc_medias_cN
    medias = _calc_medias_cN([])
    assert all(v is None for v in medias.values())
    medias = _calc_medias_cN([None, None])
    assert all(v is None for v in medias.values())


# ──────────────────────────────────────────────────────────────────────
# 4. Helpers puros — _envio_tem_problema
# ──────────────────────────────────────────────────────────────────────

def test_perfil_aluno_envios_com_problema_contabilizados():
    """Envios com falha de pipeline são detectados como tem_problema=True
    pra alimentar o botão Reprocessar na UI."""
    from redato_backend.portal.portal_api import _envio_tem_problema
    # 1. redato_output null (timeout não-tratado, antes do fix)
    assert _envio_tem_problema(None, None) is True
    # 2. redato_output com error (caminho oficial do reprocessar quando falha)
    assert _envio_tem_problema(
        {"error": "OpenAIFTGradingError: timeout"}, None,
    ) is True
    # 3. redato_output presente mas nota_total não foi extraída
    #    (parser não bateu — reprocessar pode ressuscitar)
    assert _envio_tem_problema(
        {"modo": "completo", "alguma_coisa": "incompleta"}, None,
    ) is True
    # 4. Envio normal com nota → False
    assert _envio_tem_problema(
        {"modo": "completo", "nota_total_enem": 800}, 800,
    ) is False


def test_perfil_aluno_envio_tem_feedback():
    """Feedback existe quando análise pedagógica está populada."""
    from redato_backend.portal.portal_api import _envio_tem_feedback
    # Sem redato → sem feedback
    assert _envio_tem_feedback(None) is False
    # Erro → sem feedback
    assert _envio_tem_feedback({"error": "x"}) is False
    # Estruturado moderno (M9.4+)
    assert _envio_tem_feedback({
        "feedback_professor": {
            "pontos_fortes": ["argumentação consistente"],
            "pontos_fracos": [],
            "padrao_falha": "",
            "transferencia_competencia": "",
        },
    }) is True


# ──────────────────────────────────────────────────────────────────────
# 5. Helper externo já testado — _mascarar_telefone aplicado no perfil
# ──────────────────────────────────────────────────────────────────────

def test_perfil_aluno_telefone_mascarado_corretamente():
    """Mantém prefixo e mascara os últimos 3 dígitos.
    Padrão: '+5561999998888' → '+5561999998***'."""
    from redato_backend.portal.portal_api import _mascarar_telefone
    assert _mascarar_telefone("+5561999998888") == "+5561999998***"
    assert _mascarar_telefone("+5511987654321") == "+5511987654***"
    # Edge: telefone curto (< 6 chars) — passa direto
    assert _mascarar_telefone("123") == "123"
    assert _mascarar_telefone("") == ""


# ──────────────────────────────────────────────────────────────────────
# 6. Estrutura crítica do endpoint (smoke via getsource)
# ──────────────────────────────────────────────────────────────────────
#
# Padrão dos tests do portal: garantir que refactors futuros não quebrem
# os invariantes de auth/permissão/404 sem subir DB Postgres.

def test_perfil_aluno_professor_da_turma_acessa_200():
    """Endpoint usa `_check_view_turma` (= can_view_turma) — concede
    acesso ao professor da turma E ao coordenador da escola.
    Smoke: confere que a chamada está no source."""
    import inspect
    from redato_backend.portal import portal_api
    src = inspect.getsource(portal_api.perfil_aluno)
    assert "_check_view_turma(auth, turma)" in src, (
        "perfil_aluno deve passar auth+turma por _check_view_turma "
        "pra preservar acesso de professor E coordenador"
    )
    # E o helper de erro 404 vem de `_get_turma_or_404` (turma deletada
    # ou inexistente).
    assert "_get_turma_or_404(session, turma_id)" in src


def test_perfil_aluno_outro_professor_403():
    """`_check_view_turma` levanta 403 quando `can_view_turma` retorna
    False. A lógica de can_view_turma já é coberta em
    `auth/permissions.py` — aqui só confirmamos que o endpoint NÃO faz
    by-pass dessa checagem (não usa role-only, não pula auth)."""
    import inspect
    from redato_backend.portal import portal_api
    src = inspect.getsource(portal_api.perfil_aluno)
    # Não pode usar `can_create_atividade` (mais restrito — só prof) —
    # coordenador também tem que conseguir abrir.
    assert "can_create_atividade" not in src, (
        "perfil_aluno não deve usar can_create_atividade — bloquearia "
        "coordenador. Use _check_view_turma."
    )


def test_perfil_aluno_inexistente_na_turma_404():
    """Endpoint deve checar `aluno.turma_id != turma_id` (aluno-turma
    com ID válido mas em OUTRA turma da escola) — caso contrário,
    coordenador podia fazer cross-turma sem permissão correta."""
    import inspect
    from redato_backend.portal import portal_api
    src = inspect.getsource(portal_api.perfil_aluno)
    assert "aluno.turma_id != turma_id" in src
    assert "404" in src or "status_code=404" in src


def test_perfil_aluno_sem_envios_estado_vazio():
    """Aluno sem envios: total_envios=0, envios=[], stats.media_geral=
    None. Endpoint não pode quebrar com divisão por zero."""
    import inspect
    from redato_backend.portal import portal_api
    src = inspect.getsource(portal_api.perfil_aluno)
    # Guarda contra ZeroDivisionError: só calcula média se há notas válidas.
    assert "notas_validas" in src
    assert "if notas_validas" in src or "if len(notas_validas)" in src
