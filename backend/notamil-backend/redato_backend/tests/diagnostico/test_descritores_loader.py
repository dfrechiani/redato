"""Testes do loader de descritores (Fase 2).

Cobre:
1. load_descritores() retorna 40 descritores válidos
2. Cache em memória com mtime check (segunda chamada não relê arquivo)
3. YAML inválido levanta DescritoresInvalidosError com mensagem útil
4. PACKAGE_YAML em sincronia com REPO_YAML (fonte da verdade da Fase 1)
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest


# ──────────────────────────────────────────────────────────────────────
# 1. Carregamento básico
# ──────────────────────────────────────────────────────────────────────

def test_load_descritores_carrega_40():
    """Primeira chamada: 40 descritores, todos com 7 campos preenchidos."""
    from redato_backend.diagnostico import load_descritores
    ds = load_descritores(force_reload=True)
    assert len(ds) == 40
    # Estrutura: 8 por competência
    from collections import Counter
    dist = Counter(d.competencia for d in ds)
    for comp in ("C1", "C2", "C3", "C4", "C5"):
        assert dist[comp] == 8, f"{comp} tem {dist[comp]}, esperado 8"
    # Campos populados (validação já em _validate_and_parse, mas
    # check defensivo aqui pra alertar se a Descritor dataclass mudar)
    for d in ds:
        assert d.id and d.competencia and d.categoria_inep
        assert d.nome and d.definicao
        assert d.indicador_lacuna and d.exemplo_lacuna


def test_load_descritores_cache_funciona(monkeypatch):
    """Segunda chamada com mesmo mtime devolve a MESMA lista (cache).

    Garantia: leitura do arquivo + parse acontece 1x. Em prod (Railway)
    o YAML não muda em runtime — cache fica quente após o primeiro hit.
    """
    from redato_backend.diagnostico import load_descritores
    ds1 = load_descritores(force_reload=True)
    ds2 = load_descritores()  # sem force_reload
    # Mesma instância da lista (cache hit, não rebuilt)
    assert ds1 is ds2


# ──────────────────────────────────────────────────────────────────────
# 2. YAML inválido
# ──────────────────────────────────────────────────────────────────────

def test_load_descritores_yaml_invalido_levanta(tmp_path, monkeypatch):
    """YAML com contagem errada (não 40) → DescritoresInvalidosError."""
    from redato_backend.diagnostico.descritores import (
        DescritoresInvalidosError, load_descritores,
    )
    # YAML com só 1 descritor
    yaml_path = tmp_path / "descritores.yaml"
    yaml_path.write_text(textwrap.dedent("""\
        versao: "0.0"
        descritores:
          - id: "C1.001"
            competencia: "C1"
            categoria_inep: "Estrutura sintática"
            nome: "Estrutura sintática"
            definicao: "x"
            indicador_lacuna: "y"
            exemplo_lacuna: "z"
    """))
    monkeypatch.setenv("REDATO_DIAGNOSTICO_YAML", str(yaml_path))

    with pytest.raises(DescritoresInvalidosError) as exc:
        load_descritores(force_reload=True)
    assert "40" in str(exc.value)


def test_load_descritores_yaml_campo_faltando_levanta(tmp_path, monkeypatch):
    """YAML com descritor sem campo obrigatório → erro com ID e campo."""
    from redato_backend.diagnostico.descritores import (
        DescritoresInvalidosError, load_descritores,
    )
    # Constrói 40 descritores válidos. Indentação fixa (sem dedent)
    # pra controlar exatamente o texto pra `replace` corromper só o
    # primeiro descritor.
    def _entry(cid: str, comp: str) -> str:
        return (
            f"  - id: \"{cid}\"\n"
            f"    competencia: \"{comp}\"\n"
            f"    categoria_inep: \"x\"\n"
            f"    nome: \"n\"\n"
            f"    definicao: \"d\"\n"
            f"    indicador_lacuna: \"i\"\n"
            f"    exemplo_lacuna: \"e\"\n"
        )
    entries = [
        _entry(f"C{ci}.{n:03d}", f"C{ci}")
        for ci in range(1, 6) for n in range(1, 9)
    ]
    yaml_text = 'versao: "0.0"\ndescritores:\n' + "".join(entries)
    # Corrompe: remove a primeira ocorrência de "indicador_lacuna"
    # (vai cair na primeira entry C1.001).
    yaml_text = yaml_text.replace(
        '    indicador_lacuna: "i"\n', "", 1,
    )
    yaml_path = tmp_path / "descritores.yaml"
    yaml_path.write_text(yaml_text)
    monkeypatch.setenv("REDATO_DIAGNOSTICO_YAML", str(yaml_path))

    with pytest.raises(DescritoresInvalidosError) as exc:
        load_descritores(force_reload=True)
    assert "indicador_lacuna" in str(exc.value)


# ──────────────────────────────────────────────────────────────────────
# 3. Sincronia entre as duas cópias do YAML
# ──────────────────────────────────────────────────────────────────────

def test_descritores_yaml_em_sincronia():
    """PACKAGE_YAML (bundle pro Docker) deve ser idêntico ao REPO_YAML
    (fonte da Fase 1). Detecta drift quando alguém edita só uma cópia.

    Se este teste falhar, sincronize manualmente:
        cp docs/redato/v3/diagnostico/descritores.yaml \
           backend/notamil-backend/redato_backend/diagnostico/descritores.yaml
    """
    from redato_backend.diagnostico.descritores import (
        PACKAGE_YAML_PATH, REPO_YAML_PATH,
    )
    pkg = Path(PACKAGE_YAML_PATH).read_bytes()
    repo = Path(REPO_YAML_PATH).read_bytes()
    assert pkg == repo, (
        f"PACKAGE e REPO YAML divergiram. "
        f"package_size={len(pkg)} repo_size={len(repo)}. "
        "Re-sincronize manualmente (ver docstring do teste)."
    )
