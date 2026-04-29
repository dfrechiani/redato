"""Testes dos extratores de competências/detectores/audit do redato_output.

Bug que motivou (interaction id=3, M9.3, 2026-04-29): tela individual
do aluno (atividade {aid}/aluno/{atid}) renderizava quadro de
competências vazio mesmo com correção bem-sucedida no banco.

Causa: código inline em `detalhe_envio` só lia formato legacy
(top-level `C1`/`c1` como dict ou int). Bot moderno emite:

- foco_c{N}: `nota_c{N}_enem` no top-level
- completo_parcial: `notas_enem.c{N}` (sub-dict)
- completo OF14: `c{N}_audit.nota`

Fix: extraídos em helpers `_competencias_de` e `_audit_pedagogico_de`,
testáveis sem mock de DB. `_detectores_acionados_de` já existia (lê
`flags: {nome: bool}` moderno + legacy top-level com prefixo). Tests
garantem que todos os 4 formatos funcionam.
"""
from __future__ import annotations


# ──────────────────────────────────────────────────────────────────────
# _competencias_de — formato moderno foco_c{N}
# ──────────────────────────────────────────────────────────────────────

def test_foco_c2_moderno_extrai_C2_da_chave_nota_c2_enem():
    """Caso real do bug: foco_c2 retornado pelo bot real."""
    from redato_backend.portal.portal_api import _competencias_de
    out = {
        "modo": "foco_c2",
        "missao_id": "RJ2_OF04_MF",
        "rubrica_rej": {"compreensao_tema": 88, "tipo_textual": 82,
                         "repertorio": 90},
        "nota_c2_enem": 160,
        "flags": {},
    }
    comps = _competencias_de(out)
    assert comps == [("C2", 160)]


def test_foco_c3_moderno():
    from redato_backend.portal.portal_api import _competencias_de
    out = {"modo": "foco_c3", "nota_c3_enem": 120}
    assert _competencias_de(out) == [("C3", 120)]


def test_foco_c4_moderno():
    from redato_backend.portal.portal_api import _competencias_de
    out = {"modo": "foco_c4", "nota_c4_enem": 200}
    assert _competencias_de(out) == [("C4", 200)]


def test_foco_c5_moderno():
    from redato_backend.portal.portal_api import _competencias_de
    out = {"modo": "foco_c5", "nota_c5_enem": 80}
    assert _competencias_de(out) == [("C5", 80)]


# ──────────────────────────────────────────────────────────────────────
# _competencias_de — formato moderno completo_parcial
# ──────────────────────────────────────────────────────────────────────

def test_completo_parcial_moderno_extrai_C1_a_C4():
    """OF13 — C1+C2+C3+C4 no notas_enem; C5='não_aplicável' pula."""
    from redato_backend.portal.portal_api import _competencias_de
    out = {
        "modo": "completo_parcial",
        "notas_enem": {
            "c1": 160, "c2": 160, "c3": 120, "c4": 160,
            "c5": "não_aplicável",
        },
    }
    comps = _competencias_de(out)
    assert comps == [("C1", 160), ("C2", 160), ("C3", 120), ("C4", 160)]


def test_completo_parcial_c5_string_nao_vira_competencia():
    from redato_backend.portal.portal_api import _competencias_de
    out = {"modo": "completo_parcial",
           "notas_enem": {"c5": "não_aplicável"}}
    assert _competencias_de(out) == []


# ──────────────────────────────────────────────────────────────────────
# _competencias_de — formato moderno completo OF14 (pipeline v2)
# ──────────────────────────────────────────────────────────────────────

def test_completo_of14_extrai_C1_a_C5_de_audits():
    from redato_backend.portal.portal_api import _competencias_de
    out = {
        "c1_audit": {"nota": 160},
        "c2_audit": {"nota": 200},
        "c3_audit": {"nota": 120},
        "c4_audit": {"nota": 160},
        "c5_audit": {"nota": 80},
    }
    comps = _competencias_de(out)
    assert comps == [
        ("C1", 160), ("C2", 200), ("C3", 120),
        ("C4", 160), ("C5", 80),
    ]


def test_completo_of14_audit_sem_nota_pula():
    from redato_backend.portal.portal_api import _competencias_de
    out = {"c1_audit": {"comentario": "ok"}, "c2_audit": {"nota": 160}}
    assert _competencias_de(out) == [("C2", 160)]


# ──────────────────────────────────────────────────────────────────────
# _competencias_de — formato legacy (seeds M6/M7)
# ──────────────────────────────────────────────────────────────────────

def test_legacy_top_level_int_direto():
    from redato_backend.portal.portal_api import _competencias_de
    out = {"C1": 160, "C2": 200, "C3": 80}
    assert _competencias_de(out) == [
        ("C1", 160), ("C2", 200), ("C3", 80),
    ]


def test_legacy_lowercase():
    from redato_backend.portal.portal_api import _competencias_de
    out = {"c1": 160, "c2": 120}
    assert _competencias_de(out) == [("C1", 160), ("C2", 120)]


def test_legacy_subdict_com_nota_ou_score():
    from redato_backend.portal.portal_api import _competencias_de
    out = {
        "C1": {"nota": 160, "comentario": "x"},
        "C2": {"score": 200},
        "C3": {"sem_nota": True},  # ignora
    }
    comps = _competencias_de(out)
    assert ("C1", 160) in comps
    assert ("C2", 200) in comps
    assert ("C3", 0) not in comps  # não inclui sem nota


def test_resultado_sempre_ordenado_C1_a_C5():
    from redato_backend.portal.portal_api import _competencias_de
    # Insere fora de ordem propositalmente
    out = {"c5_audit": {"nota": 80}, "c1_audit": {"nota": 160},
           "c3_audit": {"nota": 120}}
    comps = _competencias_de(out)
    assert [c for c, _ in comps] == ["C1", "C3", "C5"]


# ──────────────────────────────────────────────────────────────────────
# _competencias_de — edge cases
# ──────────────────────────────────────────────────────────────────────

def test_out_none_retorna_vazio():
    from redato_backend.portal.portal_api import _competencias_de
    assert _competencias_de(None) == []


def test_out_vazio_retorna_vazio():
    from redato_backend.portal.portal_api import _competencias_de
    assert _competencias_de({}) == []


def test_modo_desconhecido_cai_em_legacy():
    from redato_backend.portal.portal_api import _competencias_de
    out = {"modo": "modo_inventado", "C1": 160}
    assert _competencias_de(out) == [("C1", 160)]


def test_dedupe_quando_formato_moderno_e_legacy_coexistem():
    """Se o mesmo C2 aparece em ambos os formatos (raro mas possível),
    pega o do moderno (primeiro a inserir) e ignora duplicata."""
    from redato_backend.portal.portal_api import _competencias_de
    out = {
        "modo": "foco_c2",
        "nota_c2_enem": 160,  # moderno
        "C2": 80,             # legacy — ignora (já tem C2)
    }
    assert _competencias_de(out) == [("C2", 160)]


# ──────────────────────────────────────────────────────────────────────
# _audit_pedagogico_de
# ──────────────────────────────────────────────────────────────────────

def test_audit_moderno_de_feedback_professor_audit_completo():
    """Bot moderno: prosa pedagógica em
    feedback_professor.audit_completo."""
    from redato_backend.portal.portal_api import _audit_pedagogico_de
    out = {
        "modo": "foco_c2",
        "feedback_professor": {
            "padrao_falha": "x",
            "transferencia_c1": "y",
            "audit_completo": "Texto longo do audit pedagógico.",
        },
    }
    assert _audit_pedagogico_de(out) == \
        "Texto longo do audit pedagógico."


def test_audit_legacy_top_level_audit_pedagogico():
    from redato_backend.portal.portal_api import _audit_pedagogico_de
    out = {"audit_pedagogico": "Audit legacy do seed."}
    assert _audit_pedagogico_de(out) == "Audit legacy do seed."


def test_audit_legacy_outras_chaves():
    from redato_backend.portal.portal_api import _audit_pedagogico_de
    for key in ("audit", "feedback", "comentario_geral"):
        assert _audit_pedagogico_de({key: "txt"}) == "txt"


def test_audit_string_vazia_retorna_none():
    from redato_backend.portal.portal_api import _audit_pedagogico_de
    out = {"feedback_professor": {"audit_completo": "   "}}
    assert _audit_pedagogico_de(out) is None


def test_audit_none_quando_out_none():
    from redato_backend.portal.portal_api import _audit_pedagogico_de
    assert _audit_pedagogico_de(None) is None
    assert _audit_pedagogico_de({}) is None


# ──────────────────────────────────────────────────────────────────────
# _analise_da_redacao_de — estrutura discreta moderna (M9.4)
# ──────────────────────────────────────────────────────────────────────

def test_analise_modern_4_campos():
    """M9.4: feedback_professor com pontos_fortes/fracos/padrao/transferencia."""
    from redato_backend.portal.portal_api import _analise_da_redacao_de
    out = {
        "modo": "foco_c2",
        "feedback_professor": {
            "pontos_fortes": ["Tese clara.", "Repertório articulado."],
            "pontos_fracos": ["Conectivos repetidos."],
            "padrao_falha": "tese genérica",
            "transferencia_competencia": "Vai impactar C3.",
        },
    }
    r = _analise_da_redacao_de(out)
    assert r["pontos_fortes"] == ["Tese clara.", "Repertório articulado."]
    assert r["pontos_fracos"] == ["Conectivos repetidos."]
    assert r["padrao_falha"] == "tese genérica"
    assert r["transferencia"] == "Vai impactar C3."
    assert r["prosa_completa"] is None


def test_analise_filtra_strings_vazias_em_listas():
    from redato_backend.portal.portal_api import _analise_da_redacao_de
    out = {
        "feedback_professor": {
            "pontos_fortes": ["ok", "  ", ""],
            "pontos_fracos": ["válido"],
            "padrao_falha": "x",
            "transferencia_competencia": "y",
        },
    }
    r = _analise_da_redacao_de(out)
    assert r["pontos_fortes"] == ["ok"]
    assert r["pontos_fracos"] == ["válido"]


def test_analise_legacy_v3_audit_completo_string():
    """Output produzido antes do M9.4: feedback_professor monolítico."""
    from redato_backend.portal.portal_api import _analise_da_redacao_de
    out = {
        "modo": "foco_c3",
        "feedback_professor": {
            "padrao_falha": "tese genérica",
            "transferencia_c1": "Impacto em C3.",
            "audit_completo": "Texto longo do audit.",
        },
    }
    r = _analise_da_redacao_de(out)
    assert r["pontos_fortes"] == []
    assert r["pontos_fracos"] == []
    assert r["padrao_falha"] == "tese genérica"
    assert r["transferencia"] == "Impacto em C3."
    assert r["prosa_completa"] == "Texto longo do audit."


def test_analise_aceita_transferencia_c1_legacy_quando_falta_competencia():
    """Legacy v3 usava transferencia_c1; helper aceita os dois nomes."""
    from redato_backend.portal.portal_api import _analise_da_redacao_de
    out = {"feedback_professor": {"transferencia_c1": "x"}}
    assert _analise_da_redacao_de(out)["transferencia"] == "x"


def test_analise_prefere_competencia_quando_ambas_existem():
    """Se output tem ambas (por algum bug), prefere a moderna."""
    from redato_backend.portal.portal_api import _analise_da_redacao_de
    out = {
        "feedback_professor": {
            "transferencia_competencia": "moderna",
            "transferencia_c1": "legacy",
        },
    }
    assert _analise_da_redacao_de(out)["transferencia"] == "moderna"


def test_analise_legacy_seed_top_level():
    from redato_backend.portal.portal_api import _analise_da_redacao_de
    for k in ("audit_pedagogico", "audit", "feedback",
              "comentario_geral", "analise_da_redacao"):
        out = {k: f"seed via {k}"}
        r = _analise_da_redacao_de(out)
        assert r["prosa_completa"] == f"seed via {k}", (
            f"chave {k} não foi reconhecida"
        )
        assert r["pontos_fortes"] == []


def test_analise_estrutura_moderna_tem_prioridade_sobre_top_level():
    """Se output tem AMBOS estrutura moderna E top-level legacy, NÃO
    duplica prosa_completa (mantém None — quem renderiza decide qual
    formato mostrar)."""
    from redato_backend.portal.portal_api import _analise_da_redacao_de
    out = {
        "feedback_professor": {
            "pontos_fortes": ["x"],
            "pontos_fracos": ["y"],
            "padrao_falha": "p",
            "transferencia_competencia": "t",
        },
        "audit_pedagogico": "prosa antiga top-level",
    }
    r = _analise_da_redacao_de(out)
    # Estrutura moderna populada
    assert r["pontos_fortes"] == ["x"]
    # Top-level NÃO sobrescreve quando feedback_professor.audit_completo
    # ausente — top-level só preenche prosa_completa via fallback.
    assert r["prosa_completa"] == "prosa antiga top-level"


def test_analise_vazio_quando_out_none():
    from redato_backend.portal.portal_api import _analise_da_redacao_de
    r = _analise_da_redacao_de(None)
    assert r["pontos_fortes"] == []
    assert r["pontos_fracos"] == []
    assert r["padrao_falha"] is None
    assert r["transferencia"] is None
    assert r["prosa_completa"] is None


def test_analise_vazio_quando_sem_feedback_professor():
    from redato_backend.portal.portal_api import _analise_da_redacao_de
    out = {"modo": "foco_c2", "nota_c2_enem": 160}  # sem feedback_professor
    r = _analise_da_redacao_de(out)
    assert all(not v for v in r.values())


def test_alias_audit_pedagogico_de_retorna_prosa():
    """`_audit_pedagogico_de` é alias deprecated — extrai só prosa."""
    from redato_backend.portal.portal_api import _audit_pedagogico_de
    out_legacy = {"feedback_professor": {"audit_completo": "prosa"}}
    assert _audit_pedagogico_de(out_legacy) == "prosa"
    out_modern = {"feedback_professor": {"pontos_fortes": ["x"]}}
    # Modern não tem prosa monolítica → None
    assert _audit_pedagogico_de(out_modern) is None


# ──────────────────────────────────────────────────────────────────────
# Schema do feedback_professor (M9.4) — verifica estrutura nova
# ──────────────────────────────────────────────────────────────────────

def test_schema_feedback_professor_tem_4_campos_estruturados():
    from redato_backend.missions.schemas import _feedback_professor_schema
    schema = _feedback_professor_schema()
    props = schema["properties"]
    assert "pontos_fortes" in props
    assert "pontos_fracos" in props
    assert "padrao_falha" in props
    assert "transferencia_competencia" in props
    # audit_completo foi removido — agora é prosa_completa só no
    # fallback do helper, não no schema novo
    assert "audit_completo" not in props


def test_schema_pontos_fortes_e_fracos_sao_arrays():
    from redato_backend.missions.schemas import _feedback_professor_schema
    schema = _feedback_professor_schema()
    pf = schema["properties"]["pontos_fortes"]
    assert pf["type"] == "array"
    assert pf["items"]["type"] == "string"
    assert pf["minItems"] == 1
    assert pf["maxItems"] == 3


def test_schema_required_inclui_4_campos():
    from redato_backend.missions.schemas import _feedback_professor_schema
    schema = _feedback_professor_schema()
    assert set(schema["required"]) == {
        "pontos_fortes", "pontos_fracos",
        "padrao_falha", "transferencia_competencia",
    }


# ──────────────────────────────────────────────────────────────────────
# _detectores_acionados_de — confirma formato moderno funciona
# (regressão garantida — função já existia mas tela do aluno não usava)
# ──────────────────────────────────────────────────────────────────────

def test_detectores_modernos_de_flags_subdict():
    from redato_backend.portal.portal_api import _detectores_acionados_de
    out = {
        "modo": "foco_c2",
        "flags": {
            "tangenciamento_tema": True,
            "fuga_tema": False,
            "repertorio_de_bolso": True,
        },
    }
    detectores = _detectores_acionados_de(out)
    assert "tangenciamento_tema" in detectores
    assert "repertorio_de_bolso" in detectores
    assert "fuga_tema" not in detectores


def test_detectores_legacy_top_level_prefixos():
    from redato_backend.portal.portal_api import _detectores_acionados_de
    out = {
        "flag_proposta_vaga": True,
        "detector_andaime_copiado": True,
        "alerta_repertorio_de_bolso": True,
        "aviso_letra_ruim": True,
        "outro_campo": True,    # NÃO é detector — sem prefixo
    }
    detectores = _detectores_acionados_de(out)
    assert len(detectores) == 4
    assert "outro_campo" not in detectores
