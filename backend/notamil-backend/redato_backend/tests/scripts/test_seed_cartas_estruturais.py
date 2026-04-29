"""Testes do `scripts/seed_cartas_estruturais.py` (Fase 2 passo 1).

Cobre 3 frentes:

1. **Parser xlsx** — `parse_xlsx` retorna 63 rows com cor derivada
   correta + lacunas extraídas + secao normalizada.
2. **Dry-run** — não toca o banco mesmo com xlsx válido.
3. **UPSERT idempotente** — segunda chamada com mesmo dado é no-op
   (inserted=0 updated=0). Mudança no texto vira update.

Idempotência completa contra DB real é validada pelo smoke
`scripts/test_m6_gestao.py`-style — aqui a gente mocka Session pra
testes unitários rodarem sem Postgres.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[5]
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))


# ──────────────────────────────────────────────────────────────────────
# Parser xlsx — usa o xlsx real commitado no repo
# ──────────────────────────────────────────────────────────────────────

def test_parse_xlsx_real_retorna_63_estruturais():
    """xlsx commitado em data/seeds/ tem que ter exatamente 63 rows
    com prefixo E. Drift gera erro cedo (CI / dev local)."""
    from seed_cartas_estruturais import DEFAULT_XLSX, parse_xlsx
    rows = parse_xlsx(DEFAULT_XLSX)
    assert len(rows) == 63


def test_parse_xlsx_todas_secoes_validas():
    from seed_cartas_estruturais import DEFAULT_XLSX, parse_xlsx
    from redato_backend.portal.models import SECOES_ESTRUTURAIS
    rows = parse_xlsx(DEFAULT_XLSX)
    for r in rows:
        assert r["secao"] in SECOES_ESTRUTURAIS, (
            f"row {r['codigo']} secao={r['secao']} fora de "
            f"SECOES_ESTRUTURAIS"
        )


def test_parse_xlsx_todas_cores_validas():
    from seed_cartas_estruturais import DEFAULT_XLSX, parse_xlsx
    from redato_backend.portal.models import CORES_ESTRUTURAIS
    rows = parse_xlsx(DEFAULT_XLSX)
    for r in rows:
        assert r["cor"] in CORES_ESTRUTURAIS


def test_parse_xlsx_lacunas_apenas_placeholders_validos():
    """Defesa: regex pega apenas [PLACEHOLDER_VALIDO]. Se xlsx tiver
    `[Lei 13.146]` ou `[Brasil]`, a regex `[A-Z_]+` casaria —
    `_extract_lacunas` filtra contra a whitelist."""
    from seed_cartas_estruturais import (
        DEFAULT_XLSX, PLACEHOLDERS_VALIDOS, parse_xlsx,
    )
    rows = parse_xlsx(DEFAULT_XLSX)
    for r in rows:
        for placeholder in r["lacunas"]:
            assert placeholder in PLACEHOLDERS_VALIDOS


def test_parse_xlsx_resumo_bate_com_planilha():
    """Distribuição por secao bate com a aba "Resumo" do xlsx (single
    source of truth da corretora-parceira)."""
    from seed_cartas_estruturais import (
        DEFAULT_XLSX, _resumir_por_secao, parse_xlsx,
    )
    rows = parse_xlsx(DEFAULT_XLSX)
    expected = {
        "ABERTURA": 9, "TESE": 7,
        "TOPICO_DEV1": 4, "ARGUMENTO_DEV1": 7, "REPERTORIO_DEV1": 5,
        "TOPICO_DEV2": 7, "ARGUMENTO_DEV2": 5, "REPERTORIO_DEV2": 4,
        "RETOMADA": 4, "PROPOSTA": 11,
    }
    assert _resumir_por_secao(rows) == expected


def test_parse_xlsx_ordem_e_estavel_e_unica():
    """Ordem é 1, 2, 3, ... sem gaps — espelha índice da row no xlsx.
    Frontend usa pra renderizar cartas na ordem da planilha."""
    from seed_cartas_estruturais import DEFAULT_XLSX, parse_xlsx
    rows = parse_xlsx(DEFAULT_XLSX)
    ordens = [r["ordem"] for r in rows]
    assert ordens == list(range(1, len(rows) + 1))


def test_parse_xlsx_inexistente_raise():
    from seed_cartas_estruturais import parse_xlsx
    with pytest.raises(FileNotFoundError):
        parse_xlsx(Path("/tmp/nao_existe_jamais.xlsx"))


# ──────────────────────────────────────────────────────────────────────
# Extract lacunas — unidade isolada
# ──────────────────────────────────────────────────────────────────────

def test_extract_lacunas_caso_simples():
    from seed_cartas_estruturais import _extract_lacunas
    texto = "No Brasil, [PROBLEMA] persiste. Conforme [REPERTORIO]..."
    assert _extract_lacunas(texto) == ["PROBLEMA", "REPERTORIO"]


def test_extract_lacunas_preserva_repetidos():
    """[PALAVRA_CHAVE] aparece 2x → retorna 2 entradas. Frontend
    precisa renderizar 2 slots distintos pro grupo escolher 2 cartas."""
    from seed_cartas_estruturais import _extract_lacunas
    texto = "Por [PALAVRA_CHAVE] e [PALAVRA_CHAVE] que se entrelaçam."
    assert _extract_lacunas(texto) == ["PALAVRA_CHAVE", "PALAVRA_CHAVE"]


def test_extract_lacunas_ignora_brackets_que_nao_sao_placeholder():
    """Defensivo: `[Lei 13.146]`, `[2024]` etc. não casam contra a
    whitelist de PLACEHOLDERS_VALIDOS."""
    from seed_cartas_estruturais import _extract_lacunas
    texto = "Conforme [Lei 13.146], temos [PROBLEMA] em [2024]."
    assert _extract_lacunas(texto) == ["PROBLEMA"]


def test_extract_lacunas_texto_sem_placeholder():
    from seed_cartas_estruturais import _extract_lacunas
    assert _extract_lacunas("texto sem placeholders") == []


# ──────────────────────────────────────────────────────────────────────
# UPSERT idempotência — mock Session
# ──────────────────────────────────────────────────────────────────────

class _FakeCarta:
    """Espelha CartaEstrutural pra teste sem importar a model."""
    def __init__(self, codigo, secao, cor, texto, lacunas, ordem):
        self.codigo = codigo
        self.secao = secao
        self.cor = cor
        self.texto = texto
        self.lacunas = lacunas
        self.ordem = ordem


class _FakeScalars:
    def __init__(self, items): self._items = items
    def __iter__(self): return iter(self._items)


class _FakeResult:
    def __init__(self, items): self._items = items
    def scalars(self): return _FakeScalars(self._items)


class _FakeSession:
    def __init__(self, existentes=None):
        self.existentes = existentes or []
        self.commits = 0
        self.rollbacks = 0
        self.executes: list = []

    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, stmt):
        self.executes.append(stmt)
        return _FakeResult(self.existentes)
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


def test_upsert_dry_run_nao_commita(monkeypatch):
    """Dry-run com 63 rows novas e DB vazio: relata insert=63
    update=0 mas NÃO commita."""
    import seed_cartas_estruturais as sc

    fake = _FakeSession(existentes=[])
    class _FakeEngine: pass
    monkeypatch.setattr(
        "redato_backend.portal.db.get_engine", lambda: _FakeEngine(),
    )
    import sqlalchemy.orm
    monkeypatch.setattr(sqlalchemy.orm, "Session", lambda eng: fake)

    rows = [
        {"codigo": f"E{i:02d}", "secao": "ABERTURA", "cor": "AZUL",
         "texto": "x", "lacunas": [], "ordem": i}
        for i in range(1, 64)
    ]
    inserted, updated = sc.upsert(rows, apply=False)
    assert inserted == 63
    assert updated == 0
    assert fake.commits == 0
    assert fake.rollbacks == 1


def test_upsert_apply_idempotente_segunda_chamada_nao_atualiza_nada(monkeypatch):
    """DB já tem 63 rows iguais ao xlsx: insert=0 update=0 (no-op)."""
    import seed_cartas_estruturais as sc

    rows = [
        {"codigo": f"E{i:02d}", "secao": "ABERTURA", "cor": "AZUL",
         "texto": "x", "lacunas": [], "ordem": i}
        for i in range(1, 64)
    ]
    # Banco já tem tudo idêntico
    existentes = [
        _FakeCarta(r["codigo"], r["secao"], r["cor"], r["texto"],
                    r["lacunas"], r["ordem"])
        for r in rows
    ]
    fake = _FakeSession(existentes=existentes)

    class _FakeEngine: pass
    monkeypatch.setattr(
        "redato_backend.portal.db.get_engine", lambda: _FakeEngine(),
    )
    import sqlalchemy.orm
    monkeypatch.setattr(sqlalchemy.orm, "Session", lambda eng: fake)

    inserted, updated = sc.upsert(rows, apply=True)
    assert inserted == 0
    assert updated == 0
    # Apply chama commit (mesmo se INSERT é no-op a transação fecha)
    assert fake.commits == 1


def test_upsert_apply_detecta_mudanca_de_texto(monkeypatch):
    """Daniel reescreveu E01 no xlsx — apply deve relatar updated=1
    pra essa carta."""
    import seed_cartas_estruturais as sc

    novos = [
        {"codigo": "E01", "secao": "ABERTURA", "cor": "AZUL",
         "texto": "TEXTO NOVO", "lacunas": ["PROBLEMA"], "ordem": 1},
    ]
    velhos = [
        _FakeCarta("E01", "ABERTURA", "AZUL",
                    "texto antigo", ["PROBLEMA"], 1),
    ]
    fake = _FakeSession(existentes=velhos)

    class _FakeEngine: pass
    monkeypatch.setattr(
        "redato_backend.portal.db.get_engine", lambda: _FakeEngine(),
    )
    import sqlalchemy.orm
    monkeypatch.setattr(sqlalchemy.orm, "Session", lambda eng: fake)

    inserted, updated = sc.upsert(novos, apply=True)
    assert inserted == 0
    assert updated == 1


def test_upsert_apply_detecta_carta_nova(monkeypatch):
    """Xlsx ganhou E64 novo — apply relata insert=1 (vs update do
    existente E01 também presente)."""
    import seed_cartas_estruturais as sc

    novos = [
        {"codigo": "E01", "secao": "ABERTURA", "cor": "AZUL",
         "texto": "x", "lacunas": [], "ordem": 1},
        {"codigo": "E64", "secao": "PROPOSTA", "cor": "LARANJA",
         "texto": "novo", "lacunas": [], "ordem": 64},
    ]
    velhos = [
        _FakeCarta("E01", "ABERTURA", "AZUL", "x", [], 1),
    ]
    fake = _FakeSession(existentes=velhos)

    class _FakeEngine: pass
    monkeypatch.setattr(
        "redato_backend.portal.db.get_engine", lambda: _FakeEngine(),
    )
    import sqlalchemy.orm
    monkeypatch.setattr(sqlalchemy.orm, "Session", lambda eng: fake)

    inserted, updated = sc.upsert(novos, apply=True)
    assert inserted == 1
    assert updated == 0


# ──────────────────────────────────────────────────────────────────────
# CLI — sanity
# ──────────────────────────────────────────────────────────────────────

def test_main_e_callable():
    import seed_cartas_estruturais as sc
    assert callable(sc.main)
    assert callable(sc.parse_xlsx)
    assert callable(sc.upsert)
