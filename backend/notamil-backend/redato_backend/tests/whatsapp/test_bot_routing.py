"""Testes do roteamento do bot por atividade ativa (M9.2, 2026-04-29).

Bug que motivou: aluno turma 2A mandava foto sem código, bot listava
'10, 11, 12, 13 ou 14' (hardcoded da 1S). Aluno respondia '10', bot
processava como RJ1·OF10·MF (foco_c3, errado), atividade real era
RJ2·OF04·MF (foco_c2, correto).

Fix: bot resolve missão pela atividade ATIVA da turma do aluno.
- 1 ativa → processa direto
- >1 ativas → pergunta listando oficinas reais
- 0 ativas → pede código completo

Cobre também:
- Comando cancelar/resetar/sair
- Bypass FSM via código completo (RJ\\d·OF\\d\\d·MF)
- Extrator expandido pra OF de 1-2 dígitos
"""
from __future__ import annotations

from dataclasses import dataclass


# ──────────────────────────────────────────────────────────────────────
# Extrator novo — _extract_missao_canonical e _extract_oficina_numero
# ──────────────────────────────────────────────────────────────────────

def test_canonical_aceita_codigo_completo_2s():
    from redato_backend.whatsapp.bot import _extract_missao_canonical
    assert _extract_missao_canonical("RJ2·OF04·MF") == "RJ2·OF04·MF"
    assert _extract_missao_canonical("RJ2OF04MF") == "RJ2·OF04·MF"
    assert _extract_missao_canonical("rj2-of04-mf") == "RJ2·OF04·MF"


def test_canonical_aceita_codigo_completo_1s():
    from redato_backend.whatsapp.bot import _extract_missao_canonical
    assert _extract_missao_canonical("RJ1·OF10·MF") == "RJ1·OF10·MF"
    assert _extract_missao_canonical("rj1of14mf") == "RJ1·OF14·MF"


def test_canonical_pad_zero_em_of_de_1_digito():
    """OF4 → OF04 (canonical sempre 2 dígitos)."""
    from redato_backend.whatsapp.bot import _extract_missao_canonical
    assert _extract_missao_canonical("RJ2·OF4·MF") == "RJ2·OF04·MF"
    assert _extract_missao_canonical("RJ2-OF7-MF") == "RJ2·OF07·MF"


def test_canonical_aceita_autocorretor_iphone():
    """iPhone troca 'OF' por '0F' (O → 0)."""
    from redato_backend.whatsapp.bot import _extract_missao_canonical
    assert _extract_missao_canonical("RJ20F04MF") == "RJ2·OF04·MF"
    assert _extract_missao_canonical("RJ10F10MF") == "RJ1·OF10·MF"


def test_canonical_retorna_none_sem_prefixo():
    """Sem RJ\\d explícito → None (resolução de série fica com caller)."""
    from redato_backend.whatsapp.bot import _extract_missao_canonical
    assert _extract_missao_canonical("OF04") is None
    assert _extract_missao_canonical("4") is None
    assert _extract_missao_canonical("") is None
    assert _extract_missao_canonical("lixo") is None


def test_oficina_numero_aceita_1_e_2_digitos():
    from redato_backend.whatsapp.bot import _extract_oficina_numero
    assert _extract_oficina_numero("4") == 4
    assert _extract_oficina_numero("04") == 4
    assert _extract_oficina_numero("13") == 13
    assert _extract_oficina_numero("OF7") == 7
    assert _extract_oficina_numero("of 04") == 4


def test_oficina_numero_rejeita_fora_de_range():
    from redato_backend.whatsapp.bot import _extract_oficina_numero
    assert _extract_oficina_numero("0") is None
    assert _extract_oficina_numero("100") is None
    assert _extract_oficina_numero("não é número") is None


# ──────────────────────────────────────────────────────────────────────
# Resolver — _resolver_atividade_por_input
# ──────────────────────────────────────────────────────────────────────

@dataclass
class _AtividadeMock:
    missao_codigo: str
    oficina_numero: int


def test_resolver_codigo_completo_match_unico():
    from redato_backend.whatsapp.bot import _resolver_atividade_por_input
    atvs = [
        _AtividadeMock("RJ2·OF04·MF", 4),
        _AtividadeMock("RJ2·OF06·MF", 6),
    ]
    atv, ambig = _resolver_atividade_por_input("RJ2·OF04·MF", atvs)
    assert atv is atvs[0]
    assert ambig == []


def test_resolver_codigo_completo_sem_match():
    """Aluno mandou RJ\\d·OF\\d\\d·MF mas missão não está ativa."""
    from redato_backend.whatsapp.bot import _resolver_atividade_por_input
    atvs = [_AtividadeMock("RJ2·OF04·MF", 4)]
    atv, ambig = _resolver_atividade_por_input("RJ2·OF99·MF", atvs)
    assert atv is None
    assert ambig == []


def test_resolver_numero_solto_unico_match():
    """Caso bug original: aluno turma 2A com OF04 ativa, manda '4'."""
    from redato_backend.whatsapp.bot import _resolver_atividade_por_input
    atvs = [_AtividadeMock("RJ2·OF04·MF", 4)]
    atv, ambig = _resolver_atividade_por_input("4", atvs)
    assert atv is atvs[0]
    assert atv.missao_codigo == "RJ2·OF04·MF"  # NÃO 'RJ1·OF04·MF'


def test_resolver_numero_solto_ambiguo():
    """Aluno multi-turma (1A + 2A), mesmo número em ambas séries."""
    from redato_backend.whatsapp.bot import _resolver_atividade_por_input
    atvs = [
        _AtividadeMock("RJ1·OF12·MF", 12),
        _AtividadeMock("RJ2·OF12·MF", 12),
    ]
    atv, ambig = _resolver_atividade_por_input("12", atvs)
    assert atv is None
    assert ambig == [12]


def test_resolver_lista_vazia():
    from redato_backend.whatsapp.bot import _resolver_atividade_por_input
    atv, ambig = _resolver_atividade_por_input("4", [])
    assert atv is None
    assert ambig == []


def test_resolver_input_irrelevante():
    """Texto sem código nem número → no-op."""
    from redato_backend.whatsapp.bot import _resolver_atividade_por_input
    atvs = [_AtividadeMock("RJ2·OF04·MF", 4)]
    atv, ambig = _resolver_atividade_por_input("oi tudo bem", atvs)
    assert atv is None
    assert ambig == []


# ──────────────────────────────────────────────────────────────────────
# Formatar lista de oficinas
# ──────────────────────────────────────────────────────────────────────

def test_formatar_lista_um_numero():
    from redato_backend.whatsapp.bot import _formatar_lista_oficinas
    assert _formatar_lista_oficinas([_AtividadeMock("X", 4)]) == "4"


def test_formatar_lista_dois_numeros():
    from redato_backend.whatsapp.bot import _formatar_lista_oficinas
    out = _formatar_lista_oficinas([
        _AtividadeMock("X", 10), _AtividadeMock("Y", 11),
    ])
    assert out == "10 ou 11"


def test_formatar_lista_muitos_numeros_ordenados():
    """7 missões 2S em ordem, OF13 ao final."""
    from redato_backend.whatsapp.bot import _formatar_lista_oficinas
    out = _formatar_lista_oficinas([
        _AtividadeMock("X", 13), _AtividadeMock("X", 1),
        _AtividadeMock("X", 9), _AtividadeMock("X", 4),
        _AtividadeMock("X", 12), _AtividadeMock("X", 7),
        _AtividadeMock("X", 6),
    ])
    assert out == "1, 4, 6, 7, 9, 12 ou 13"


def test_formatar_lista_dedupe():
    """Se múltiplas turmas têm mesma OF, dedupe."""
    from redato_backend.whatsapp.bot import _formatar_lista_oficinas
    out = _formatar_lista_oficinas([
        _AtividadeMock("RJ1·OF12·MF", 12),
        _AtividadeMock("RJ2·OF12·MF", 12),
    ])
    assert out == "12"


# ──────────────────────────────────────────────────────────────────────
# Comando cancelar/resetar/sair
# ──────────────────────────────────────────────────────────────────────

def test_cancel_re_aceita_variantes():
    from redato_backend.whatsapp.bot import _CANCEL_RE
    aceitas = [
        "cancelar", "CANCELAR", "Cancel", "cancel",
        "resetar", "reset", "RESET",
        "sair", "exit",
        "recomeçar", "recomecar",
        "começar de novo", "comecar de novo",
        "  cancelar  ",  # com espaço
    ]
    for t in aceitas:
        assert _CANCEL_RE.match(t.strip()), f"{t!r} deveria casar"


def test_cancel_re_rejeita_falsos_positivos():
    from redato_backend.whatsapp.bot import _CANCEL_RE
    rejeitar = [
        "foto",
        "RJ2·OF04·MF",
        "cancela mas não",          # tem "cancel" mas com texto extra
        "vou sair de casa",          # tem "sair" mas em frase
        "10",
        "",
    ]
    for t in rejeitar:
        m = _CANCEL_RE.match(t.strip())
        assert m is None, f"{t!r} NÃO deveria casar (got {m})"


# ──────────────────────────────────────────────────────────────────────
# Compat: _extract_missao mantém comportamento 1S
# ──────────────────────────────────────────────────────────────────────

def test_extract_missao_compat_1s():
    """Pra compatibilidade com testes antigos, número 10-14 sem prefixo
    ainda assume 1S (legacy). Código novo usa _resolver_atividade_por_input."""
    from redato_backend.whatsapp.bot import _extract_missao
    assert _extract_missao("10") == "RJ1·OF10·MF"
    assert _extract_missao("14") == "RJ1·OF14·MF"


def test_extract_missao_compat_codigo_completo_2s():
    from redato_backend.whatsapp.bot import _extract_missao
    assert _extract_missao("RJ2·OF04·MF") == "RJ2·OF04·MF"


def test_extract_missao_compat_numero_2s_sem_prefixo_retorna_none():
    """Compat: 4 NÃO assume 1S (não existe OF04 1S) — retorna None.
    Código novo resolve via _resolver_atividade_por_input + atividades
    ativas do aluno."""
    from redato_backend.whatsapp.bot import _extract_missao
    assert _extract_missao("4") is None
    assert _extract_missao("1") is None


# ──────────────────────────────────────────────────────────────────────
# Validação sintática
# ──────────────────────────────────────────────────────────────────────

def test_is_valid_missao_aceita_canonical():
    from redato_backend.whatsapp.bot import _is_valid_missao
    assert _is_valid_missao("RJ1·OF10·MF") is True
    assert _is_valid_missao("RJ2·OF04·MF") is True
    assert _is_valid_missao("RJ3·OF99·MF") is True


def test_is_valid_missao_rejeita_formatos_errados():
    from redato_backend.whatsapp.bot import _is_valid_missao
    assert _is_valid_missao("RJ1OF10MF") is False     # sem middle dot
    assert _is_valid_missao("RJ1·OF1·MF") is False    # OF de 1 dígito
    assert _is_valid_missao("rj1·of10·mf") is False   # lowercase
    assert _is_valid_missao("") is False
    assert _is_valid_missao(None) is False  # type: ignore[arg-type]
