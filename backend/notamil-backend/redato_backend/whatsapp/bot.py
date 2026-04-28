"""Bot FSM por phone — identificação de aluno + missão + dispatch.

Estados (M4):
- NEW                 : sem registro, vai pedir código de turma
- AWAITING_CODIGO_TURMA : esperando TURMA-XXXXX-1A-2026
- AWAITING_NOME_ALUNO|<turma_id> : código OK, esperando nome
- READY               : cadastrado em pelo menos 1 turma, aguardando
                        missão ou foto
- AWAITING_FOTO|<missao>     : missão informada, esperando foto
- AWAITING_CODIGO|<foto>     : foto recebida, esperando código
- AWAITING_DUP|<id>|<missao>|<foto> : foto duplicada, esperando 1/2

Estados legados (descontinuados — não usados pós-M4):
- AWAITING_NOME, AWAITING_TURMA — fluxo livre da Fase A. Mantidos no
  código pra compatibilidade com testes antigos, mas handle_inbound
  os ignora e migra pra AWAITING_CODIGO_TURMA na próxima mensagem.

M4 mudança principal: bot recusa foto de aluno não vinculado a uma
turma E recusa foto se não há atividade ativa pra (turma, missão).
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from redato_backend.whatsapp import persistence as P
from redato_backend.whatsapp.ocr import (
    transcribe_with_quality_check,
    quality_issues_to_message,
)
from redato_backend.whatsapp.render import render_aluno_whatsapp


BACKEND = Path(__file__).resolve().parents[2]


# ──────────────────────────────────────────────────────────────────────
# Estados (constantes)
# ──────────────────────────────────────────────────────────────────────

NEW = "NEW"
# M4: cadastro novo via código de turma
AWAITING_CODIGO_TURMA = "AWAITING_CODIGO_TURMA"
AWAITING_NOME_ALUNO = "AWAITING_NOME_ALUNO"  # encoded: AWAITING_NOME_ALUNO|<turma_id>
# Estados pós-cadastro
READY = "READY"
AWAITING_FOTO = "AWAITING_FOTO"               # missão recebida, esperando foto
AWAITING_CODIGO = "AWAITING_CODIGO"           # foto recebida, esperando código
AWAITING_DUPLICATE_CHOICE = "AWAITING_DUP"    # foto duplicada — esperando 1/2
AWAITING_TURMA_CHOICE = "AWAITING_TURMA_CHOICE"  # aluno em múltiplas turmas
# Estados legados (Fase A) — descontinuados pós-M4, preservados pra
# não quebrar testes existentes que ainda referenciam constantes.
AWAITING_NOME = "AWAITING_NOME"
AWAITING_TURMA = "AWAITING_TURMA"


# ──────────────────────────────────────────────────────────────────────
# Mensagens-template
# ──────────────────────────────────────────────────────────────────────

MSG_BOAS_VINDAS = (
    "Olá! Eu sou a *Redato*, sua corretora de redação do programa "
    "Redação em Jogo. Antes de começar, preciso saber quem você é.\n\n"
    "Me manda seu *nome completo*."
)

MSG_PEDE_TURMA = (
    "Prazer, {nome}. Agora me diz sua *turma* e *escola* numa mensagem só.\n\n"
    "Exemplo: _1A — Colégio Estadual Rui Barbosa_"
)

MSG_CADASTRADO = (
    "Beleza, {nome}! Cadastro feito.\n\n"
    "Pra eu corrigir uma redação, manda a *foto da página do livro* + "
    "o *número da missão* (10, 11, 12, 13 ou 14). Pode mandar tudo na "
    "mesma mensagem ou em mensagens separadas."
)

MSG_FALTA_MISSAO = (
    "Recebi a foto, mas não sei qual missão é. Me manda o número da "
    "missão: *10*, *11*, *12*, *13* ou *14*."
)

MSG_FALTA_FOTO = (
    "Anotei: missão *{missao}*. Agora manda a foto da redação."
)

MSG_MISSAO_INVALIDA = (
    "Não reconheci esse código. Manda só o número da missão: "
    "*10*, *11*, *12*, *13* ou *14*."
)

MSG_PROCESSANDO = (
    "Recebi sua redação da missão *{missao}*. Tô lendo agora — me dá "
    "alguns segundos."
)

MSG_ERRO_GENERICO = (
    "Algo deu errado na correção. Pode tentar de novo? Se persistir, "
    "fala com seu professor."
)

MSG_DUPLICATE_PROMPT = (
    "Recebi essa mesma redação em {data}. O que você quer?\n\n"
    "1\ufe0f\u20e3 Reenviar o feedback que já te dei\n"
    "2\ufe0f\u20e3 Reavaliar como nova tentativa (a IA pode dar outra nota)\n\n"
    "Responde *1* ou *2*."
)

MSG_DUPLICATE_INVALID_CHOICE = (
    "Não entendi. Responde só *1* (reenviar feedback antigo) ou *2* "
    "(reavaliar como nova tentativa)."
)

MSG_OCR_ERRADO_CONFIRMADO = (
    "Ok, vou descartar a última correção. Manda a foto de novo. "
    "Procure boa luz e foto sem inclinação."
)

MSG_OCR_ERRADO_SEM_HISTORICO = (
    "Não tenho correção recente sua pra descartar. Se a Redato leu "
    "errado depois de avaliar, manda a foto de novo com o código da "
    "missão."
)


# ──────────────────────────────────────────────────────────────────────
# Activity ID parsing
# ──────────────────────────────────────────────────────────────────────

# Formato canônico: RJ1OF10MF com variações de separador
_MISSAO_RE_FULL = re.compile(
    r"RJ\d+\s*[\W_]*\s*OF\s*\d{2}\s*[\W_]*\s*MF",
    re.IGNORECASE,
)
# Autocorretor iPhone troca "1OF10" por "10F10" (O → 0)
_MISSAO_RE_AUTOCORRECT = re.compile(
    r"RJ(\d)0F(\d{2})\s*[\W_]*\s*MF",
    re.IGNORECASE,
)
# Forma curta com OF: "OF10", "of 10", "of12"
_MISSAO_RE_OF = re.compile(r"\bOF\s*(\d{2})\b", re.IGNORECASE)
# Forma curta com M: "M1", "m 2", "m5"
_MISSAO_RE_M = re.compile(r"\bM\s*([1-5])\b", re.IGNORECASE)
# Número puro como única coisa na mensagem: "10", " 11 "
_MISSAO_RE_NUM_ONLY = re.compile(r"^\s*(10|11|12|13|14)\s*$")

# OF válidos (extensão futura: OF20+ pra Livro 2S)
_VALID_OF_NUMBERS = {"10", "11", "12", "13", "14"}
# M ↔ OF: M1=OF10, M2=OF11, ..., M5=OF14
_M_TO_OF = {"1": "10", "2": "11", "3": "12", "4": "13", "5": "14"}


def _extract_missao(text: str) -> Optional[str]:
    """Pega o código da missão em qualquer formato aceito.

    Aceita (case-insensitive, com ou sem pontuação):
    - RJ1OF10MF, RJ1·OF10·MF, rj1.of10.mf, ...
    - RJ10F10MF (autocorretor iPhone trocou O por 0)
    - OF10, of10
    - M1, M2, M3, M4, M5
    - 10, 11, 12, 13, 14 (apenas se for o conteúdo inteiro da mensagem)

    Retorna formato canônico RJ1·OF10·MF, ou None se não reconhecer.
    """
    if not text:
        return None

    # 1. Forma completa RJ\d+OF\d{2}MF
    m = _MISSAO_RE_FULL.search(text)
    if m:
        digits = re.findall(r"\d+", m.group(0))
        if len(digits) >= 2 and digits[1] in _VALID_OF_NUMBERS:
            return f"RJ{digits[0]}·OF{digits[1]}·MF"

    # 2. Autocorretor iPhone: RJ\d0F\d{2}MF
    m = _MISSAO_RE_AUTOCORRECT.search(text)
    if m:
        of_nn = m.group(2)
        if of_nn in _VALID_OF_NUMBERS:
            return f"RJ{m.group(1)}·OF{of_nn}·MF"

    # 3. Forma curta OF<nn>
    m = _MISSAO_RE_OF.search(text)
    if m:
        of_nn = m.group(1)
        if of_nn in _VALID_OF_NUMBERS:
            return f"RJ1·OF{of_nn}·MF"

    # 4. Forma curta M<n>
    m = _MISSAO_RE_M.search(text)
    if m:
        m_n = m.group(1)
        of_nn = _M_TO_OF.get(m_n)
        if of_nn:
            return f"RJ1·OF{of_nn}·MF"

    # 5. Número puro (apenas se for o conteúdo único da mensagem,
    #    pra evitar pegar "10 anos" numa frase qualquer)
    m = _MISSAO_RE_NUM_ONLY.match(text)
    if m:
        of_nn = m.group(1)
        return f"RJ1·OF{of_nn}·MF"

    return None


def _is_valid_missao(canon: str) -> bool:
    """O canon já vem validado por _extract_missao. Função mantida pra
    compatibilidade com chamadas antigas; sempre True se o canon é
    daqueles produzidos por _extract_missao."""
    return any(f"OF{n}" in canon for n in _VALID_OF_NUMBERS)


# ──────────────────────────────────────────────────────────────────────
# Inbound message handler — entry point
# ──────────────────────────────────────────────────────────────────────

@dataclass
class InboundMessage:
    """Representação agnóstica de uma mensagem WhatsApp recebida.

    Provedor (Twilio, Meta) traduz seu webhook neste shape antes de
    chamar handle_inbound.
    """
    phone: str                              # E.164 ou identificador estável
    text: Optional[str] = None              # caption ou texto puro
    image_path: Optional[str] = None        # path local; None se só texto


@dataclass
class OutboundMessage:
    """Resposta a enviar de volta. Lista pra suportar múltiplas (ex.: ack
    + resultado)."""
    text: str


def handle_inbound(msg: InboundMessage) -> List[OutboundMessage]:
    """Processa uma mensagem recebida. Retorna 0 ou mais respostas.

    Fluxo M4:
    1. NEW ou estado legado → AWAITING_CODIGO_TURMA + msg de boas-vindas
    2. AWAITING_CODIGO_TURMA → tenta extrair código + valida + pede nome
    3. AWAITING_NOME_ALUNO|<turma_id> → cria AlunoTurma + READY
    4. AWAITING_TURMA_CHOICE|... → aluno escolhe turma quando em múltiplas
    5. READY/AWAITING_FOTO/AWAITING_CODIGO → fluxo de envio com
       validação de atividade ativa
    """
    from redato_backend.whatsapp import messages as MSG
    from redato_backend.whatsapp import portal_link as PL

    P.init_db()
    aluno = P.get_aluno(msg.phone)

    # Caso 1: usuário novo
    if aluno is None:
        P.upsert_aluno(msg.phone, estado=AWAITING_CODIGO_TURMA)
        return [OutboundMessage(MSG.MSG_BEM_VINDO_NOVO_ALUNO)]

    estado = aluno["estado"]

    # Comando especial "ocr errado" — pode chegar em qualquer estado pós-avaliação
    if msg.text and _is_ocr_errado(msg.text):
        return _handle_ocr_errado(msg, aluno)

    # Caso especial: aguardando decisão de duplicata (1=reusar, 2=reavaliar)
    if estado.startswith(AWAITING_DUPLICATE_CHOICE + "|"):
        return _handle_duplicate_choice(msg, aluno)

    # Caso especial: aguardando escolha de turma (aluno em múltiplas)
    if estado.startswith(AWAITING_TURMA_CHOICE + "|"):
        return _handle_turma_choice(msg, aluno)

    # M4: estados legados de Fase A são reciclados pra fluxo novo
    if estado in (AWAITING_NOME, AWAITING_TURMA):
        P.upsert_aluno(msg.phone, estado=AWAITING_CODIGO_TURMA)
        return [OutboundMessage(MSG.MSG_BEM_VINDO_NOVO_ALUNO)]

    # Caso 2: aguardando código de turma
    if estado == AWAITING_CODIGO_TURMA:
        return _handle_codigo_turma(msg, aluno)

    # Caso 3: código aceito, aguardando nome do aluno
    if estado.startswith(AWAITING_NOME_ALUNO + "|"):
        return _handle_nome_aluno(msg, aluno)

    # M4: aluno em READY que manda novo código de turma — pode estar
    # tentando se cadastrar de novo na mesma turma OU se vincular a
    # uma turma adicional. Tratar antes do fluxo de foto.
    if estado == READY and msg.text:
        codigo_turma = PL.extract_codigo_turma(msg.text)
        if codigo_turma:
            return _handle_codigo_turma(msg, aluno)

    # Caso 4: READY ou AWAITING_FOTO — fluxo principal
    return _handle_ready_or_awaiting(msg, aluno)


def _handle_codigo_turma(
    msg: InboundMessage, aluno: Dict[str, Any],
) -> List[OutboundMessage]:
    from redato_backend.whatsapp import messages as MSG
    from redato_backend.whatsapp import portal_link as PL

    text = (msg.text or "").strip()
    codigo = PL.extract_codigo_turma(text)
    if codigo is None:
        return [OutboundMessage(MSG.MSG_CODIGO_TURMA_INVALIDO)]

    info = PL.find_turma_por_codigo_join(codigo)
    if info is None:
        return [OutboundMessage(MSG.MSG_CODIGO_TURMA_INVALIDO)]
    if not info.ativa:
        return [OutboundMessage(MSG.MSG_TURMA_INATIVA)]

    # Já estava cadastrado nesta turma?
    existing_vinculos = PL.list_alunos_ativos_por_telefone(msg.phone)
    for v in existing_vinculos:
        if v.turma_id == info.turma_id:
            P.upsert_aluno(msg.phone, estado=READY)
            return [OutboundMessage(
                MSG.MSG_JA_CADASTRADO_NESSA_TURMA.format(nome=v.nome)
            )]

    # Estado encoded: AWAITING_NOME_ALUNO|<turma_id>
    P.upsert_aluno(
        msg.phone,
        estado=f"{AWAITING_NOME_ALUNO}|{info.turma_id}",
    )
    return [OutboundMessage(MSG.MSG_PEDE_NOME_ALUNO.format(
        turma_codigo=info.turma_codigo,
        escola_nome=info.escola_nome,
    ))]


def _handle_nome_aluno(
    msg: InboundMessage, aluno: Dict[str, Any],
) -> List[OutboundMessage]:
    from redato_backend.whatsapp import messages as MSG
    from redato_backend.whatsapp import portal_link as PL
    import uuid as _uuid

    estado = aluno["estado"]
    parts = estado.split("|", 1)
    if len(parts) != 2:
        P.upsert_aluno(msg.phone, estado=AWAITING_CODIGO_TURMA)
        return [OutboundMessage(MSG.MSG_BEM_VINDO_NOVO_ALUNO)]

    try:
        turma_id = _uuid.UUID(parts[1])
    except ValueError:
        P.upsert_aluno(msg.phone, estado=AWAITING_CODIGO_TURMA)
        return [OutboundMessage(MSG.MSG_BEM_VINDO_NOVO_ALUNO)]

    nome = (msg.text or "").strip()
    if len(nome) < 3:
        return [OutboundMessage(
            "Não entendi seu nome. Manda o nome completo, por favor."
        )]

    vinculo, criado = PL.cadastrar_aluno_em_turma(
        turma_id=turma_id, nome=nome, telefone=msg.phone,
    )
    P.upsert_aluno(msg.phone, nome=nome, estado=READY)

    primeiro = nome.split()[0]
    return [OutboundMessage(MSG.MSG_CADASTRO_COMPLETO.format(
        primeiro_nome=primeiro,
        turma_codigo=vinculo.turma_codigo,
        escola_nome=vinculo.escola_nome,
    ))]


def _handle_turma_choice(
    msg: InboundMessage, aluno: Dict[str, Any],
) -> List[OutboundMessage]:
    """Aluno em múltiplas turmas escolheu por número (1, 2, ...).
    Estado: AWAITING_TURMA_CHOICE|<missao_canon>|<foto_path>"""
    from redato_backend.whatsapp import messages as MSG
    from redato_backend.whatsapp import portal_link as PL
    import uuid as _uuid

    estado = aluno["estado"]
    parts = estado.split("|", 2)
    if len(parts) < 2:
        P.upsert_aluno(msg.phone, estado=READY)
        return [OutboundMessage(MSG.MSG_ERRO_GENERICO)]
    missao_canon = parts[1]
    foto_path = parts[2] if len(parts) > 2 else None

    text = (msg.text or "").strip()
    if not text.isdigit():
        return [OutboundMessage(MSG.MSG_TURMA_ESCOLHA_INVALIDA)]
    idx = int(text) - 1

    vinculos = PL.list_alunos_ativos_por_telefone(msg.phone)
    if not (0 <= idx < len(vinculos)):
        return [OutboundMessage(MSG.MSG_TURMA_ESCOLHA_INVALIDA)]

    chosen = vinculos[idx]
    P.upsert_aluno(msg.phone, estado=READY)
    if foto_path and missao_canon:
        return _process_photo_after_validations(
            msg.phone, foto_path, missao_canon, aluno, chosen,
        )
    # Sem foto pendente: só confirma escolha e volta pra READY.
    return [OutboundMessage(
        f"OK, atendendo pela turma *{chosen.turma_codigo}* "
        f"da *{chosen.escola_nome}*. Manda a foto + código quando estiver "
        f"pronto."
    )]


def _parse_turma(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Extrai (turma_id, escola). Aceita 'TURMA — ESCOLA' ou
    'TURMA - ESCOLA' ou 'TURMA, ESCOLA'."""
    if not text:
        return None, None
    parts = re.split(r"\s*[—–\-,]\s*", text, maxsplit=1)
    if len(parts) < 2:
        return None, None
    turma = parts[0].strip()
    escola = parts[1].strip()
    if not turma or len(escola) < 5:
        return None, None
    # turma_id determinístico: <escola_slug>__<turma_slug>
    def _slug(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
    return f"{_slug(escola)}__{_slug(turma)}", escola


def _handle_ready_or_awaiting(
    msg: InboundMessage, aluno: Dict[str, Any],
) -> List[OutboundMessage]:
    estado = aluno["estado"]
    text = (msg.text or "").strip()
    image_path = msg.image_path

    # Tenta extrair missão da mensagem.
    missao_canon = _extract_missao(text) if text else None
    if missao_canon and not _is_valid_missao(missao_canon):
        return [OutboundMessage(MSG_MISSAO_INVALIDA)]

    # Sub-caso 4a: aluno mandou só texto sem missão e sem foto.
    if not image_path and not missao_canon:
        return [OutboundMessage(
            "Pra eu corrigir, preciso da *foto da redação* + o *código "
            "da missão* (ex.: RJ1OF10MF)."
        )]

    # Sub-caso 4b: missão sem foto → checa foto pendente, ou aguarda foto
    if missao_canon and not image_path:
        pending_foto = _get_pending_foto(msg.phone)
        if pending_foto and estado.startswith(AWAITING_CODIGO):
            return _process_photo(msg.phone, pending_foto, missao_canon, aluno)
        _set_pending_missao(msg.phone, missao_canon)
        return [OutboundMessage(MSG_FALTA_FOTO.format(missao=missao_canon))]

    # Sub-caso 4c: foto sem missão → tentar resgatar pendente, ou GUARDAR
    if image_path and not missao_canon:
        pending_missao = _get_pending_missao(msg.phone)
        if pending_missao and estado.startswith(AWAITING_FOTO):
            return _process_photo(msg.phone, image_path, pending_missao, aluno)
        # Guarda a foto pra reusar quando o código chegar
        _set_pending_foto(msg.phone, image_path)
        return [OutboundMessage(MSG_FALTA_MISSAO)]

    # Sub-caso 4d: missão + foto na mesma mensagem — vai direto.
    if image_path and missao_canon:
        return _process_photo(msg.phone, image_path, missao_canon, aluno)

    return [OutboundMessage(MSG_ERRO_GENERICO)]


# ──────────────────────────────────────────────────────────────────────
# Pending mission slot (simples — usa tabela alunos com pseudo-coluna em
# estado: AWAITING_FOTO|<missao_canon>). Evita schema migration.
# ──────────────────────────────────────────────────────────────────────

def _set_pending_missao(phone: str, missao_canon: str) -> None:
    """Aluno mandou código mas falta foto — guarda missão no estado."""
    P.upsert_aluno(phone, estado=f"{AWAITING_FOTO}|{missao_canon}")


def _get_pending_missao(phone: str) -> Optional[str]:
    a = P.get_aluno(phone)
    if not a:
        return None
    estado = a.get("estado") or ""
    if "|" in estado and estado.startswith(AWAITING_FOTO):
        return estado.split("|", 1)[1]
    return None


def _set_pending_foto(phone: str, foto_path: str) -> None:
    """Aluno mandou foto mas falta código — guarda path da foto no estado."""
    P.upsert_aluno(phone, estado=f"{AWAITING_CODIGO}|{foto_path}")


def _get_pending_foto(phone: str) -> Optional[str]:
    a = P.get_aluno(phone)
    if not a:
        return None
    estado = a.get("estado") or ""
    if "|" in estado and estado.startswith(AWAITING_CODIGO):
        return estado.split("|", 1)[1]
    return None


def _set_pending_duplicate(phone: str, dup_interaction_id: int,
                            foto_path: str, missao_canon: str) -> None:
    """Aluno enviou foto que duplica uma já corrigida. Guarda contexto pra
    decisão (1=reusar, 2=reavaliar). Encoded como
    `AWAITING_DUP|<id>|<missao>|<foto_path>`."""
    P.upsert_aluno(
        phone,
        estado=f"{AWAITING_DUPLICATE_CHOICE}|{dup_interaction_id}|{missao_canon}|{foto_path}",
    )


def _get_pending_duplicate(phone: str) -> Optional[Dict[str, str]]:
    a = P.get_aluno(phone)
    if not a:
        return None
    estado = a.get("estado") or ""
    if not estado.startswith(AWAITING_DUPLICATE_CHOICE + "|"):
        return None
    parts = estado.split("|", 3)
    if len(parts) != 4:
        return None
    _, dup_id, missao_canon, foto_path = parts
    return {
        "dup_id": dup_id,
        "missao_canon": missao_canon,
        "foto_path": foto_path,
    }


# ──────────────────────────────────────────────────────────────────────
# Foto → OCR → grade_mission → render
# ──────────────────────────────────────────────────────────────────────

_OCR_ERRADO_RE = re.compile(
    r"\b(ocr|leitura)\s*(errad[ao]|errou|errei|incorret[ao])\b",
    re.IGNORECASE,
)


def _is_ocr_errado(text: str) -> bool:
    """Detecta variações de 'ocr errado' / 'leitura errada' / 'ocr errou'."""
    return bool(_OCR_ERRADO_RE.search(text or ""))


def _handle_ocr_errado(
    msg: InboundMessage, aluno: Dict[str, Any],
) -> List[OutboundMessage]:
    """Aluno reportou que o OCR leu errado. Invalida última correção
    válida + volta estado pra AWAITING_FOTO mantendo a missão."""
    last = P.get_last_valid_interaction(msg.phone)
    if last is None:
        return [OutboundMessage(MSG_OCR_ERRADO_SEM_HISTORICO)]

    P.invalidate_interaction(int(last["id"]))
    activity_id = last.get("activity_id")
    if activity_id:
        _set_pending_missao(msg.phone, activity_id)
    else:
        P.upsert_aluno(msg.phone, estado=READY)
    return [OutboundMessage(MSG_OCR_ERRADO_CONFIRMADO)]


def _format_data_pt(iso_str: Optional[str]) -> str:
    """Converte ISO timestamp em 'DD/MM às HH:MM'."""
    if not iso_str:
        return "data anterior"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m às %H:%M")
    except Exception:
        return "data anterior"


def _handle_duplicate_choice(
    msg: InboundMessage, aluno: Dict[str, Any],
) -> List[OutboundMessage]:
    """Aluno está em AWAITING_DUPLICATE_CHOICE. Aceita '1' ou '2'.

    1 → re-renderiza feedback do JSON salvo (custo zero, nota idêntica)
    2 → processa normalmente como nova tentativa
    Outros → MSG_DUPLICATE_INVALID_CHOICE (mantém estado)
    """
    pending = _get_pending_duplicate(msg.phone)
    if pending is None:
        # Estado inconsistente; reseta pra READY
        P.upsert_aluno(msg.phone, estado=READY)
        return [OutboundMessage(MSG_ERRO_GENERICO)]

    text = (msg.text or "").strip()
    # Aceita "1", "1️⃣", "um" — idem pra 2
    is_one = text in {"1", "1️⃣", "1\ufe0f\u20e3", "um", "UM", "Um"}
    is_two = text in {"2", "2️⃣", "2\ufe0f\u20e3", "dois", "DOIS", "Dois"}

    if not (is_one or is_two):
        return [OutboundMessage(MSG_DUPLICATE_INVALID_CHOICE)]

    if is_one:
        # Re-renderiza do JSON salvo. Sem chamar API.
        dup_id = int(pending["dup_id"])
        with P._conn() as c:
            row = c.execute(
                "SELECT resposta_aluno FROM interactions WHERE id = ?",
                (dup_id,),
            ).fetchone()
        resposta = (row["resposta_aluno"] if row else None) or MSG_ERRO_GENERICO
        P.upsert_aluno(msg.phone, estado=READY)
        prefix = "Aqui está o feedback anterior:\n\n"
        return [OutboundMessage(prefix + resposta)]

    # is_two — processa como nova tentativa
    # Limpa o estado de duplicate e roda o pipeline com a foto guardada.
    foto_path = pending["foto_path"]
    missao_canon = pending["missao_canon"]
    P.upsert_aluno(msg.phone, estado=READY)
    return _process_photo_force(msg.phone, foto_path, missao_canon, aluno)


def _process_photo_force(
    phone: str,
    image_path: str,
    missao_canon: str,
    aluno: Dict[str, Any],
) -> List[OutboundMessage]:
    """Variante de _process_photo que pula a checagem de duplicata.
    Chamada quando aluno escolheu opção 2 (reavaliar)."""
    return _process_photo(phone, image_path, missao_canon, aluno,
                          skip_duplicate_check=True)


def _format_data_pt_dt(dt: datetime) -> str:
    return dt.strftime("%d/%m %H:%M")


def _format_choice_msg(vinculos: list) -> str:
    """Renderiza lista numerada de turmas pro aluno escolher."""
    from redato_backend.whatsapp import messages as MSG
    lista = "\n".join(
        f"{i+1}. {v.turma_codigo} — {v.escola_nome}"
        for i, v in enumerate(vinculos)
    )
    return MSG.MSG_ESCOLHE_TURMA.format(
        n_turmas=len(vinculos), lista_turmas=lista,
    )


def _process_photo_after_validations(
    phone: str, image_path: str, missao_canon: str,
    aluno: Dict[str, Any], aluno_vinculo,
) -> List[OutboundMessage]:
    """Variante chamada depois que aluno já escolheu turma. Pula a
    busca de vinculo mas REFAZ check de atividade (pode ter encerrado
    enquanto aluno escolhia)."""
    return _process_photo(
        phone, image_path, missao_canon, aluno,
        aluno_vinculo=aluno_vinculo,
    )


def _process_photo(
    phone: str,
    image_path: str,
    missao_canon: str,
    aluno: Dict[str, Any],
    skip_duplicate_check: bool = False,
    aluno_vinculo=None,
) -> List[OutboundMessage]:
    """Pipeline completo: OCR → router → render. Persiste interaction.

    M4: antes de processar, valida (1) aluno está vinculado a alguma
    turma, (2) há atividade ativa pra (turma, missão).

    Antes de chamar API (a menos que `skip_duplicate_check=True`): hash
    da foto + busca por duplicata. Se aluno já enviou exatamente essa
    foto pra essa missão, dispara prompt interativo (1=reusar feedback,
    2=reavaliar) em vez de gastar API gerando nota possivelmente
    diferente.
    """
    from redato_backend.missions import resolve_mode, MissionMode, grade_mission
    from redato_backend.missions.router import _canonicalize  # noqa
    from redato_backend.whatsapp import messages as MSG
    from redato_backend.whatsapp import portal_link as PL

    t0 = time.time()
    mode = resolve_mode(missao_canon)
    if mode is None:
        return [OutboundMessage(MSG_MISSAO_INVALIDA)]

    # M4: identificação de aluno + validação de atividade
    if aluno_vinculo is None:
        vinculos = PL.list_alunos_ativos_por_telefone(phone)
        if not vinculos:
            return [OutboundMessage(MSG.MSG_ALUNO_NAO_CADASTRADO)]
        if len(vinculos) > 1:
            # Encoda missão + foto no estado pra retomar após escolha
            P.upsert_aluno(
                phone,
                estado=f"{AWAITING_TURMA_CHOICE}|{missao_canon}|{image_path}",
            )
            return [OutboundMessage(_format_choice_msg(vinculos))]
        aluno_vinculo = vinculos[0]

    # M4: valida atividade ativa
    atividade = PL.find_atividade_para_missao(
        turma_id=aluno_vinculo.turma_id, missao_codigo=missao_canon,
    )
    if atividade is None:
        return [OutboundMessage(MSG.MSG_SEM_ATIVIDADE_ATIVA.format(
            codigo=missao_canon))]
    if atividade.status == "agendada":
        return [OutboundMessage(MSG.MSG_ATIVIDADE_AGENDADA.format(
            codigo=missao_canon,
            data_inicio_pt=_format_data_pt_dt(atividade.data_inicio),
        ))]
    if atividade.status == "encerrada":
        return [OutboundMessage(MSG.MSG_ATIVIDADE_ENCERRADA.format(
            codigo=missao_canon,
            data_fim_pt=_format_data_pt_dt(atividade.data_fim),
        ))]

    foto_hash = P.compute_image_hash(image_path)
    missao_id = missao_canon.replace("·", "_")

    if not skip_duplicate_check:
        duplicate = P.find_duplicate_interaction(phone, missao_id, foto_hash)
        if duplicate and duplicate.get("resposta_aluno"):
            data_str = _format_data_pt(duplicate.get("created_at"))
            _set_pending_duplicate(
                phone,
                int(duplicate["id"]),
                str(image_path),
                missao_canon,
            )
            return [OutboundMessage(MSG_DUPLICATE_PROMPT.format(data=data_str))]

    # OCR + quality check
    try:
        ocr = transcribe_with_quality_check(image_path)
    except Exception as exc:
        # Persiste falha técnica
        P.save_interaction(
            aluno_phone=phone, turma_id=aluno.get("turma_id"),
            missao_id=missao_canon.replace("·", "_"),
            activity_id=missao_canon,
            foto_path=str(image_path),
            foto_hash=foto_hash,
            texto_transcrito=None,
            ocr_quality_issues=[f"erro_tecnico: {type(exc).__name__}"],
            ocr_metrics=None,
            redato_output=None,
            resposta_aluno=MSG_ERRO_GENERICO,
            elapsed_ms=int((time.time() - t0) * 1000),
        )
        return [OutboundMessage(MSG_ERRO_GENERICO)]

    if ocr.rejected:
        msg_aluno = quality_issues_to_message(ocr.quality_issues)
        P.save_interaction(
            aluno_phone=phone, turma_id=aluno.get("turma_id"),
            missao_id=missao_canon.replace("·", "_"),
            activity_id=missao_canon,
            foto_path=str(image_path),
            foto_hash=foto_hash,
            texto_transcrito=ocr.text or None,
            ocr_quality_issues=ocr.quality_issues,
            ocr_metrics=ocr.metrics,
            redato_output=None,
            resposta_aluno=msg_aluno,
            elapsed_ms=int((time.time() - t0) * 1000),
        )
        return [OutboundMessage(msg_aluno)]

    # Pipeline Redato
    if mode == MissionMode.COMPLETO_INTEGRAL:
        # OF14 usa _claude_grade_essay direto (passa pelo pipeline v2).
        from redato_backend.dev_offline import _claude_grade_essay
        data = {
            "request_id": f"wpp_{phone}_{int(time.time())}",
            "user_id": phone,
            "activity_id": missao_canon,
            "theme": "Tema livre (foto enviada via WhatsApp)",
            "content": ocr.text,
        }
        try:
            tool_args = _claude_grade_essay(data)
        except Exception as exc:
            P.save_interaction(
                aluno_phone=phone, turma_id=aluno.get("turma_id"),
                missao_id=missao_canon.replace("·", "_"),
                activity_id=missao_canon,
                foto_path=str(image_path),
                foto_hash=foto_hash,
                texto_transcrito=ocr.text,
                ocr_quality_issues=ocr.quality_issues,
                ocr_metrics=ocr.metrics,
                redato_output={"error": f"{type(exc).__name__}: {exc}"},
                resposta_aluno=MSG_ERRO_GENERICO,
                elapsed_ms=int((time.time() - t0) * 1000),
            )
            return [OutboundMessage(MSG_ERRO_GENERICO)]
    else:
        data = {
            "request_id": f"wpp_{phone}_{int(time.time())}",
            "user_id": phone,
            "activity_id": missao_canon,
            "theme": "Tema livre (foto enviada via WhatsApp)",
            "content": ocr.text,
        }
        try:
            tool_args = grade_mission(data)
        except Exception as exc:
            P.save_interaction(
                aluno_phone=phone, turma_id=aluno.get("turma_id"),
                missao_id=missao_canon.replace("·", "_"),
                activity_id=missao_canon,
                foto_path=str(image_path),
                foto_hash=foto_hash,
                texto_transcrito=ocr.text,
                ocr_quality_issues=ocr.quality_issues,
                ocr_metrics=ocr.metrics,
                redato_output={"error": f"{type(exc).__name__}: {exc}"},
                resposta_aluno=MSG_ERRO_GENERICO,
                elapsed_ms=int((time.time() - t0) * 1000),
            )
            return [OutboundMessage(MSG_ERRO_GENERICO)]

    resposta = render_aluno_whatsapp(tool_args, texto_transcrito=ocr.text)
    elapsed_ms = int((time.time() - t0) * 1000)

    P.save_interaction(
        aluno_phone=phone, turma_id=aluno.get("turma_id"),
        missao_id=missao_canon.replace("·", "_"),
        activity_id=missao_canon,
        foto_path=str(image_path),
        foto_hash=foto_hash,
        texto_transcrito=ocr.text,
        ocr_quality_issues=ocr.quality_issues,
        ocr_metrics=ocr.metrics,
        redato_output=tool_args,
        resposta_aluno=resposta,
        elapsed_ms=elapsed_ms,
    )

    # M4: cria Interaction + Envio em Postgres pra agregação por turma
    # (dashboard, PDF). Falha aqui não invalida o feedback ao aluno —
    # SQLite legado tem source of truth pro bot.
    try:
        PL.criar_interaction_e_envio_postgres(
            aluno_phone=phone,
            aluno_turma_id=aluno_vinculo.aluno_turma_id,
            atividade_id=atividade.atividade_id,
            missao_codigo=missao_canon,
            activity_id=missao_canon,
            foto_path=str(image_path),
            foto_hash=foto_hash,
            texto_transcrito=ocr.text,
            ocr_quality_issues=ocr.quality_issues,
            ocr_metrics=ocr.metrics,
            redato_output=tool_args,
            resposta_aluno=resposta,
            elapsed_ms=elapsed_ms,
        )
    except Exception as exc:  # noqa: BLE001
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "Falha ao persistir Interaction/Envio em Postgres "
            "(SQLite legado já salvou): %r", exc,
        )

    # Volta pro estado READY (limpa pending)
    P.upsert_aluno(phone, estado=READY)

    return [OutboundMessage(resposta)]


# ──────────────────────────────────────────────────────────────────────
# Compatibilidade: handle_message simples (text-only)
# ──────────────────────────────────────────────────────────────────────

def handle_message(phone: str, text: Optional[str] = None,
                   image_path: Optional[str] = None) -> List[str]:
    """Entry point conveniente — retorna lista de strings."""
    msg = InboundMessage(phone=phone, text=text, image_path=image_path)
    return [m.text for m in handle_inbound(msg)]
