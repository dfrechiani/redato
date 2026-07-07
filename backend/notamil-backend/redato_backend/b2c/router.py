"""Desvio B2C do bot WhatsApp — FSM por telefone (SPEC §4 + ADENDO §1).

`maybe_route_b2c(msg)` é chamado no topo de `bot.handle_inbound`, logo
após o lookup de professor e ANTES de qualquer coisa do fluxo escola.
Retorna `None` (mensagem NÃO é B2C → fluxo escola intocado) ou uma lista
de respostas.

Fluxo do tema (ADENDO §D7): toda correção é contra um tema. A pendência
"aguardando tema" vive num ENVIO (`envios_b2c.status='aguardando_tema'`),
não no estado do aluno — assim degustação e assinante podem ambos ter
uma pendência sem perder o estado principal (paywall vs não).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
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
_RE_SIM = re.compile(r"^\s*(sim|confirmo|confirmar|isso|isso mesmo)\s*$", re.IGNORECASE)

_FILLER = {"QUERO", "QUER", "OI", "OLA", "OLÁ", "A", "O", "DA", "DO", "PROF"}

# Texto digitado com pelo menos este tamanho é tratado como redação.
_MIN_CHARS_REDACAO = 200
# Legenda com pelo menos isto é aceita como tema direto (§1.1).
_MIN_CHARS_TEMA = 15
# Atalho do tema sorteado (M16a) vale por esta janela.
_TEMA_ATALHO_HORAS = 48
# Sentinela guardada em envios_b2c.tema pra marcar "M16 pediu tema e a 1ª
# resposta veio curta" — a 2ª resposta curta é aceita como tema (§1.2).
_M17_SENTINEL = "\x00m17"

_TEMAS = [
    "Os desafios da democratização do acesso à leitura no Brasil",
    "Caminhos para combater a desinformação nas redes sociais",
    "O estigma associado às doenças mentais na sociedade brasileira",
    "A valorização das comunidades tradicionais e seus saberes",
    "Educação financeira como política pública no Brasil",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _out(text: str, branding: Optional[dict] = None):
    from redato_backend.whatsapp.bot import OutboundMessage
    return OutboundMessage(M.assinar(text, branding))


def _fmt_reais(centavos: int) -> str:
    return f"{centavos / 100:.2f}".replace(".", ",")


def _fmt_evolucao(notas: List[int]) -> str:
    if not notas:
        return "primeira correção"
    return " → ".join(str(n) for n in notas)


def _is_comando(text: str) -> bool:
    t = (text or "").strip()
    return bool(_RE_AJUDA.match(t) or _RE_EVOLUCAO.match(t)
                or _RE_TEMA.match(t) or _RE_CANCELAR.match(t))


# ──────────────────────────────────────────────────────────────────────
# CPF (validação real — só usada quando B2C_EXIGE_CPF=1)
# ──────────────────────────────────────────────────────────────────────

def _cpf_valido(cpf: str) -> Optional[str]:
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
# Extração do código de parceiro / checagem B2G
# ──────────────────────────────────────────────────────────────────────

def _extrair_parceiro(text: Optional[str]):
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
        # ADENDO §D9: bump da janela de 24h a cada mensagem recebida.
        repo.atualizar_aluno(phone, ultima_inbound_at=_now())
        aluno = repo.get_aluno_por_telefone(phone) or aluno
        return _dispatch(msg, aluno)

    if _tem_vinculo_b2g(phone) or _tem_estado_b2g(phone):
        return None

    parceiro = _extrair_parceiro(msg.text)
    if parceiro is not None:
        repo.criar_aluno(phone, parceiro.id, estado="aguardando_nome")
        repo.atualizar_aluno(phone, ultima_inbound_at=_now())
        return [_out(
            M.M1_BOAS_VINDAS.format(
                nome_publico=parceiro.nome_publico,
                nome_professor=parceiro.nome_professor,
                link_politica=config.politica_url(),
            ),
            parceiro.branding,
        )]

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
        return _handle_aguardando_pagamento(msg, aluno, parceiro)
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
    # Continuar após o aviso de LGPD = aceite (grava consentimento +
    # versão do texto — §D14).
    repo.atualizar_aluno(
        msg.phone, nome=nome, estado="degustacao",
        consent_lgpd_at=_now(), consent_version=config.CONSENT_VERSION,
    )
    return [_out(
        M.M2_CONVITE_GRATIS.format(nome=nome.split()[0]),
        parceiro.branding if parceiro else None,
    )]


# ──────────────────────────────────────────────────────────────────────
# Degustação e assinante ativo — ambos passam pelo fluxo do tema
# ──────────────────────────────────────────────────────────────────────

def _handle_degustacao(msg, aluno, parceiro) -> List:
    branding = parceiro.branding if parceiro else None
    pend = repo.get_envio_pendente(aluno.id)

    # Comando durante pendência → executa e mantém a pendência.
    if pend and msg.text and not msg.image_path and _is_comando(msg.text):
        return _handle_comando(msg, aluno, parceiro)

    # Resolução do tema pendente (texto que não é comando).
    if pend and msg.text and not msg.image_path:
        return _resolver_pendente(msg, aluno, parceiro, pend, is_degustacao=True)

    # Foto nova (substitui pendência anterior, se houver).
    if msg.image_path:
        return _fluxo_foto(msg, aluno, parceiro, gratis=True, is_degustacao=True)

    # Redação digitada sem tema → pede tema (M16).
    if msg.text and len(msg.text.strip()) >= _MIN_CHARS_REDACAO:
        return _fluxo_texto_redacao(msg, aluno, parceiro, gratis=True,
                                    is_degustacao=True)

    return [_out(
        M.M2_CONVITE_GRATIS.format(nome=_primeiro(aluno)),
        branding,
    )]


def _handle_ativo(msg, aluno, parceiro) -> List:
    branding = parceiro.branding if parceiro else None
    text = (msg.text or "").strip()
    pend = repo.get_envio_pendente(aluno.id)

    # Comandos (F8) — antes de tratar como redação/tema; mantêm pendência.
    if text and not msg.image_path and _is_comando(text):
        return _handle_comando(msg, aluno, parceiro)

    # Resolução do tema pendente.
    if pend and text and not msg.image_path:
        return _resolver_pendente(msg, aluno, parceiro, pend, is_degustacao=False)

    # Foto nova.
    if msg.image_path:
        # Fair use ANTES de gastar OCR/API.
        if _excede_fair_use(aluno):
            return [_out(M.M7_FAIR_USE.format(n=repo.contar_envios_hoje(aluno.id)),
                         branding)]
        return _fluxo_foto(msg, aluno, parceiro, gratis=False, is_degustacao=False)

    # Redação digitada.
    if text and len(text) >= _MIN_CHARS_REDACAO:
        if _excede_fair_use(aluno):
            return [_out(M.M7_FAIR_USE.format(n=repo.contar_envios_hoje(aluno.id)),
                         branding)]
        return _fluxo_texto_redacao(msg, aluno, parceiro, gratis=False,
                                    is_degustacao=False)

    return [_out(M.M15_FALLBACK, branding)]


def _excede_fair_use(aluno) -> bool:
    return repo.contar_envios_hoje(aluno.id) >= config.fair_use_dia()


def _handle_comando(msg, aluno, parceiro) -> List:
    branding = parceiro.branding if parceiro else None
    text = (msg.text or "").strip()
    if _RE_CANCELAR.match(text):
        repo.atualizar_aluno(msg.phone, estado="aguardando_cancelamento")
        return [_out(M.M11_CANCELAR.format(nome=_primeiro(aluno),
                                           fim_ciclo=_fim_ciclo_str(aluno)), branding)]
    if _RE_AJUDA.match(text):
        return [_out(M.M13_AJUDA, branding)]
    if _RE_EVOLUCAO.match(text):
        return [_out(_montar_evolucao(aluno), branding)]
    if _RE_TEMA.match(text):
        tema = _sortear_e_guardar_tema(aluno)
        return [_out(M.M14_TEMA.format(tema=tema), branding)]
    return [_out(M.M15_FALLBACK, branding)]


# ──────────────────────────────────────────────────────────────────────
# Fluxo do tema — foto → cascata → correção
# ──────────────────────────────────────────────────────────────────────

def _fluxo_foto(msg, aluno, parceiro, *, gratis, is_degustacao) -> List:
    branding = parceiro.branding if parceiro else None
    # OCR PRIMEIRO (§1.1): se ilegível, avisa já — não pede tema à toa.
    try:
        ocr = correction.transcrever(msg.image_path)
    except Exception:  # noqa: BLE001
        logger.exception("B2C: OCR falhou")
        return [_out(M.M_FOTO_ILEGIVEL, branding)]
    if getattr(ocr, "rejected", False):
        return [_out(M.M_FOTO_ILEGIVEL, branding)]
    texto = getattr(ocr, "text", "") or ""
    caption = (msg.text or "").strip()

    # Cascata de resolução do tema.
    if len(caption) >= _MIN_CHARS_TEMA:
        return _corrigir_e_entregar(msg, aluno, parceiro, texto=texto,
                                    tema=caption, gratis=gratis,
                                    is_degustacao=is_degustacao)

    if len(caption) >= 1:
        # Legenda dúbia (1–14) → M16b confirma.
        repo.substituir_envio_pendente(aluno.id, aluno.parceiro_id,
                                       texto_ocr=texto, gratis=gratis,
                                       tema=caption)
        return [_out(M.M16B_CONFIRMA_LEGENDA.format(caption=caption), branding)]

    # Sem legenda: atalho do tema sorteado (<48h)?
    if _tem_tema_sorteado_recente(aluno):
        repo.substituir_envio_pendente(aluno.id, aluno.parceiro_id,
                                       texto_ocr=texto, gratis=gratis,
                                       tema=aluno.ultimo_tema_sorteado)
        return [_out(M.M16A_ATALHO_SORTEADO.format(
            ultimo_tema=aluno.ultimo_tema_sorteado), branding)]

    # Sem legenda, sem atalho → pergunta o tema.
    repo.substituir_envio_pendente(aluno.id, aluno.parceiro_id,
                                   texto_ocr=texto, gratis=gratis, tema=None)
    return [_out(M.M16_PEDE_TEMA, branding)]


def _fluxo_texto_redacao(msg, aluno, parceiro, *, gratis, is_degustacao) -> List:
    """Redação digitada sem tema identificável → mesmo fluxo M16 (§1.2)."""
    branding = parceiro.branding if parceiro else None
    texto = msg.text.strip()
    repo.substituir_envio_pendente(aluno.id, aluno.parceiro_id,
                                   texto_ocr=texto, gratis=gratis, tema=None)
    return [_out(M.M16_PEDE_TEMA, branding)]


def _tem_tema_sorteado_recente(aluno) -> bool:
    if not aluno.ultimo_tema_sorteado or not aluno.ultimo_tema_sorteado_at:
        return False
    delta = _now() - aluno.ultimo_tema_sorteado_at
    return delta < timedelta(hours=_TEMA_ATALHO_HORAS)


def _resolver_pendente(msg, aluno, parceiro, pend, *, is_degustacao) -> List:
    """Texto que resolve o tema de um envio pendente (§1.2)."""
    branding = parceiro.branding if parceiro else None
    text = (msg.text or "").strip()
    candidato = pend.get("tema")  # None | caption/sorteado | sentinela

    if candidato and candidato != _M17_SENTINEL and _RE_SIM.match(text):
        tema = candidato
    elif candidato == _M17_SENTINEL:
        # 2ª resposta curta: aceita como tema assim mesmo.
        tema = text
    elif candidato:
        # M16a/M16b ofereceram atalho, aluno digitou tema diferente.
        tema = text
    elif len(text) >= _MIN_CHARS_TEMA:
        tema = text
    else:
        # M16 pediu tema e veio resposta curta sem atalho → M17 uma vez.
        repo.atualizar_tema_pendente(pend["id"], _M17_SENTINEL)
        return [_out(M.M17_ANTI_LOOP, branding)]

    return _corrigir_e_entregar(
        msg, aluno, parceiro, texto=pend["texto_ocr"], tema=tema,
        gratis=bool(pend.get("gratis")), is_degustacao=is_degustacao,
        envio_pendente_id=pend["id"],
    )


def _corrigir_e_entregar(msg, aluno, parceiro, *, texto, tema, gratis,
                         is_degustacao, envio_pendente_id=None) -> List:
    """Corrige `texto` contra `tema`, persiste e entrega M3 (degustação)
    ou M6 (assinante)."""
    branding = parceiro.branding if parceiro else None
    import time as _time
    t0 = _time.time()
    try:
        res = correction.corrigir_texto(texto, tema=tema)
    except Exception:  # noqa: BLE001
        logger.exception("B2C: correção falhou")
        return [_out(M.M_FOTO_ILEGIVEL, branding)]
    elapsed_ms = int((_time.time() - t0) * 1000)
    custo = correction.estimar_custo_correcao_centavos(texto)

    if envio_pendente_id:
        repo.corrigir_envio_pendente(
            envio_pendente_id, tema=tema, nota_total=res.nota_total,
            notas_competencias=res.notas, custo_estimado_centavos=custo,
            tempo_processamento_ms=elapsed_ms,
        )
    else:
        repo.registrar_envio(
            aluno.id, aluno.parceiro_id, texto_ocr=texto, texto_final=texto,
            tema=tema, nota_total=res.nota_total, notas_competencias=res.notas,
            gratis=gratis, custo_estimado_centavos=custo,
            tempo_processamento_ms=elapsed_ms, status="corrigido",
        )

    if is_degustacao:
        aluno2 = repo.incrementar_gratis(msg.phone) or aluno
        replies = [_out(M.M3_ENTREGA_DEGUSTACAO.format(
            tema=tema, nota_total=res.nota_total, **res.notas,
            ponto_forte=res.ponto_forte, foco_melhoria=res.foco_melhoria,
            nome_publico=parceiro.nome_publico if parceiro else "Redato",
        ), branding)]
        if aluno2.correcoes_gratis_usadas >= config.free_corrections():
            replies.extend(_ir_para_paywall(msg, aluno2, parceiro))
        return replies

    # Assinante: M6 com bloco de evolução condicional (≥2 corrigidos).
    texto_m6 = M.M6_BASE.format(
        tema=tema, nota_total=res.nota_total, **res.notas,
        ponto_forte=res.ponto_forte, foco_melhoria=res.foco_melhoria,
    )
    if repo.contar_corrigidos(aluno.id) >= 2:
        texto_m6 += M.M6_EVOLUCAO_LINE.format(
            ultimas_notas=_fmt_evolucao(repo.ultimas_notas(aluno.id)))
    texto_m6 += M.M6_FECHO
    return [_out(texto_m6, branding)]


# ──────────────────────────────────────────────────────────────────────
# Paywall / checkout (SPEC F2-F3)
# ──────────────────────────────────────────────────────────────────────

def _ir_para_paywall(msg, aluno, parceiro) -> List:
    branding = parceiro.branding if parceiro else None
    if config.exige_cpf() and not aluno.cpf:
        repo.atualizar_aluno(msg.phone, estado="aguardando_cpf")
        return [_out(M.M_PEDE_CPF, branding)]
    link = _criar_checkout(aluno, parceiro)
    repo.atualizar_aluno(msg.phone, estado="aguardando_pagamento")
    preco = parceiro.preco_centavos if parceiro else 3990
    return [_out(M.M4_PAYWALL.format(
        nome_publico=parceiro.nome_publico if parceiro else "Redato",
        preco=_fmt_reais(preco), link_checkout=link,
    ), branding)]


def _criar_checkout(aluno, parceiro) -> str:
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
        logger.exception("B2C: falha criando checkout Asaas para %s",
                         aluno.telefone_e164)
        return "https://wa.me/"
    repo.upsert_assinatura(
        aluno.id, valor_centavos=preco,
        asaas_customer_id=customer.get("id"),
        asaas_subscription_id=sub.get("id"), status="pendente",
    )
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
    return [_out(M.M4_PAYWALL.format(
        nome_publico=parceiro.nome_publico if parceiro else "Redato",
        preco=_fmt_reais(preco), link_checkout=link,
    ), branding)]


def _handle_aguardando_pagamento(msg, aluno, parceiro) -> List:
    """Ainda não pagou. Foto/redação NÃO é corrigida — reforça o paywall."""
    branding = parceiro.branding if parceiro else None
    sub = repo.get_assinatura_por_aluno(aluno.id)
    if sub is None or not sub.asaas_subscription_id:
        link = _criar_checkout(aluno, parceiro)
    else:
        link = f"https://sandbox.asaas.com/i/{sub.asaas_subscription_id}"
    preco = parceiro.preco_centavos if parceiro else 3990
    return [_out(M.M4_PAYWALL.format(
        nome_publico=parceiro.nome_publico if parceiro else "Redato",
        preco=_fmt_reais(preco), link_checkout=link,
    ), branding)]


def _handle_confirma_cancelamento(msg, aluno, parceiro) -> List:
    branding = parceiro.branding if parceiro else None
    text = (msg.text or "").strip()
    if not _RE_SIM.match(text):
        repo.atualizar_aluno(msg.phone, estado="ativo")
        return [_out(M.M13_AJUDA, branding)]
    sub = repo.get_assinatura_por_aluno(aluno.id)
    if sub and sub.asaas_subscription_id:
        try:
            from redato_backend.billing.asaas import get_asaas_client
            get_asaas_client().cancel_subscription(sub.asaas_subscription_id)
        except Exception:  # noqa: BLE001
            logger.exception("B2C: falha cancelando assinatura Asaas")
    repo.atualizar_aluno(msg.phone, estado="cancelado")
    return [_out(M.M11_CANCELAR.format(nome=_primeiro(aluno),
                                       fim_ciclo=_fim_ciclo_str(aluno)), branding)]


def _handle_inadimplente(msg, aluno, parceiro) -> List:
    """Recebe a redação, guarda SEM rodar OCR/grader, responde M10 (§D10)."""
    branding = parceiro.branding if parceiro else None
    sub = repo.get_assinatura_por_aluno(aluno.id)
    link = (
        f"https://sandbox.asaas.com/i/{sub.asaas_subscription_id}"
        if sub and sub.asaas_subscription_id else "https://wa.me/"
    )
    if msg.image_path or (msg.text and len(msg.text.strip()) >= _MIN_CHARS_REDACAO):
        repo.registrar_envio_bloqueado(aluno.id, aluno.parceiro_id)
    return [_out(M.M10_BLOQUEADO.format(link_fatura=link), branding)]


# ──────────────────────────────────────────────────────────────────────
# Helpers de evolução / tema
# ──────────────────────────────────────────────────────────────────────

def _primeiro(aluno) -> str:
    return (aluno.nome or "").split(" ")[0] or "aluno(a)"


def _fim_ciclo_str(aluno) -> str:
    sub = repo.get_assinatura_por_aluno(aluno.id)
    if sub and sub.proximo_vencimento:
        return sub.proximo_vencimento.astimezone(timezone.utc).strftime("%d/%m/%Y")
    return "o fim do ciclo pago"


def _sortear_e_guardar_tema(aluno) -> str:
    # Rotação determinística (sem aleatoriedade) + persiste pro atalho M16a.
    idx = repo.contar_corrigidos(aluno.id) % len(_TEMAS)
    tema = _TEMAS[idx]
    repo.atualizar_aluno(aluno.telefone_e164, ultimo_tema_sorteado=tema,
                         ultimo_tema_sorteado_at=_now())
    return tema


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
