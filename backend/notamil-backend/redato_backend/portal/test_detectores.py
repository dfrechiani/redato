"""Testes unitários do catálogo de detectores (M7).

Roda standalone sem Postgres. Não usa pytest pra ser consistente com
os smoke tests do projeto.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

from redato_backend.portal.detectores import (  # noqa: E402
    CATEGORIAS, SEVERIDADES,
    canonical_detectores, get_canonical, humanize_detector,
    is_canonical, _normalize_codigo, severidade_de, categoria_de,
)


def test_catalog_minimum():
    """Lista mínima esperada — manter sincronizada com decisões M7."""
    cat = canonical_detectores()
    must_have = {
        "proposta_vaga", "proposta_ausente", "tese_ausente",
        "andaime_copiado", "argumentacao_circular", "repeticao_lexical",
        "conclusao_ausente", "texto_curto", "ilegivel_parcial",
    }
    missing = must_have - set(cat.keys())
    assert not missing, f"detectores canônicos faltando: {missing}"
    return f"catálogo tem {len(cat)} detectores; mínimo OK"


def test_severidade_categoria_validas():
    """Todos os detectores devem ter severidade/categoria do enum."""
    for codigo, det in canonical_detectores().items():
        assert det.severidade in SEVERIDADES, \
            f"{codigo}: severidade '{det.severidade}' inválida"
        assert det.categoria in CATEGORIAS, \
            f"{codigo}: categoria '{det.categoria}' inválida"
    return "todos detectores com severidade/categoria válidas"


def test_normalize_strip_prefix():
    """Prefixos comuns são removidos."""
    cases = [
        ("flag_proposta_vaga", "proposta_vaga"),
        ("FLAG_proposta_vaga", "proposta_vaga"),
        ("detector_repeticao_lexical", "repeticao_lexical"),
        ("alerta_andaime_copiado", "andaime_copiado"),
        ("aviso_letra_ruim", "letra_ruim"),
        ("proposta_vaga", "proposta_vaga"),  # já normalizado
        ("  proposta_vaga  ", "proposta_vaga"),  # com espaço
    ]
    for raw, expected in cases:
        got = _normalize_codigo(raw)
        assert got == expected, f"{raw!r} → {got!r} (esperava {expected!r})"
    return f"normalize_codigo OK em {len(cases)} casos"


def test_humanize_canonical():
    """Detector canônico devolve nome_humano oficial."""
    assert humanize_detector("flag_proposta_vaga") == \
        "Proposta de intervenção vaga"
    assert humanize_detector("repeticao_lexical") == "Repetição lexical"
    assert humanize_detector("DETECTOR_andaime_copiado") == \
        "Andaime copiado"
    return "humanize: detectores canônicos retornam nome oficial"


def test_humanize_nao_canonical_fallback():
    """Detector NÃO cadastrado ainda é humanizado graciosamente."""
    # Caso típico: experimento novo do time pedagógico
    assert humanize_detector("flag_proposta_irregular") == \
        "Proposta irregular"
    # Prefixo + snake_case
    assert humanize_detector("alerta_quebra_de_paragrafo_estranha") == \
        "Quebra de paragrafo estranha"
    # Sem prefixo
    assert humanize_detector("nova_heuristica_xyz") == \
        "Nova heuristica xyz"
    # Edge cases
    assert humanize_detector("") == "Detector"
    assert humanize_detector("flag_") == "Detector"
    return "humanize: fallback gracioso pra detectores desconhecidos"


def test_is_canonical_e_lookup():
    assert is_canonical("flag_proposta_vaga") is True
    assert is_canonical("proposta_vaga") is True
    assert is_canonical("flag_inventado_ainda_nao_existente") is False
    assert get_canonical("flag_proposta_vaga").categoria == "estrutural"
    assert get_canonical("not_real") is None
    return "is_canonical / get_canonical OK"


def test_severidade_e_categoria_helpers():
    assert severidade_de("flag_proposta_vaga") == "alta"
    assert severidade_de("repeticao_lexical") == "baixa"
    # detector desconhecido cai pro default
    assert severidade_de("flag_inventado") == "media"
    assert categoria_de("flag_inventado") == "forma"
    return "severidade_de / categoria_de helpers OK"


TESTS = [
    test_catalog_minimum,
    test_severidade_categoria_validas,
    test_normalize_strip_prefix,
    test_humanize_canonical,
    test_humanize_nao_canonical_fallback,
    test_is_canonical_e_lookup,
    test_severidade_e_categoria_helpers,
]


def main():
    print(f"{'='*70}")
    failures = []
    for fn in TESTS:
        try:
            res = fn()
            print(f"  ✓ {fn.__name__}: {res}")
        except AssertionError as exc:
            print(f"  ✗ {fn.__name__}: AssertionError: {exc}")
            failures.append((fn.__name__, str(exc)))
        except Exception as exc:
            print(f"  ✗ {fn.__name__}: {type(exc).__name__}: {exc}")
            failures.append((fn.__name__, repr(exc)))

    print(f"\n{'='*70}")
    if failures:
        print(f"FALHA: {len(failures)}/{len(TESTS)}")
        sys.exit(1)
    print(f"OK: {len(TESTS)}/{len(TESTS)} testes passaram")


if __name__ == "__main__":
    main()
