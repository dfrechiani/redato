"""Testes do `scripts/seed_minideck.py` (Fase 2 passo 2).

Cobre:

1. **Parser xlsx temático** — aceita aliases P/R/K/A/AC/ME/F e
   labels acentuados (REPERTÓRIO, AÇÃO, PALAVRA-CHAVE) — todos
   normalizam pra enum DB.
2. **Validação de codigo** — bate prefix com tipo, exige 2 dígitos,
   barra E## (reservado pra estruturais).
3. **Validação semântica** — minideck precisa ter todos os 7 tipos
   obrigatórios; total >= 50.
4. **Mapping de temas** — `--list` retorna os 7 temas; aba real do
   xlsx existe pra cada slug.
5. **Idempotência** — segunda chamada de `upsert_tema` sem mudanças
   é no-op (mock Session).
6. **Wrapping transacional** — erro no INSERT de cartas aborta o
   tema (não deixa minideck órfão sem cartas).
7. **Smoke do parser real do xlsx** — todos os 7 temas batem
   contagem mínima e tipos obrigatórios.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[5]
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))


# ──────────────────────────────────────────────────────────────────────
# Parser — labels e aliases
# ──────────────────────────────────────────────────────────────────────

def test_tipo_by_label_aceita_label_humano_xlsx():
    """Forma canônica que aparece nas abas (com acento e hífen)."""
    from seed_minideck import TIPO_BY_LABEL
    assert TIPO_BY_LABEL["PROBLEMA"] == "PROBLEMA"
    assert TIPO_BY_LABEL["REPERTÓRIO"] == "REPERTORIO"
    assert TIPO_BY_LABEL["PALAVRA-CHAVE"] == "PALAVRA_CHAVE"
    assert TIPO_BY_LABEL["AGENTE"] == "AGENTE"
    assert TIPO_BY_LABEL["AÇÃO"] == "ACAO"
    assert TIPO_BY_LABEL["MEIO"] == "MEIO"
    assert TIPO_BY_LABEL["FIM"] == "FIM"


def test_tipo_by_label_aceita_aliases_curtos():
    """P/R/K/A/AC/ME/F do briefing — Daniel pode preferir esses
    aliases ao re-importar de um sheet diferente."""
    from seed_minideck import TIPO_BY_LABEL
    assert TIPO_BY_LABEL["P"] == "PROBLEMA"
    assert TIPO_BY_LABEL["R"] == "REPERTORIO"
    assert TIPO_BY_LABEL["K"] == "PALAVRA_CHAVE"
    assert TIPO_BY_LABEL["A"] == "AGENTE"
    assert TIPO_BY_LABEL["AC"] == "ACAO"
    assert TIPO_BY_LABEL["ME"] == "MEIO"
    assert TIPO_BY_LABEL["F"] == "FIM"


def test_tipo_by_label_aceita_variantes_ascii():
    """Defensivo: REPERTORIO sem acento, ACAO sem cedilha+til."""
    from seed_minideck import TIPO_BY_LABEL
    assert TIPO_BY_LABEL["REPERTORIO"] == "REPERTORIO"
    assert TIPO_BY_LABEL["ACAO"] == "ACAO"
    assert TIPO_BY_LABEL["PALAVRA_CHAVE"] == "PALAVRA_CHAVE"


def test_normaliza_tipo_label_handle_none_e_lowercase():
    from seed_minideck import _normaliza_tipo_label
    assert _normaliza_tipo_label(None) is None
    assert _normaliza_tipo_label("") is None
    assert _normaliza_tipo_label("  problema  ") == "PROBLEMA"
    assert _normaliza_tipo_label("Repertório") == "REPERTÓRIO"


# ──────────────────────────────────────────────────────────────────────
# Validação de codigo
# ──────────────────────────────────────────────────────────────────────

def test_codigo_valido_passa():
    from seed_minideck import _valida_codigo
    assert _valida_codigo("P01", "PROBLEMA") is None
    assert _valida_codigo("R15", "REPERTORIO") is None
    assert _valida_codigo("K30", "PALAVRA_CHAVE") is None
    assert _valida_codigo("A10", "AGENTE") is None
    assert _valida_codigo("AC12", "ACAO") is None
    assert _valida_codigo("ME12", "MEIO") is None
    assert _valida_codigo("F10", "FIM") is None


def test_codigo_e_estrutural_reserved_e_rejeitado():
    """E## é reservado pra cartas_estruturais — barra silenciosamente
    qualquer aba temática que tente E. Daniel pode ter dragged uma
    row pra aba errada por engano."""
    from seed_minideck import _valida_codigo
    err = _valida_codigo("E01", "PROBLEMA")
    assert err is not None
    assert "reservado pra cartas_estruturais" in err


def test_codigo_sem_2_digitos_rejeita():
    """P1 (1 dígito) e P099 (3 dígitos) devem barrar — Postgres
    aceitaria mas a regex do jogo espera P01 zero-padded."""
    from seed_minideck import _valida_codigo
    assert _valida_codigo("P1", "PROBLEMA") is not None
    assert _valida_codigo("P099", "PROBLEMA") is not None
    assert _valida_codigo("P", "PROBLEMA") is not None


def test_codigo_prefixo_errado_pra_tipo():
    """P01 num row marcado como REPERTORIO bate erro — Daniel
    provavelmente trocou o tipo na aba e esqueceu de mudar codigo."""
    from seed_minideck import _valida_codigo
    err = _valida_codigo("P01", "REPERTORIO")
    assert err is not None
    assert "RNN" in err  # mensagem cita prefixo esperado


def test_codigo_2_letras_AC_ME_funciona():
    """AC e ME são 2 letras (pra diferenciar de A/M simples) +
    2 dígitos. AC01, ME12."""
    from seed_minideck import _valida_codigo
    assert _valida_codigo("AC01", "ACAO") is None
    assert _valida_codigo("ME12", "MEIO") is None
    # Mas A01 NÃO bate ACAO
    err = _valida_codigo("A01", "ACAO")
    assert err is not None


# ──────────────────────────────────────────────────────────────────────
# Validação semântica de minideck
# ──────────────────────────────────────────────────────────────────────

def _row(codigo, tipo, conteudo="x"):
    return {"codigo": codigo, "tipo": tipo, "conteudo": conteudo}


def test_valida_minideck_total_minimo():
    """< 50 cartas é suspeito — minideck real tem ~104. Daniel tá
    testando provavelmente."""
    from seed_minideck import valida_minideck
    rows = [_row("P01", "PROBLEMA")]  # só 1 carta
    problemas = valida_minideck(rows, "tema_x")
    assert any("< 50" in p for p in problemas)


def test_valida_minideck_falta_tipo_obrigatorio():
    """Minideck sem AGENTE — propostas com [AGENTE] não preencheriam.
    Validador detecta isso antes do INSERT."""
    from seed_minideck import valida_minideck
    rows = []
    # 60 cartas mas SEM AGENTE
    for i in range(15):
        rows.append(_row(f"P{i+1:02d}", "PROBLEMA"))
    for i in range(15):
        rows.append(_row(f"R{i+1:02d}", "REPERTORIO"))
    for i in range(15):
        rows.append(_row(f"K{i+1:02d}", "PALAVRA_CHAVE"))
    for i in range(5):
        rows.append(_row(f"AC{i+1:02d}", "ACAO"))
    for i in range(5):
        rows.append(_row(f"ME{i+1:02d}", "MEIO"))
    for i in range(5):
        rows.append(_row(f"F{i+1:02d}", "FIM"))
    problemas = valida_minideck(rows, "tema_x")
    assert any("AGENTE" in p and "obrigatório" in p for p in problemas)


def test_valida_minideck_codigos_duplicados():
    """Daniel copy-pasted P01 e esqueceu de renumerar — UPSERT
    silenciaria (último ganha) mas validador avisa."""
    from seed_minideck import valida_minideck
    rows = []
    rows.append(_row("P01", "PROBLEMA"))
    rows.append(_row("P01", "PROBLEMA", "outro conteudo"))  # dup
    # Padding pra passar minimum
    for i in range(60):
        rows.append(_row(f"R{i+1:02d}", "REPERTORIO"))
    # Pelo menos 1 de cada outro tipo
    rows.append(_row("K01", "PALAVRA_CHAVE"))
    rows.append(_row("A01", "AGENTE"))
    rows.append(_row("AC01", "ACAO"))
    rows.append(_row("ME01", "MEIO"))
    rows.append(_row("F01", "FIM"))
    problemas = valida_minideck(rows, "tema_x")
    assert any("duplicados" in p for p in problemas)


def test_valida_minideck_104_cartas_completo_passa():
    """Minideck completo bem-formado: 0 problemas."""
    from seed_minideck import valida_minideck
    rows = []
    for i in range(15):
        rows.append(_row(f"P{i+1:02d}", "PROBLEMA"))
    for i in range(15):
        rows.append(_row(f"R{i+1:02d}", "REPERTORIO"))
    for i in range(30):
        rows.append(_row(f"K{i+1:02d}", "PALAVRA_CHAVE"))
    for i in range(10):
        rows.append(_row(f"A{i+1:02d}", "AGENTE"))
    for i in range(12):
        rows.append(_row(f"AC{i+1:02d}", "ACAO"))
    for i in range(12):
        rows.append(_row(f"ME{i+1:02d}", "MEIO"))
    for i in range(10):
        rows.append(_row(f"F{i+1:02d}", "FIM"))
    assert len(rows) == 104
    assert valida_minideck(rows, "tema_x") == []


# ──────────────────────────────────────────────────────────────────────
# Parser real (xlsx commitado) — smoke por tema
# ──────────────────────────────────────────────────────────────────────

# 6 dos 7 temas têm os 7 tipos obrigatórios completos. Meio Ambiente
# tem só 5 tipos (MEIO + FIM ausentes no xlsx — gap conhecido).
@pytest.mark.parametrize("aba,tema,esperado_min", [
    ("Saúde Mental", "saude_mental", 100),
    ("Inclusão Digital", "inclusao_digital", 100),
    ("Violência contra a Mulher", "violencia_contra_mulher", 100),
    ("Educação Financeira", "educacao_financeira", 100),
    ("Gênero e Diversidade", "genero_diversidade", 100),
    ("Família e Sociedade", "familia_sociedade", 100),
])
def test_parse_aba_real_xlsx_temas_completos(aba, tema, esperado_min):
    """Smoke: cada tema completo tem >=100 cartas, 0 erros de parse,
    e todos os tipos obrigatórios presentes. Meio Ambiente excluído
    (tem MEIO + FIM ausentes no xlsx — ver
    `test_meio_ambiente_xlsx_incompleto_documentado`)."""
    from seed_minideck import (
        DEFAULT_XLSX, TIPOS_OBRIGATORIOS, _resumir_por_tipo,
        parse_aba, valida_minideck,
    )
    rows, erros = parse_aba(DEFAULT_XLSX, aba)
    assert erros == [], f"erros de parse em {aba}: {erros}"
    assert len(rows) >= esperado_min, (
        f"{aba} tem só {len(rows)} cartas, esperado >= {esperado_min}"
    )
    por_tipo = _resumir_por_tipo(rows)
    for tipo in TIPOS_OBRIGATORIOS:
        assert por_tipo.get(tipo, 0) > 0, (
            f"{aba} sem cartas de tipo {tipo}"
        )
    # Validador semântico passa em todos
    assert valida_minideck(rows, tema) == []


def test_meio_ambiente_xlsx_incompleto_documentado():
    """Documenta o gap: aba 'Meio Ambiente' tem 108 cartas em apenas
    5 tipos (PROBLEMA, REPERTORIO, PALAVRA_CHAVE, AGENTE, ACAO).
    MEIO e FIM estão ausentes no xlsx — `seed_minideck.py` vai
    abortar esse tema com erro semântico (tipo obrigatório ausente).

    Este teste guarda contra REGRESSÃO: se um dia Daniel completar
    o xlsx, esse teste FAIL e a gente sabe que pode mover Meio
    Ambiente pra `test_parse_aba_real_xlsx_temas_completos`. Até lá,
    `--all` vai pular Meio Ambiente (1 erro reportado, 6 sucessos)."""
    from seed_minideck import (
        DEFAULT_XLSX, _resumir_por_tipo, parse_aba, valida_minideck,
    )
    rows, erros = parse_aba(DEFAULT_XLSX, "Meio Ambiente")
    assert erros == []
    por_tipo = _resumir_por_tipo(rows)
    # Tipos presentes
    assert por_tipo.get("PROBLEMA", 0) > 0
    assert por_tipo.get("REPERTORIO", 0) > 0
    assert por_tipo.get("PALAVRA_CHAVE", 0) > 0
    assert por_tipo.get("AGENTE", 0) > 0
    assert por_tipo.get("ACAO", 0) > 0
    # Tipos AUSENTES — gap conhecido. Se algum dia ganhar > 0, o
    # validador passa a aceitar e este teste sinaliza pra mudar a
    # parametrização do teste anterior.
    assert por_tipo.get("MEIO", 0) == 0, (
        "Meio Ambiente ganhou cartas MEIO! Move pra teste de temas "
        "completos."
    )
    assert por_tipo.get("FIM", 0) == 0, (
        "Meio Ambiente ganhou cartas FIM! Move pra teste de temas "
        "completos."
    )
    # Validador semântico AINDA falha (por design — minideck
    # incompleto não deve ir pra prod até completar)
    problemas = valida_minideck(rows, "meio_ambiente")
    assert any("MEIO" in p for p in problemas)
    assert any("FIM" in p for p in problemas)


def test_parse_aba_inexistente_raise():
    from seed_minideck import DEFAULT_XLSX, parse_aba
    with pytest.raises(RuntimeError, match="não encontrada"):
        parse_aba(DEFAULT_XLSX, "Aba que não existe")


def test_parse_aba_xlsx_inexistente_raise():
    from seed_minideck import parse_aba
    with pytest.raises(FileNotFoundError):
        parse_aba(Path("/tmp/nao_existe.xlsx"), "Saúde Mental")


def test_parse_aba_saude_mental_distribuicao_bate_proposta():
    """Distribuição de Saúde Mental documentada na proposta seção
    A.1: 15 P + 15 R + 30 K + 10 A + 12 AC + 12 ME + 10 F = 104."""
    from seed_minideck import DEFAULT_XLSX, _resumir_por_tipo, parse_aba
    rows, _ = parse_aba(DEFAULT_XLSX, "Saúde Mental")
    por_tipo = _resumir_por_tipo(rows)
    assert por_tipo == {
        "PROBLEMA": 15, "REPERTORIO": 15, "PALAVRA_CHAVE": 30,
        "AGENTE": 10, "ACAO": 12, "MEIO": 12, "FIM": 10,
    }


# ──────────────────────────────────────────────────────────────────────
# Mapping de temas / CLI --list
# ──────────────────────────────────────────────────────────────────────

def test_temas_mapeamento_tem_7_entradas():
    from seed_minideck import TEMAS_MAPEAMENTO
    assert len(TEMAS_MAPEAMENTO) == 7


def test_temas_mapeamento_aba_existe_no_xlsx():
    """Cada slug do mapping tem aba real no xlsx — sanity vs drift
    se Daniel renomear aba sem atualizar TEMAS_MAPEAMENTO."""
    import openpyxl
    from seed_minideck import DEFAULT_XLSX, TEMAS_MAPEAMENTO
    wb = openpyxl.load_workbook(DEFAULT_XLSX, read_only=True)
    sheets = set(wb.sheetnames)
    for nome_humano in TEMAS_MAPEAMENTO.keys():
        assert nome_humano in sheets, (
            f"aba {nome_humano!r} não existe no xlsx — "
            f"sheets={sheets}"
        )


def test_temas_slug_e_canonico_snake_case():
    """Slugs são lowercase, ASCII, snake_case. Vão pra URL/JSON e
    têm que ser estáveis."""
    import re
    from seed_minideck import TEMAS_MAPEAMENTO
    for slug in TEMAS_MAPEAMENTO.values():
        assert re.match(r"^[a-z][a-z0-9_]*$", slug), (
            f"slug {slug!r} não é snake_case canônico"
        )


# ──────────────────────────────────────────────────────────────────────
# Idempotência + transactional — mock Session
# ──────────────────────────────────────────────────────────────────────

class _FakeMD:
    def __init__(self, id, tema, nome_humano, descricao=None):
        self.id = id
        self.tema = tema
        self.nome_humano = nome_humano
        self.descricao = descricao


class _FakeCarta:
    def __init__(self, codigo, tipo, conteudo):
        self.codigo = codigo
        self.tipo = tipo
        self.conteudo = conteudo


class _FakeScalars:
    def __init__(self, items): self._items = items
    def __iter__(self): return iter(self._items)


class _FakeResult:
    def __init__(self, val=None, items=None):
        self._val = val
        self._items = items or []
    def scalar_one_or_none(self): return self._val
    def scalar_one(self): return self._val
    def scalars(self): return _FakeScalars(self._items)


def _is_select(stmt) -> bool:
    """Diferencia SELECT de INSERT/UPDATE/DELETE pra mock saber quando
    consumir o queue de results. SQLAlchemy `Select` é uma classe
    distinta de `Insert`."""
    cls_name = type(stmt).__name__
    return "Select" in cls_name


class _FakeSession:
    """Mock SQLAlchemy Session pra testar pipeline sem Postgres real.

    `query_returns` é uma fila — APENAS SELECTs consomem. INSERTs
    retornam result vazio sem consumir o queue. Isso bate com o uso
    real: a gente só liga pro retorno de SELECT (scalar/scalars),
    INSERT é fire-and-forget (commit decide o resultado final).

    Ordem dos SELECTs em `upsert_tema`:
        1. SELECT minideck WHERE tema (existe?)
        2. (apply only) SELECT minideck WHERE tema (re-fetch p/ id)
        3. SELECT cartas WHERE minideck_id (existem quais codigos)

    Em dry-run são 2 SELECTs (sem re-fetch). Em apply são 3.
    """
    def __init__(self, query_returns=None, raise_on_execute_n=None):
        self.query_returns = list(query_returns or [])
        self.raise_on_execute_n = raise_on_execute_n
        self.commits = 0
        self.rollbacks = 0
        self.executes = 0

    def __enter__(self): return self
    def __exit__(self, *args): pass

    def execute(self, stmt):
        self.executes += 1
        if (self.raise_on_execute_n is not None
                and self.executes == self.raise_on_execute_n):
            from sqlalchemy.exc import IntegrityError
            raise IntegrityError("fake", "fake", Exception("forced"))
        if not _is_select(stmt):
            return _FakeResult()  # INSERTs não consomem queue
        if self.query_returns:
            r = self.query_returns.pop(0)
            return r if isinstance(r, _FakeResult) else _FakeResult(r)
        return _FakeResult()

    def flush(self): pass
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


@pytest.fixture
def patch_engine_session(monkeypatch):
    """Patch get_engine + Session pra retornar o fake fornecido."""
    def _patch(fake_session):
        class _FakeEngine: pass
        monkeypatch.setattr(
            "redato_backend.portal.db.get_engine",
            lambda: _FakeEngine(),
        )
        import sqlalchemy.orm
        monkeypatch.setattr(
            sqlalchemy.orm, "Session", lambda eng: fake_session,
        )
    return _patch


def _rows_minimo_validas(n=60):
    rows = []
    n_each = max(1, n // 7)
    types_prefixos = [
        ("PROBLEMA", "P"), ("REPERTORIO", "R"), ("PALAVRA_CHAVE", "K"),
        ("AGENTE", "A"), ("ACAO", "AC"), ("MEIO", "ME"), ("FIM", "F"),
    ]
    for tipo, prefix in types_prefixos:
        for i in range(n_each):
            rows.append({
                "codigo": f"{prefix}{i+1:02d}",
                "tipo": tipo,
                "conteudo": f"conteudo {prefix}{i+1:02d}",
            })
    return rows


def test_upsert_tema_dry_run_nao_commita(patch_engine_session):
    from seed_minideck import upsert_tema
    fake = _FakeSession(query_returns=[
        # SELECT minideck — não existe
        _FakeResult(val=None),
        # SELECT cartas — vazio (md_id é None em dry-run)
    ])
    patch_engine_session(fake)
    rows = _rows_minimo_validas(70)
    stats = upsert_tema(
        tema="t1", nome_humano="T1", rows=rows, apply=False,
    )
    assert fake.commits == 0
    assert fake.rollbacks == 1
    assert stats.minideck_inserted is True
    assert stats.cartas_inserted == len(rows)


def test_upsert_tema_apply_commita_e_seta_inserted(patch_engine_session):
    """Apply com tema novo + cartas novas: minideck_inserted=True,
    cartas_inserted=N, commit chamado."""
    from seed_minideck import upsert_tema
    md_novo = _FakeMD(id=uuid.uuid4(), tema="t2", nome_humano="T2")
    fake = _FakeSession(query_returns=[
        _FakeResult(val=None),         # SELECT inicial — não existe
        _FakeResult(val=md_novo),       # re-fetch após INSERT
        _FakeResult(items=[]),          # cartas existentes — vazio
    ])
    patch_engine_session(fake)
    rows = _rows_minimo_validas(70)
    stats = upsert_tema(
        tema="t2", nome_humano="T2", rows=rows, apply=True,
    )
    assert fake.commits == 1
    assert stats.minideck_inserted is True
    assert stats.cartas_inserted == len(rows)
    assert stats.erro is None


def test_upsert_tema_idempotente_segunda_chamada_nao_atualiza_nada(
    patch_engine_session,
):
    """DB já tem md + todas as cartas idênticas: insert=0 update=0
    unchanged=N."""
    from seed_minideck import upsert_tema
    md_id = uuid.uuid4()
    md_existente = _FakeMD(
        id=md_id, tema="t3", nome_humano="T3",
    )
    rows = _rows_minimo_validas(70)
    cartas_existentes = [
        _FakeCarta(r["codigo"], r["tipo"], r["conteudo"])
        for r in rows
    ]
    fake = _FakeSession(query_returns=[
        _FakeResult(val=md_existente),         # SELECT inicial — existe
        _FakeResult(val=md_existente),         # re-fetch após no-op INSERT
        _FakeResult(items=cartas_existentes),  # cartas — todas presentes
    ])
    patch_engine_session(fake)
    stats = upsert_tema(
        tema="t3", nome_humano="T3", rows=rows, apply=True,
    )
    assert stats.minideck_inserted is False
    assert stats.minideck_updated is False
    assert stats.cartas_inserted == 0
    assert stats.cartas_updated == 0
    assert stats.cartas_unchanged == len(rows)
    assert fake.commits == 1


def test_upsert_tema_detecta_update_em_conteudo_carta(
    patch_engine_session,
):
    """Daniel reescreveu P01 no xlsx — apply detecta update=1."""
    from seed_minideck import upsert_tema
    md_id = uuid.uuid4()
    md_existente = _FakeMD(id=md_id, tema="t4", nome_humano="T4")

    rows_novos = _rows_minimo_validas(70)
    rows_novos[0]["conteudo"] = "conteudo NOVO de P01"

    cartas_existentes = []
    for i, r in enumerate(rows_novos):
        if i == 0:
            cartas_existentes.append(
                _FakeCarta(r["codigo"], r["tipo"], "conteudo VELHO"),
            )
        else:
            cartas_existentes.append(
                _FakeCarta(r["codigo"], r["tipo"], r["conteudo"]),
            )

    fake = _FakeSession(query_returns=[
        _FakeResult(val=md_existente),
        _FakeResult(val=md_existente),
        _FakeResult(items=cartas_existentes),
    ])
    patch_engine_session(fake)
    stats = upsert_tema(
        tema="t4", nome_humano="T4", rows=rows_novos, apply=True,
    )
    assert stats.cartas_updated == 1
    assert stats.cartas_unchanged == len(rows_novos) - 1


def test_upsert_tema_falha_no_meio_seta_erro_e_nao_commita(
    patch_engine_session,
):
    """Wrapping transacional: IntegrityError numa query no meio do
    pipeline NÃO chama commit — script reporta erro pra Daniel sem
    deixar md órfão sem cartas."""
    from seed_minideck import upsert_tema
    fake = _FakeSession(
        query_returns=[
            _FakeResult(val=None),
        ],
        raise_on_execute_n=2,  # 2ª execute (INSERT minideck) bate erro
    )
    patch_engine_session(fake)
    rows = _rows_minimo_validas(70)
    stats = upsert_tema(
        tema="t5", nome_humano="T5", rows=rows, apply=True,
    )
    assert fake.commits == 0
    assert stats.erro is not None


def test_upsert_tema_apply_md_existente_atualiza_nome_humano(
    patch_engine_session,
):
    """Daniel renomeou aba 'Saúde Mental' pra 'Saúde Mental e Bem-Estar'
    — UPSERT detecta minideck_updated=True."""
    from seed_minideck import upsert_tema
    md_id = uuid.uuid4()
    md_existente = _FakeMD(
        id=md_id, tema="t6", nome_humano="Velho Nome",
    )
    rows = _rows_minimo_validas(70)
    cartas_existentes = [
        _FakeCarta(r["codigo"], r["tipo"], r["conteudo"]) for r in rows
    ]
    fake = _FakeSession(query_returns=[
        _FakeResult(val=md_existente),
        _FakeResult(val=md_existente),
        _FakeResult(items=cartas_existentes),
    ])
    patch_engine_session(fake)
    stats = upsert_tema(
        tema="t6", nome_humano="Novo Nome", rows=rows, apply=True,
    )
    assert stats.minideck_updated is True
    assert stats.minideck_inserted is False


# ──────────────────────────────────────────────────────────────────────
# CLI sanity
# ──────────────────────────────────────────────────────────────────────

def test_main_e_processar_tema_callable():
    import seed_minideck as sm
    assert callable(sm.main)
    assert callable(sm.processar_tema)
    assert callable(sm.upsert_tema)
    assert callable(sm.parse_aba)
