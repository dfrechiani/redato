"""Desvio B2C do bot WhatsApp — FSM por telefone (SPEC_B2C_REDATO.md §4).

`maybe_route_b2c(msg)` é chamado no topo de `bot.handle_inbound`, logo
após o lookup de professor e ANTES de qualquer coisa do fluxo escola.
Retorna:
- `None`  → a mensagem NÃO é B2C; o fluxo escola (B2G) segue intocado.
- `list` → a mensagem é B2C; o bot devolve estas respostas.

Regra de captura (regressão zero pro B2G):
1. flag REDATO_B2C_ENABLED off → retorna None sempre.
2. telefone já é AlunoB2C → segue a FSM dele.
3. telefone desconhecido ao B2C: só captura se também é desconhecido ao
   B2G (sem vínculo de turma E sem estado no SQLite do bot) E a mensagem
   traz um código de parceiro válido. Caso contrário devolve None.

Assim, aluno de escola (mesmo em onboarding) nunca é sequestrado pelo
B2C, e com a flag off o bloco inteiro é pulado.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import List, Optional

from redato_backend.b2c import config, correction
from redato_backend.b2c import messages as M
from redato_backend.b2c import repo


logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Regexes de comando (F8) + consentimento
# ──────────────────────────────────────────────────────────────────────

_RE_EVOLUCAO = re.compile(r"^\s*(evolu[çc][ãa]o|hist[óo]rico)\s*$", re.IGNORECASE)
_RE_AJUDA = re.compile(r"^\s*(ajuda|help|comandos)\s*$", re.IGNORECASE)
_RE_TEMA = re.compile(r"^\s*(tema|proposta)\s*$", re.IGNORECASE)
_RE_CANCELAR = re.compile(r"^\s*(cancelar|cancelamento)\s*$", re.IGNORECASE)
_RE_SIM = re.compile(r"^\s*(sim|confirmo|confirmar)\s*$", re.IGNORECASE)

# Palavras de saudação a ignorar ao procurar o código do parceiro no
# texto do deep link ("QUERO LUMA", "quero a LUMA", ...).
_FILLER = {"QUERO", "QUER", "OI", "OLA", "OLÁ", "A", "O", "DA", "DO", "PROF"}

# Texto digitado com pelo menos este tamanho é tratado como redação
# (F4: assinante pode mandar texto em vez de foto).
_MIN_CHARS_REDACAO = 200

# Banco simples de temas de treino (F8 "tema"). Reutilizável; sem
# dependência externa no MVP.
_TEMAS = [
    "Os desafios da democratização do acesso à leitura no Brasil",
    "Caminhos para combater a desinformação nas redes sociais",
    "O estigma associado às doenças mentais na sociedade brasileira",
    "A valorização das comunidades tradicionais e seus saberes",
    "Educação financeira como política pública no Brasil",
]


def _out(text: str, branding: Optional[dict] = None):
    from redato_backend.whatsapp.bot import OutboundMessage
    return OutboundMessage(M.assinar(text, branding))


def _fmt_reais(centavos: int) -> str:
    return f"{centavos / 100:.2f}".replace(".", ",")


def _fmt_evolucao(notas: List[int]) -> str:
    if not notas:
        return "primeira correção"
    return " → ".join(str(n) for n in notas)


# ──────────────────────────────────────────────────────────────────────
# CPF (validação real — só usada quando B2C_EXIGE_CPF=1)
# ──────────────────────────────────────────────────────────────────────

def _cpf_valido(cpf: str) -> Optional[str]:
    """Retorna o CPF só-dígitos se válido (DV correto), senão None."""
    d = re.sub(r"\D", "", cpf or "")
    if len(d) != 11 or d == d[0] * 11:
        return None
    for i in (9, 10):
        soma = sum(int(d[j]) * ((i + 1) - j) for j in range(i))
        dv = (soma * 10) % 11
        dv = 0 if dv == 10 else dv
        if dv != int(d[i]):
            return None
    return d


# ──────────────────────────────────────────────────────────────────────
# Extração do código de parceiro
# ──────────────────────────────────────────────────────────────────────

def _extrair_parceiro(text: Optional[str]):
    """Procura no texto um token que case com o codigo_entrada de algum
    parceiro ativo. Retorna ParceiroDTO ou None."""
    if not text:
        return None
    tokens = [t for t in re.split(r"[^0-9A-Za-zÀ-ÿ]+", text.upper()) if len(t) >= 2]
    for tok in tokens:
        if tok in _FILLER:
            continue
        p = repo.get_parceiro_por_codigo(tok)
        if p is not None:
            return p
    return None


def _tem_vinculo_b2g(phone: str) -> bool:
    try:
        from redato_backend.whatsapp import portal_link as PL
        return bool(PL.list_alunos_ativos_por_telefone(phone))
    except Exception:  # noqa: BLE001
        logger.exception("B2C: falha checando vínculo B2G; assume sem vínculo")
        return False


def _tem_estado_b2g(phone: str) -> bool:
    """Telefone já tem estado no SQLite do bot (onboarding de escola em
    curso). Se sim, NÃO capturamos pro B2C."""
    try:
        from redato_backend.whatsapp import persistence as P
        return P.get_aluno(phone) is not None
    except Exception:  # noqa: BLE001
        logger.exception("B2C: falha checando estado B2G; assume sem estado")
        return False


# ──────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────

def maybe_route_b2c(msg) -> Optional[List]:
    if not config.b2c_enabled():
        return None

    phone = msg.phone
    aluno = repo.get_aluno_por_telefone(phone)
    if aluno is not None:
        return _dispatch(msg, aluno)

    # Desconhecido ao B2C. Só captura se também for desconhecido ao B2G.
    if _tem_vinculo_b2g(phone) or _tem_estado_b2g(phone):
        return None

    parceiro = _extrair_parceiro(msg.text)
    if parceiro is not None:
        repo.criar_aluno(phone, parceiro.id, estado="aguardando_nome")
        return [_out(
            M.M1_BOAS_VINDAS.format(
                nome_publico=parceiro.nome_publico,
                nome_professor=parceiro.nome_professor,
                link_politica=config.politica_url(),
            ),
            parceiro.branding,
        )]

    # Sem código. Só respondemos M0 numa linha dedicada B2C
    # (B2C_LINHA_DEDICADA=1). Numa linha COMPARTILHADA com a escola,
    # devolvemos None pra não atropelar o onboarding B2G.
    if config._flag("B2C_LINHA_DEDICADA", default=False):
        return [_out(M.M0_SEM_CODIGO)]
    return None


# ──────────────────────────────────────────────────────────────────────
# Dispatch por estado
# ──────────────────────────────────────────────────────────────────────

def _dispatch(msg, aluno) -> List:
    parceiro = repo.get_parceiro_por_id(aluno.parceiro_id)
    branding = parceiro.branding if parceiro else None
    estado = aluno.estado

    if estado == "aguardando_nome":
        return _handle_nome(msg, aluno, parceiro)
    if estado == "aguardando_cpf":
        return _handle_cpf(msg, aluno, parceiro)
    if estado == "degustacao":
        return _handle_degustacao(msg, aluno, parceiro)
    if estado == "aguardando_pagamento":
        return _handle_aguardando_pagamento(msg, aluno, parceiro)
    if estado == "ativo":
        return _handle_ativo(msg, aluno, parceiro)
    if estado == "aguardando_cancelamento":
        return _handle_confirma_cancelamento(msg, aluno, parceiro)
    if estado in ("inadimplente", "bloqueado"):
        return _handle_inadimplente(msg, aluno, parceiro)
    if estado == "cancelado":
        # Reengajamento simples: trata como quem vai (re)assinar.
        return _handle_aguardando_pagamento(msg, aluno, parceiro)
    # 'novo' ou estado inesperado — reenvia boas-vindas pedindo nome.
    return [_out(
        M.M1_BOAS_VINDAS.format(
            nome_publico=parceiro.nome_publico if parceiro else "Redato",
            nome_professor=parceiro.nome_professor if parceiro else "",
            link_politica=config.politica_url(),
        ),
        branding,
    )]


def _handle_nome(msg, aluno, parceiro) -> List:
    nome = (msg.text or "").strip()
    if len(nome) < 2:
        return [_out(
            "Como você se chama? Me manda seu primeiro nome.",
            parceiro.branding if parceiro else None,
        )]
    # Continuar após o aviso de LGPD = aceite (gravamos o consentimento).
    repo.atualizar_aluno(
        msg.phone, nome=nome, estado="degustacao",
        consent_lgpd_at=datetime.now(timezone.utc),
    )
    return [_out(
        M.M2_CONVITE_GRATIS.format(nome=nome.split()[0]),
        parceiro.branding if parceiro else None,
    )]


def _handle_degustacao(msg, aluno, parceiro) -> List:
    res, err, texto = _corrigir_entrada(msg)
    if err:
        return [_out(err, parceiro.branding if parceiro else None)]
    if res is None:
        return [_out(
            M.M2_CONVITE_GRATIS.format(nome=(aluno.nome or "").split(" ")[0] or "aluno(a)"),
            parceiro.branding if parceiro else None,
        )]

    branding = parceiro.branding if parceiro else None
    repo.registrar_envio(
        aluno.id, aluno.parceiro_id,
        texto_ocr=texto, texto_final=texto,
        nota_total=res.nota_total, notas_competencias=res.notas,
        gratis=True, tempo_processamento_ms=None,
    )
    aluno = repo.incrementar_gratis(msg.phone) or aluno

    replies = [_out(
        M.M3_ENTREGA_DEGUSTACAO.format(
            nota_total=res.nota_total, **res.notas,
            ponto_forte=res.ponto_forte, foco_melhoria=res.foco_melhoria,
            nome_publico=parceiro.nome_publico if parceiro else "Redato",
        ),
        branding,
    )]

    # Esgotou a degustação → paywall (F2).
    if aluno.correcoes_gratis_usadas >= config.free_corrections():
        replies.extend(_ir_para_paywall(msg, aluno, parceiro))
    return replies


def _ir_para_paywall(msg, aluno, parceiro) -> List:
    """Emite o paywall M4 com link real de checkout, ou pede CPF antes
    (F3, quando B2C_EXIGE_CPF=1). Move o estado adequadamente."""
    branding = parceiro.branding if parceiro else None
    if config.exige_cpf() and not aluno.cpf:
        repo.atualizar_aluno(msg.phone, estado="aguardando_cpf")
        return [_out(M.M_PEDE_CPF, branding)]

    link = _criar_checkout(aluno, parceiro)
    repo.atualizar_aluno(msg.phone, estado="aguardando_pagamento")
    preco = parceiro.preco_centavos if parceiro else 3990
    return [_out(
        M.M4_PAYWALL.format(
            nome_publico=parceiro.nome_publico if parceiro else "Redato",
            preco=_fmt_reais(preco), link_checkout=link,
        ),
        branding,
    )]


def _criar_checkout(aluno, parceiro) -> str:
    """Cria customer + subscription (com split) no gateway e persiste a
    assinatura pendente. Retorna o invoiceUrl."""
    from redato_backend.billing.asaas import get_asaas_client
    client = get_asaas_client()
    preco = parceiro.preco_centavos if parceiro else 3990
    try:
        customer = client.create_customer(aluno.nome or "Aluno", cpf=aluno.cpf)
        sub = client.create_subscription(
            customer_id=customer["id"], valor_centavos=preco,
            wallet_id=parceiro.wallet_id_asaas if parceiro else None,
            share_pct=parceiro.share_pct if parceiro else None,
        )
    except Exception:  # noqa: BLE001
        logger.exception("B2C: falha criando checkout Asaas para %s", aluno.telefone_e164)
        return "https://wa.me/"  # link inócuo; aluno pode tentar de novo
    repo.upsert_assinatura(
        aluno.id, valor_centavos=preco,
        asaas_customer_id=customer.get("id"),
        asaas_subscription_id=sub.get("id"),
        status="pendente",
    )
    # CPF já cumpriu seu papel (emissão) — não guardamos além do necessário.
    if aluno.cpf:
        repo.atualizar_aluno(aluno.telefone_e164, cpf=None)
    return sub.get("invoiceUrl") or "https://wa.me/"


def _handle_cpf(msg, aluno, parceiro) -> List:
    branding = parceiro.branding if parceiro else None
    cpf = _cpf_valido(msg.text or "")
    if cpf is None:
        return [_out(M.M_CPF_INVALIDO, branding)]
    repo.atualizar_aluno(msg.phone, cpf=cpf)
    aluno = repo.get_aluno_por_telefone(msg.phone) or aluno
    link = _criar_checkout(aluno, parceiro)
    repo.atualizar_aluno(msg.phone, estado="aguardando_pagamento")
    preco = parceiro.preco_centavos if parceiro else 3990
    return [_out(
        M.M4_PAYWALL.format(
            nome_publico=parceiro.nome_publico if parceiro else "Redato",
            preco=_fmt_reais(preco), link_checkout=link,
        ),
        branding,
    )]


def _handle_aguardando_pagamento(msg, aluno, parceiro) -> List:
    """Ainda não pagou. Foto/redação NÃO é corrigida — reforça o paywall
    (critério #3: 2ª foto sem pagar → M4)."""
    branding = parceiro.branding if parceiro else None
    sub = repo.get_assinatura_por_aluno(aluno.id)
    link = None
    if sub is None or not sub.asaas_subscription_id:
        link = _criar_checkout(aluno, parceiro)
    else:
        link = f"https://sandbox.asaas.com/i/{sub.asaas_subscription_id}"
    preco = parceiro.preco_centavos if parceiro else 3990
    return [_out(
        M.M4_PAYWALL.format(
            nome_publico=parceiro.nome_publico if parceiro else "Redato",
            preco=_fmt_reais(preco), link_checkout=link,
        ),
        branding,
    )]


def _handle_ativo(msg, aluno, parceiro) -> List:
    branding = parceiro.branding if parceiro else None
    text = (msg.text or "").strip()

    # Comandos (F8) — antes de tratar como redação.
    if text and not msg.image_path:
        if _RE_CANCELAR.match(text):
            repo.atualizar_aluno(msg.phone, estado="aguardando_cancelamento")
            fim = _fim_ciclo_str(aluno)
            return [_out(M.M11_CANCELAR.format(nome=_primeiro(aluno), fim_ciclo=fim), branding)]
        if _RE_AJUDA.match(text):
            return [_out(M.M13_AJUDA, branding)]
        if _RE_EVOLUCAO.match(text):
            return [_out(_montar_evolucao(aluno), branding)]
        if _RE_TEMA.match(text):
            tema = _sortear_tema(aluno)
            return [_out(M.M14_TEMA.format(tema=tema), branding)]

    # Fair use (F5): conta correções do dia ANTES de gastar API.
    hoje = repo.contar_envios_hoje(aluno.id)
    if hoje >= config.fair_use_dia():
        return [_out(M.M7_FAIR_USE.format(n=hoje), branding)]

    res, err, texto = _corrigir_entrada(msg)
    if err:
        return [_out(err, branding)]
    if res is None:
        return [_out(M.M15_FALLBACK, branding)]

    repo.registrar_envio(
        aluno.id, aluno.parceiro_id,
        texto_ocr=texto, texto_final=texto,
        nota_total=res.nota_total, notas_competencias=res.notas,
        gratis=False,
    )
    evol = _fmt_evolucao(repo.ultimas_notas(aluno.id))
    return [_out(
        M.M6_ENTREGA_ASSINANTE.format(
            nota_total=res.nota_total, **res.notas,
            ponto_forte=res.ponto_forte, foco_melhoria=res.foco_melhoria,
            ultimas_notas=evol,
        ),
        branding,
    )]


def _handle_confirma_cancelamento(msg, aluno, parceiro) -> List:
    branding = parceiro.branding if parceiro else None
    text = (msg.text or "").strip()
    if not _RE_SIM.match(text):
        # Qualquer coisa que não seja SIM: volta pra ativo (desiste).
        repo.atualizar_aluno(msg.phone, estado="ativo")
        return [_out(M.M13_AJUDA, branding)]
    sub = repo.get_assinatura_por_aluno(aluno.id)
    if sub and sub.asaas_subscription_id:
        try:
            from redato_backend.billing.asaas import get_asaas_client
            get_asaas_client().cancel_subscription(sub.asaas_subscription_id)
        except Exception:  # noqa: BLE001
            logger.exception("B2C: falha cancelando assinatura Asaas")
    # Mantém acesso até o fim do ciclo pago; marca cancelamento agendado.
    repo.atualizar_aluno(msg.phone, estado="cancelado")
    fim = _fim_ciclo_str(aluno)
    return [_out(M.M11_CANCELAR.format(nome=_primeiro(aluno), fim_ciclo=fim), branding)]


def _handle_inadimplente(msg, aluno, parceiro) -> List:
    """Recebe a redação, guarda, mas NÃO corrige (F6 D+5)."""
    branding = parceiro.branding if parceiro else None
    sub = repo.get_assinatura_por_aluno(aluno.id)
    link = (
        f"https://sandbox.asaas.com/i/{sub.asaas_subscription_id}"
        if sub and sub.asaas_subscription_id else "https://wa.me/"
    )
    if msg.image_path or (msg.text and len(msg.text.strip()) >= _MIN_CHARS_REDACAO):
        # Guarda a redação pra corrigir depois da regularização.
        texto = None
        if msg.image_path:
            try:
                ocr = correction.transcrever(msg.image_path)
                texto = getattr(ocr, "text", None)
            except Exception:  # noqa: BLE001
                logger.exception("B2C: OCR falhou no estado inadimplente")
        else:
            texto = msg.text
        repo.registrar_envio(
            aluno.id, aluno.parceiro_id, texto_ocr=texto, texto_final=texto,
        )
    return [_out(M.M10_BLOQUEADO.format(link_fatura=link), branding)]


# ──────────────────────────────────────────────────────────────────────
# Helpers de correção / evolução / tema
# ──────────────────────────────────────────────────────────────────────

def _corrigir_entrada(msg):
    """Resolve a entrada (foto ou texto) numa correção.

    Retorna (ResultadoCorrecao|None, erro_msg|None, texto|None):
    - (res, None, texto) : corrigiu
    - (None, msg_erro, None) : erro amigável (foto ilegível)
    - (None, None, None) : nada corrigível (não é foto nem redação)
    """
    if msg.image_path:
        try:
            ocr = correction.transcrever(msg.image_path)
        except Exception:  # noqa: BLE001
            logger.exception("B2C: OCR falhou")
            return None, M.M_FOTO_ILEGIVEL, None
        if getattr(ocr, "rejected", False):
            return None, M.M_FOTO_ILEGIVEL, None
        texto = getattr(ocr, "text", "") or ""
    elif msg.text and len(msg.text.strip()) >= _MIN_CHARS_REDACAO:
        texto = msg.text.strip()
    else:
        return None, None, None

    try:
        res = correction.corrigir_texto(texto)
    except Exception:  # noqa: BLE001
        logger.exception("B2C: correção falhou")
        return None, M.M_FOTO_ILEGIVEL, None
    return res, None, texto


def _primeiro(aluno) -> str:
    return (aluno.nome or "").split(" ")[0] or "aluno(a)"


def _fim_ciclo_str(aluno) -> str:
    sub = repo.get_assinatura_por_aluno(aluno.id)
    if sub and sub.proximo_vencimento:
        return sub.proximo_vencimento.astimezone(timezone.utc).strftime("%d/%m/%Y")
    return "o fim do ciclo pago"


def _sortear_tema(aluno) -> str:
    # Sem aleatoriedade não-determinística: rotaciona pelo nº de envios.
    idx = repo.contar_envios_hoje(aluno.id) % len(_TEMAS)
    return _TEMAS[idx]


def _montar_evolucao(aluno) -> str:
    notas = repo.ultimas_notas(aluno.id, limite=5)
    hist = repo.listar_notas_competencias(aluno.id)
    medias = {c: 0 for c in ("c1", "c2", "c3", "c4", "c5")}
    if hist:
        for c in medias:
            vals = [int(h.get(c, 0) or 0) for h in hist if h.get(c) is not None]
            medias[c] = round(sum(vals) / len(vals)) if vals else 0
    pior = min(medias, key=lambda k: medias[k]) if hist else "c5"
    medias_str = " · ".join(f"{c.upper()} {medias[c]}" for c in medias)
    return M.M12_EVOLUCAO.format(
        lista=_fmt_evolucao(notas), medias=medias_str, pior_comp=pior.upper(),
    )
