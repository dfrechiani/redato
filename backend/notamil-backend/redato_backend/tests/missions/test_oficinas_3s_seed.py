"""Testes do seed das oficinas 3S (migration j0a1b2c3d4e5) +
mapeamento `_MISSAO_TO_MODE` em `missions/router.py`.

Cobre:
1. Migration tem 11 oficinas 3S com schema correto (códigos batem
   regex, modos no enum permitido pelo CHECK constraint).
2. Router resolve_mode mapeia as 11 corretamente, incluindo:
   - OF09/OF11/OF14/OF15 → COMPLETO_INTEGRAL (vai pro path FT)
   - OF01/OF07/OF10 → COMPLETO_PARCIAL (vai por grade_mission)
   - OF03/OF04 → FOCO_C2 (mesma rubrica das 2S)
   - OF05/OF06 → FOCO_C5
3. OF02, OF08, OF12, OF13 NÃO estão no mapeamento — pendentes.
4. Padrão é canônico: prefixo RJ3, sufixo MF, oficina 2 dígitos.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path


_REPO = Path(__file__).resolve().parents[5]
_MIGRATION_PATH = (
    _REPO / "backend" / "notamil-backend" / "redato_backend"
    / "portal" / "migrations" / "versions"
    / "j0a1b2c3d4e5_seed_missoes_3s.py"
)


def _carrega_migration():
    """Carrega o módulo da migration sem registrar no sys.path."""
    spec = importlib.util.spec_from_file_location("mig_3s", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ──────────────────────────────────────────────────────────────────────
# 1. Migration — schema das 11 oficinas
# ──────────────────────────────────────────────────────────────────────

def test_migration_seed_3s_adiciona_11_missoes():
    """11 oficinas, não 12 (OF08 ficou de fora junto com OF02/12/13
    porque foco_c1 ainda está adiado — sessão dedicada futura)."""
    mod = _carrega_migration()
    assert len(mod._MISSOES_3S) == 11
    assert mod.revision == "j0a1b2c3d4e5"
    assert mod.down_revision == "i0a1b2c3d4e5"


def test_migration_3s_codigos_validos():
    """Cada código bate o padrão canônico RJ3·OFxx·MF (oficina como
    2 dígitos zero-padded). Detecta typos cedo."""
    mod = _carrega_migration()
    regex = re.compile(r"^RJ3·OF\d{2}·MF$")
    for codigo, *_ in mod._MISSOES_3S:
        assert regex.match(codigo), f"código fora do padrão: {codigo}"


def test_migration_3s_modos_validos():
    """Cada modo_correcao está no enum permitido pelo CHECK constraint
    de `missoes` (ck_missao_modo_correcao). Modos novos exigem alterar
    o constraint primeiro — esse test trava regressão silenciosa."""
    mod = _carrega_migration()
    modos_validos = {
        "foco_c1", "foco_c2", "foco_c3", "foco_c4", "foco_c5",
        "completo_parcial", "completo",
    }
    for codigo, _serie, _of, _titulo, modo in mod._MISSOES_3S:
        assert modo in modos_validos, (
            f"{codigo} tem modo_correcao={modo!r} fora do CHECK constraint"
        )


def test_migration_3s_serie_consistente():
    """Todos os entries têm serie='3S'."""
    mod = _carrega_migration()
    for codigo, serie, *_ in mod._MISSOES_3S:
        assert serie == "3S", f"{codigo} tem serie={serie}"


def test_migration_3s_oficina_numero_bate_codigo():
    """oficina_numero deve bater com o número embutido no código.
    Pega quebra entre código e numero (typo de copy-paste)."""
    mod = _carrega_migration()
    for codigo, _serie, oficina_num, *_ in mod._MISSOES_3S:
        # Extrai "OF09" do código RJ3·OF09·MF
        match = re.search(r"OF(\d{2})", codigo)
        assert match
        oficina_no_codigo = int(match.group(1))
        assert oficina_no_codigo == oficina_num, (
            f"{codigo} tem oficina_numero={oficina_num} mas código diz {oficina_no_codigo}"
        )


def test_migration_3s_excludes_pendentes():
    """OF02, OF08, OF12, OF13 NÃO devem aparecer no seed — são
    pendentes documentadas."""
    mod = _carrega_migration()
    pendentes = {"RJ3·OF02·MF", "RJ3·OF08·MF",
                 "RJ3·OF12·MF", "RJ3·OF13·MF"}
    codigos_seed = {c for c, *_ in mod._MISSOES_3S}
    sobreposicao = pendentes & codigos_seed
    assert sobreposicao == set(), (
        f"oficinas pendentes vazaram pro seed: {sobreposicao}"
    )


# ──────────────────────────────────────────────────────────────────────
# 2. Router — mapeamento _MISSAO_TO_MODE
# ──────────────────────────────────────────────────────────────────────

def test_router_resolve_mode_3s_todas_11_mapeadas():
    """As 11 oficinas seedadas devem resolver pra MissionMode válido.
    Espelha o mapeamento no migration — se faltar 1, é gap entre
    catálogo e router (atividade criada pra missão sem mode → bot
    crash)."""
    from redato_backend.missions.router import resolve_mode, MissionMode
    esperados = {
        "RJ3_OF01_MF": MissionMode.COMPLETO_PARCIAL,
        "RJ3_OF03_MF": MissionMode.FOCO_C2,
        "RJ3_OF04_MF": MissionMode.FOCO_C2,
        "RJ3_OF05_MF": MissionMode.FOCO_C5,
        "RJ3_OF06_MF": MissionMode.FOCO_C5,
        "RJ3_OF07_MF": MissionMode.COMPLETO_PARCIAL,
        "RJ3_OF09_MF": MissionMode.COMPLETO_INTEGRAL,
        "RJ3_OF10_MF": MissionMode.COMPLETO_PARCIAL,
        "RJ3_OF11_MF": MissionMode.COMPLETO_INTEGRAL,
        "RJ3_OF14_MF": MissionMode.COMPLETO_INTEGRAL,
        "RJ3_OF15_MF": MissionMode.COMPLETO_INTEGRAL,
    }
    for activity_id, mode_esperado in esperados.items():
        assert resolve_mode(activity_id) == mode_esperado, (
            f"{activity_id} esperava {mode_esperado}"
        )


def test_router_3s_completo_integral_simulados():
    """4 simulados (OF09, OF11, OF14, OF15) usam COMPLETO_INTEGRAL.
    Esses passam pelo path do _claude_grade_essay → FT BTBOS5VF
    (com fallback Sonnet via REDATO_OF14_BACKEND=claude)."""
    from redato_backend.missions.router import resolve_mode, MissionMode
    simulados = ["RJ3·OF09·MF", "RJ3·OF11·MF",
                 "RJ3·OF14·MF", "RJ3·OF15·MF"]
    for s in simulados:
        assert resolve_mode(s) == MissionMode.COMPLETO_INTEGRAL


def test_router_3s_completo_parcial_nao_aciona_FT():
    """OF01, OF07, OF10 são completo_parcial — vão por grade_mission
    (Claude com schema flat), NÃO pelo FT."""
    from redato_backend.missions.router import resolve_mode, MissionMode
    parciais = ["RJ3·OF01·MF", "RJ3·OF07·MF", "RJ3·OF10·MF"]
    for p in parciais:
        m = resolve_mode(p)
        assert m == MissionMode.COMPLETO_PARCIAL
        assert m != MissionMode.COMPLETO_INTEGRAL


def test_router_3s_pendentes_resolvem_none():
    """OF02, OF08, OF12, OF13 NÃO devem estar mapeadas — pendentes.
    resolve_mode retorna None pra activity_id não conhecido."""
    from redato_backend.missions.router import resolve_mode
    for codigo in ("RJ3·OF02·MF", "RJ3·OF08·MF",
                   "RJ3·OF12·MF", "RJ3·OF13·MF"):
        assert resolve_mode(codigo) is None, (
            f"{codigo} deveria estar pendente mas resolveu pra mode"
        )


def test_router_consistencia_com_migration():
    """Todos os códigos do seed devem estar no _MISSAO_TO_MODE
    (e vice-versa pra RJ3_*). Detecta divergência migration ↔ router."""
    from redato_backend.missions.router import _MISSAO_TO_MODE
    mod = _carrega_migration()
    seed_canonicos = {
        c.replace("·", "_") for c, *_ in mod._MISSOES_3S
    }
    router_3s = {
        k for k in _MISSAO_TO_MODE.keys() if k.startswith("RJ3_")
    }
    assert seed_canonicos == router_3s, (
        f"divergência migration vs router:\n"
        f"  só na migration: {seed_canonicos - router_3s}\n"
        f"  só no router: {router_3s - seed_canonicos}"
    )
