"""Testes da infra de dashboard professor via WhatsApp (PROMPT 1/2).

Cobre:
1. Schema do MeResponse com campos novos opcionais.
2. Schema do TelefoneRequest + regex E.164.
3. Estrutura dos endpoints /auth/perfil/telefone (PATCH/DELETE) via
   inspect.getsource — regressão contra refactors.
4. Migration revisão correta (i0a1b2c3d4e5).
5. Schema do ProfessorVinculo + comportamento defensivo de
   find_professor_por_telefone quando DATABASE_URL ausente.
"""
from __future__ import annotations


# ──────────────────────────────────────────────────────────────────────
# 1. MeResponse — campos novos opcionais
# ──────────────────────────────────────────────────────────────────────

def test_me_response_aceita_telefone_e_lgpd():
    """Schema deve aceitar telefone + lgpd_aceito_em opcionais."""
    from redato_backend.portal.auth.api import MeResponse
    r = MeResponse(
        id="00000000-0000-0000-0000-000000000001",
        nome="Prof Teste",
        email="prof@teste.com",
        papel="professor",
        escola_id="00000000-0000-0000-0000-000000000002",
        escola_nome="Escola X",
        telefone="+5561912345678",
        lgpd_aceito_em="2026-05-02T12:00:00+00:00",
    )
    assert r.telefone == "+5561912345678"
    assert r.lgpd_aceito_em is not None


def test_me_response_telefone_omitido_default_none():
    """Coordenador (e professor sem telefone) → ambos campos None."""
    from redato_backend.portal.auth.api import MeResponse
    r = MeResponse(
        id="00000000-0000-0000-0000-000000000001",
        nome="Coord", email="coord@teste.com", papel="coordenador",
        escola_id="00000000-0000-0000-0000-000000000002",
        escola_nome="Escola X",
    )
    assert r.telefone is None
    assert r.lgpd_aceito_em is None


# ──────────────────────────────────────────────────────────────────────
# 2. TelefoneRequest + regex E.164
# ──────────────────────────────────────────────────────────────────────

def test_telefone_request_aceita_string():
    """Schema TelefoneRequest é só string — validação E.164 é
    no handler, não no schema (mensagem de erro mais clara)."""
    from redato_backend.portal.auth.api import TelefoneRequest
    r = TelefoneRequest(telefone="+5561912345678")
    assert r.telefone == "+5561912345678"


def test_regex_e164_aceita_formatos_validos():
    """+ + 10-15 dígitos. BR padrão: +55 + DDD + 9 + 8 dígitos = 14
    chars. Internacional curto: +1 + 10 dígitos = 12 chars."""
    from redato_backend.portal.auth.api import _TELEFONE_E164_RE
    assert _TELEFONE_E164_RE.match("+5561912345678")  # BR celular
    assert _TELEFONE_E164_RE.match("+12025551234")     # US
    assert _TELEFONE_E164_RE.match("+5511999998888")   # SP celular
    # 10 dígitos é o mínimo
    assert _TELEFONE_E164_RE.match("+1234567890")


def test_regex_e164_rejeita_formatos_invalidos():
    from redato_backend.portal.auth.api import _TELEFONE_E164_RE
    # Sem + inicial
    assert not _TELEFONE_E164_RE.match("5561912345678")
    # Letras
    assert not _TELEFONE_E164_RE.match("+55abc12345678")
    # Curto demais (<10 dígitos)
    assert not _TELEFONE_E164_RE.match("+123456789")
    # Longo demais (>15 dígitos)
    assert not _TELEFONE_E164_RE.match("+1234567890123456")
    # Espaço/parênteses (humanos digitam mas não passa)
    assert not _TELEFONE_E164_RE.match("+55 (61) 91234-5678")
    # String vazia
    assert not _TELEFONE_E164_RE.match("")


# ──────────────────────────────────────────────────────────────────────
# 3. Endpoints estrutura (regressão via inspect.getsource)
# ──────────────────────────────────────────────────────────────────────

def test_patch_telefone_rejeita_coordenador():
    """Coordenador não pode vincular telefone (escopo M10 cobre só
    professor). Endpoint deve responder 403."""
    import inspect
    from redato_backend.portal.auth.api import patch_perfil_telefone
    src = inspect.getsource(patch_perfil_telefone)
    assert 'auth.papel != "professor"' in src
    assert "HTTP_403_FORBIDDEN" in src


def test_patch_telefone_valida_unicidade():
    """Outro professor com mesmo telefone → 409 Conflict.
    Backend valida ANTES do INSERT pra dar mensagem clara
    (em vez do IntegrityError do índice único)."""
    import inspect
    from redato_backend.portal.auth.api import patch_perfil_telefone
    src = inspect.getsource(patch_perfil_telefone)
    assert "HTTP_409_CONFLICT" in src
    assert "Professor.telefone == telefone" in src
    assert "Professor.id != auth.user_id" in src


def test_patch_telefone_zera_lgpd_em_novo_telefone():
    """Vincular telefone novo (mesmo se professor já tinha outro)
    força reset do LGPD — aceite vale por telefone, não por user."""
    import inspect
    from redato_backend.portal.auth.api import patch_perfil_telefone
    src = inspect.getsource(patch_perfil_telefone)
    assert "prof.lgpd_aceito_em = None" in src


def test_delete_telefone_limpa_3_campos():
    """DELETE limpa telefone + telefone_verificado_em + lgpd_aceito_em
    (evita audit trail inconsistente quando re-vincula)."""
    import inspect
    from redato_backend.portal.auth.api import delete_perfil_telefone
    src = inspect.getsource(delete_perfil_telefone)
    assert "prof.telefone = None" in src
    assert "prof.telefone_verificado_em = None" in src
    assert "prof.lgpd_aceito_em = None" in src


# ──────────────────────────────────────────────────────────────────────
# 4. Migration alembic — revisão correta
# ──────────────────────────────────────────────────────────────────────

def test_migration_revision_aponta_pro_anterior_correto():
    """Migration nova deve descender de h0a1b2c3d4e5 (jogo redacao).
    Quebra se alguém mexer no head accidentalmente."""
    import importlib.util
    from pathlib import Path
    repo = Path(__file__).resolve().parents[5]
    mig_path = (
        repo / "backend" / "notamil-backend" / "redato_backend"
        / "portal" / "migrations" / "versions"
        / "i0a1b2c3d4e5_professor_telefone.py"
    )
    assert mig_path.exists(), f"migration não encontrada em {mig_path}"
    spec = importlib.util.spec_from_file_location("mig", mig_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.revision == "i0a1b2c3d4e5"
    assert mod.down_revision == "h0a1b2c3d4e5"


def test_migration_upgrade_adiciona_3_colunas_e_indice():
    """upgrade() cria 3 colunas + índice único parcial."""
    import inspect
    import importlib.util
    from pathlib import Path
    repo = Path(__file__).resolve().parents[5]
    mig_path = (
        repo / "backend" / "notamil-backend" / "redato_backend"
        / "portal" / "migrations" / "versions"
        / "i0a1b2c3d4e5_professor_telefone.py"
    )
    spec = importlib.util.spec_from_file_location("mig", mig_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    src = inspect.getsource(mod.upgrade)
    # 3 colunas adicionadas
    assert 'add_column("professores"' in src or 'add_column(\n        "professores"' in src
    assert "telefone" in src
    assert "telefone_verificado_em" in src
    assert "lgpd_aceito_em" in src
    # Índice único parcial
    assert "create_index" in src
    assert "unique=True" in src
    assert "postgresql_where" in src


# ──────────────────────────────────────────────────────────────────────
# 5. ProfessorVinculo + find_professor_por_telefone defensivo
# ──────────────────────────────────────────────────────────────────────

def test_professor_vinculo_dataclass():
    """Schema mínimo pro bot processar mensagens de professor."""
    import uuid
    from datetime import datetime, timezone
    from redato_backend.whatsapp.portal_link import ProfessorVinculo
    pv = ProfessorVinculo(
        id=uuid.uuid4(),
        nome="Prof Maria",
        escola_id=uuid.uuid4(),
        lgpd_aceito_em=None,
    )
    assert pv.nome == "Prof Maria"
    assert pv.lgpd_aceito_em is None
    pv2 = ProfessorVinculo(
        id=uuid.uuid4(), nome="Prof X",
        escola_id=uuid.uuid4(),
        lgpd_aceito_em=datetime.now(timezone.utc),
    )
    assert pv2.lgpd_aceito_em is not None


def test_find_professor_por_telefone_phone_vazio_retorna_none():
    """Defensiva: phone="" ou None → return early, sem tocar DB."""
    from redato_backend.whatsapp.portal_link import find_professor_por_telefone
    assert find_professor_por_telefone("") is None


def test_find_professor_por_telefone_db_indisponivel_retorna_none():
    """Sem DATABASE_URL configurada (test default), DB lookup levanta
    RuntimeError. Função deve capturar e retornar None pra não derrubar
    o fluxo de aluno em handle_inbound."""
    from redato_backend.whatsapp.portal_link import find_professor_por_telefone
    # Phone qualquer — não importa, vai falhar no get_engine
    assert find_professor_por_telefone("+5561999999999") is None


# ──────────────────────────────────────────────────────────────────────
# 6. Bot — _handle_professor_inbound + dispatch
# ──────────────────────────────────────────────────────────────────────

def _professor_vinculo(lgpd_aceito_em=None):
    """Helper: cria ProfessorVinculo pra tests do bot."""
    import uuid
    from redato_backend.whatsapp.portal_link import ProfessorVinculo
    return ProfessorVinculo(
        id=uuid.uuid4(),
        nome="Prof Maria",
        escola_id=uuid.uuid4(),
        lgpd_aceito_em=lgpd_aceito_em,
    )


def test_handle_professor_sem_lgpd_envia_aviso(monkeypatch):
    """Professor 1ª vez (lgpd_aceito_em=None) + texto vazio →
    envia AVISO_LGPD_PROFESSOR."""
    from redato_backend.whatsapp.bot import (
        _handle_professor_inbound, InboundMessage,
    )
    from redato_backend.whatsapp import messages as MSG

    msg = InboundMessage(phone="+5561999", text=None)
    out = _handle_professor_inbound(msg, _professor_vinculo())
    assert len(out) == 1
    assert "AVISO LGPD" in out[0].text
    assert "Prof Maria" in out[0].text


def test_handle_professor_aceita_lgpd_marca_db(monkeypatch):
    """Professor responde 'sim' → chama marcar_lgpd_aceito_professor +
    envia placeholder."""
    from redato_backend.whatsapp.bot import (
        _handle_professor_inbound, InboundMessage,
    )
    from redato_backend.whatsapp import portal_link as PL

    chamado = {"count": 0}
    def fake_marcar(prof_id):
        chamado["count"] += 1
    monkeypatch.setattr(PL, "marcar_lgpd_aceito_professor", fake_marcar)

    msg = InboundMessage(phone="+5561999", text="sim")
    out = _handle_professor_inbound(msg, _professor_vinculo())
    assert chamado["count"] == 1
    # 2 mensagens: confirmação + placeholder
    assert len(out) == 2
    assert "Obrigado" in out[0].text
    assert "construção" in out[1].text or "Dashboard" in out[1].text


def test_handle_professor_lgpd_aceito_envia_placeholder():
    """Professor já aceitou (lgpd_aceito_em != None) + qualquer texto →
    placeholder MSG_DASHBOARD_PLACEHOLDER (PROMPT 2 vai trocar por
    dispatcher de comandos)."""
    from datetime import datetime, timezone
    from redato_backend.whatsapp.bot import (
        _handle_professor_inbound, InboundMessage,
    )

    msg = InboundMessage(phone="+5561999", text="qualquer coisa")
    out = _handle_professor_inbound(
        msg, _professor_vinculo(lgpd_aceito_em=datetime.now(timezone.utc)),
    )
    assert len(out) == 1
    assert "construção" in out[0].text or "Dashboard" in out[0].text
    assert "Prof Maria" in out[0].text


def test_handle_professor_resposta_invalida_pede_de_novo():
    """Professor responde algo que não é sim/não/vazio durante
    AGUARDANDO_LGPD → pede confirmação clara."""
    from redato_backend.whatsapp.bot import (
        _handle_professor_inbound, InboundMessage,
    )

    msg = InboundMessage(phone="+5561999", text="oi tudo bem?")
    out = _handle_professor_inbound(msg, _professor_vinculo())
    assert len(out) == 1
    assert "confirmação" in out[0].text.lower() or "Responde" in out[0].text


def test_handle_inbound_chama_professor_lookup_antes_de_aluno(monkeypatch):
    """Smoke estrutural: handle_inbound em bot.py deve chamar
    find_professor_por_telefone ANTES de get_aluno. Refactor que mover
    pode quebrar roteamento — esse test pega cedo."""
    import inspect
    from redato_backend.whatsapp import bot

    src = inspect.getsource(bot.handle_inbound)
    pos_find_prof = src.find("find_professor_por_telefone")
    pos_get_aluno = src.find("P.get_aluno(msg.phone)")
    assert pos_find_prof > 0, "perdeu find_professor_por_telefone"
    assert pos_get_aluno > 0, "perdeu get_aluno"
    assert pos_find_prof < pos_get_aluno, (
        "find_professor_por_telefone deve vir ANTES de get_aluno — "
        "ordem inversa rotaria professor pelo fluxo de aluno"
    )
    assert "_handle_professor_inbound" in src, (
        "perdeu chamada do handler de professor"
    )
