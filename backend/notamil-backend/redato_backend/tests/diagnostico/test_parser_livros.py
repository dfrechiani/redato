"""Testes do parser de HTMLs dos livros (Fase 5A.1).

Cobre:
1. Extração de oficinas via comments (1S)
2. Extração via cover blocks (2S/3S)
3. Identificação de mf-redato-page → tem_redato_avaliavel
4. Extração de seções via H2/H3
5. Classificação de tipo de seção (abertura, doj, missao_final, etc.)
"""
from __future__ import annotations

from pathlib import Path
import textwrap

import pytest


# ──────────────────────────────────────────────────────────────────────
# 1. Extrai oficinas (mock HTML)
# ──────────────────────────────────────────────────────────────────────

def test_parser_livro_extrai_oficinas_via_comentarios(tmp_path):
    """1S usa comentários '<!-- ════ OFICINA NN — TITLE ════ -->'."""
    from redato_backend.diagnostico.parser_livros import (
        extrair_oficinas_do_livro,
    )
    html = textwrap.dedent("""\
        <!DOCTYPE html><html><body>
        <!-- ════ OFICINA 01 — DESCRIÇÃO MISTERIOSA ════ -->
        <h2>Abertura</h2>
        <p>Conteúdo da abertura.</p>
        <h2>Mãos à Obra</h2>
        <p>Conteúdo da prática.</p>
        <!-- ════ OFICINA 02 — PALAVRA CERTA ════ -->
        <h2>Visão</h2>
        <p>Outra oficina.</p>
        </body></html>
    """)
    p = tmp_path / "livro.html"
    p.write_text(html)
    ofs = extrair_oficinas_do_livro(str(p), "1S")
    assert len(ofs) == 2
    assert ofs[0].codigo == "RJ1·OF01·MF"
    assert "DESCRIÇÃO MISTERIOSA" in ofs[0].titulo
    assert ofs[1].codigo == "RJ1·OF02·MF"
    assert "PALAVRA CERTA" in ofs[1].titulo


# ──────────────────────────────────────────────────────────────────────
# 2. Identificar mf-redato-page → tem_redato_avaliavel
# ──────────────────────────────────────────────────────────────────────

def test_parser_livro_identifica_redato_avaliavel(tmp_path):
    """Oficina com div.mf-redato-page é avaliável pelo bot."""
    from redato_backend.diagnostico.parser_livros import (
        extrair_oficinas_do_livro,
    )
    html = textwrap.dedent("""\
        <!DOCTYPE html><html><body>
        <!-- ════ OFICINA 01 — TEÓRICA ════ -->
        <h2>Abertura</h2>
        <p>Sem produção avaliável.</p>
        <!-- ════ OFICINA 02 — PRÁTICA ════ -->
        <h2>Missão Final</h2>
        <div class="production-block mf-redato-page">
          <p>Espaço pra escrever.</p>
        </div>
        </body></html>
    """)
    p = tmp_path / "livro.html"
    p.write_text(html)
    ofs = extrair_oficinas_do_livro(str(p), "1S")
    assert len(ofs) == 2
    assert ofs[0].tem_redato_avaliavel is False  # OF01 sem mf-redato-page
    assert ofs[1].tem_redato_avaliavel is True   # OF02 com mf-redato-page


# ──────────────────────────────────────────────────────────────────────
# 3. Extrai seções via H2/H3 e classifica tipo
# ──────────────────────────────────────────────────────────────────────

def test_parser_livro_extrai_secoes_e_classifica_tipo(tmp_path):
    """Cada H2 vira uma Secao; tipo é inferido pelo título."""
    from redato_backend.diagnostico.parser_livros import (
        extrair_oficinas_do_livro,
    )
    html = textwrap.dedent("""\
        <!DOCTYPE html><html><body>
        <!-- ════ OFICINA 01 — TÍTULO ════ -->
        <h2>Abertura</h2>
        <p>Texto abertura.</p>
        <h2>Decodificando o Jogo</h2>
        <p>Texto DOJ.</p>
        <h2>Missão Final</h2>
        <p>Texto missão.</p>
        <h2>Ponte</h2>
        <p>Texto ponte.</p>
        </body></html>
    """)
    p = tmp_path / "livro.html"
    p.write_text(html)
    ofs = extrair_oficinas_do_livro(str(p), "1S")
    assert len(ofs) == 1
    tipos = [s.tipo for s in ofs[0].secoes]
    assert "abertura" in tipos
    assert "doj" in tipos
    assert "missao_final" in tipos
    assert "ponte" in tipos


# ──────────────────────────────────────────────────────────────────────
# 4. Smoke real nos 3 livros
# ──────────────────────────────────────────────────────────────────────

def test_parser_livros_reais_extraem_oficinas():
    """Livros reais no repo → 14+13+15 = 42 oficinas (smoke).
    Pula se livros não estão presentes (CI sem repo completo)."""
    from redato_backend.diagnostico.parser_livros import (
        extrair_oficinas_do_livro,
    )
    backend = Path(__file__).resolve().parents[3]
    repo = backend.parent.parent
    livros = [
        (repo / "LIVRO_1S_PROF_v3_COMPLETO-checkpoints.html", "1S", 14),
        (repo / "docs/redato/v3/livros/LIVRO_ATO_2S_PROF.html", "2S", 13),
        (repo / "docs/redato/v3/livros/LIVRO_ATO_3S_PROF.html", "3S", 15),
    ]
    for path, serie, esperado in livros:
        if not path.exists():
            pytest.skip(f"livro {serie} não presente: {path}")
        ofs = extrair_oficinas_do_livro(str(path), serie)
        assert len(ofs) == esperado, (
            f"{serie}: esperava {esperado} oficinas, extraí {len(ofs)}"
        )
        # Pelo menos 1 oficina avaliável por livro (Redato existe nos 3)
        assert any(o.tem_redato_avaliavel for o in ofs), (
            f"{serie}: nenhuma oficina avaliável detectada"
        )
