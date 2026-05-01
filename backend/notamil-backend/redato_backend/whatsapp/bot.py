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

import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from redato_backend.whatsapp import persistence as P


# Logger pros 3 try/except que protegem o pipeline de pegar 500 (OCR,
# grading OF14, grading foco/parcial). Antes do fix(of14) de 01/05,
# essas exceções eram persistidas no banco mas NÃO logadas — em prod o
# aluno via "Algo deu errado na correção" e ninguém sabia o motivo. Os
# raises de _claude_grade_essay/grade_mission sobem até aqui e a stack
# completa precisa aparecer nos logs Railway.
logger = logging.getLogger(__name__)
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
# Fase 2 passo 4 (jogo "Redação em Jogo") — estados encoded com partida_id
# pra evitar re-resolver via DB a cada mensagem do aluno na partida.
# Formato: "AGUARDANDO_CARTAS_PARTIDA|<uuid_partida>" e
#          "REVISANDO_TEXTO_MONTADO|<uuid_partida>".
AGUARDANDO_CARTAS_PARTIDA = "AGUARDANDO_CARTAS_PARTIDA"
REVISANDO_TEXTO_MONTADO = "REVISANDO_TEXTO_MONTADO"
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

# Aliases das mensagens canônicas em messages.py — preservados pra
# retrocompat de imports antigos. Lógica que precisa de versão dinâmica
# (lista de oficinas calculada do banco) usa `_msg_falta_missao` ou
# importa `messages.MSG_FALTA_MISSAO_DINAMICO` direto.
MSG_CADASTRADO = (
    "Beleza, {nome}! Cadastro feito.\n\n"
    "Pra eu corrigir uma redação, manda a *foto da página do livro*. "
    "Eu identifico a missão pela atividade aberta na sua turma. Se "
    "tiver mais de uma, pergunto."
)

MSG_FALTA_MISSAO = (
    "Recebi a foto, mas não sei qual missão é. "
    "Manda o número ou o código completo (ex.: RJ2·OF04·MF)."
)

MSG_FALTA_FOTO = (
    "Anotei: missão *{missao}*. Agora manda a foto da redação."
)

MSG_MISSAO_INVALIDA = (
    "Não reconheci esse código. Manda o código completo no formato "
    "`RJ{N}·OF{NN}·MF` (ex.: RJ2·OF04·MF) ou *cancelar* pra recomeçar."
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
# Mensagens do jogo "Redação em Jogo" (Fase 2 passo 4)
# ──────────────────────────────────────────────────────────────────────

MSG_JOGO_SAUDACAO_CARTAS = (
    "🎲 Você está jogando o *jogo de redação* na atividade "
    "*{missao_titulo}*, no grupo *{grupo_codigo}*.\n"
    "Tema: *{nome_humano_tema}*.\n\n"
    "Manda os *códigos das cartas* que vocês escolheram, separados "
    "por vírgula ou espaço. Exemplo:\n\n"
    "_E01, E10, E17, E22, E33, E37, E49, E51, "
    "P03, R05, K11, K22, A02, AC07, ME04, F02_"
)

MSG_JOGO_TEXTO_MONTADO = (
    "📝 Esta é a redação que o seu grupo montou com as cartas:\n\n"
    "{texto_montado}\n\n"
    "✏️ Agora você precisa *reescrever* em sua versão autoral.\n"
    "- Use suas palavras\n"
    "- Reforce com seu repertório\n"
    "- Mude onde achar que a carta escolhida ficou fraca\n\n"
    "Manda sua versão final quando estiver pronto."
)

MSG_JOGO_REESCRITA_RECEBIDA = (
    "✅ Reescrita recebida ({n_chars} caracteres). A avaliação "
    "será enviada quando o sistema processar."
)

MSG_JOGO_REESCRITA_CURTA_AVISO = (
    "⚠️ Texto curto demais ({n_chars} caracteres). Tem certeza que é "
    "sua versão final? Se for, manda *sim*. Se não, manda a versão "
    "completa."
)

MSG_JOGO_FOTO_EM_PARTIDA = (
    "Esta atividade pede *texto*, não foto. Manda os códigos das "
    "cartas (ou cancela com *cancelar*)."
)

MSG_JOGO_FOTO_EM_REESCRITA = (
    "Esta atividade pede a *reescrita em texto*, não foto. Manda sua "
    "versão autoral em texto (ou cancela com *cancelar*)."
)

MSG_JOGO_PRAZO_EXPIRADO = (
    "⏰ O prazo da partida ({prazo_pt}) já passou. Fala com o "
    "professor pra reabrir."
)

MSG_JOGO_REESCRITA_JA_ENVIADA = (
    "Você já mandou a reescrita dessa partida. Não é possível "
    "reenviar (decisão pedagógica). Espera a avaliação."
)

MSG_JOGO_AVISOS_PRE_TEXTO = (
    "ℹ️ Antes de seguir, alguns avisos:\n\n{avisos}"
)


# ──────────────────────────────────────────────────────────────────────
# Activity ID parsing — agora suporta 2S (OF01, OF04, ..., OF09 com
# leading zero) e mantém compat com 1S (OF10..OF14).
# ──────────────────────────────────────────────────────────────────────

# Formato canônico completo: RJ\dOF\d{1,2}MF com variações de separador
_MISSAO_RE_FULL = re.compile(
    r"RJ(\d)\s*[\W_]*\s*OF\s*(\d{1,2})\s*[\W_]*\s*MF",
    re.IGNORECASE,
)
# Autocorretor iPhone troca "RJ\dOF" por "RJ\d0F" (O → 0)
_MISSAO_RE_AUTOCORRECT = re.compile(
    r"RJ(\d)0F(\d{1,2})\s*[\W_]*\s*MF",
    re.IGNORECASE,
)
# Forma curta com OF: "OF01", "OF10", "of 4", "of12"
_MISSAO_RE_OF = re.compile(r"\bOF\s*(\d{1,2})\b", re.IGNORECASE)
# Número puro 1-99 como única coisa na mensagem: "1", "10", " 04 "
_MISSAO_RE_NUM_ONLY = re.compile(r"^\s*0*(\d{1,2})\s*$")

# Comando de cancelamento — em qualquer estado da FSM volta pra READY.
_CANCEL_RE = re.compile(
    r"^\s*(cancelar|cancel|resetar|reset|sair|exit|recome[çc]ar|come[çc]ar de novo)\s*$",
    re.IGNORECASE,
)

# Comando "trocar turma" — limpa escolha persistida e abre nova
# desambiguação (se aluno tem 2+ vínculos). Aceita variações comuns.
_TROCAR_TURMA_RE = re.compile(
    r"^\s*(trocar|mudar|alterar|outra)\s+(de\s+)?turma\s*$",
    re.IGNORECASE,
)


def _pad2(n: str) -> str:
    """Normaliza '4' → '04', '04' → '04', '10' → '10'."""
    return n.zfill(2)


def _extract_missao_canonical(text: str) -> Optional[str]:
    """Extrai SOMENTE quando há prefixo RJ\\d explícito. Retorna o
    canonical `RJ{N}·OF{NN}·MF` ou None.

    Útil pra aceitar código completo em qualquer estado da FSM (sem
    ambiguidade — o aluno especificou série).
    """
    if not text:
        return None
    m = _MISSAO_RE_FULL.search(text)
    if m:
        rj_n, of_nn = m.group(1), _pad2(m.group(2))
        return f"RJ{rj_n}·OF{of_nn}·MF"
    m = _MISSAO_RE_AUTOCORRECT.search(text)
    if m:
        rj_n, of_nn = m.group(1), _pad2(m.group(2))
        return f"RJ{rj_n}·OF{of_nn}·MF"
    return None


def _extract_oficina_numero(text: str) -> Optional[int]:
    """Extrai apenas o número da oficina, sem prefixo de série.

    Aceita (case-insensitive):
    - `OF10`, `OF01`, `of 4`
    - número puro como conteúdo único: `10`, `4`, `04`

    Retorna int 1-99 ou None. Caller resolve qual série usar via
    `list_atividades_ativas_por_aluno`.
    """
    if not text:
        return None
    m = _MISSAO_RE_OF.search(text)
    if m:
        try:
            n = int(m.group(1))
            if 1 <= n <= 99:
                return n
        except ValueError:
            pass
    m = _MISSAO_RE_NUM_ONLY.match(text)
    if m:
        try:
            n = int(m.group(1))
            if 1 <= n <= 99:
                return n
        except ValueError:
            pass
    return None


def _resolver_atividade_por_input(
    text: str,
    atividades_ativas: list,
) -> Tuple[Optional[Any], List[int]]:
    """Tenta casar o input do aluno com uma atividade ativa.

    Retorna (atividade_resolvida, numeros_ambiguos):
    - atividade != None, [] : match único — caller usa essa atividade
    - None, [n1, n2, ...] : número casou com >1 atividade (ambíguo) —
      caller deve perguntar pra desambiguar
    - None, [] : nenhum match — caller decide próxima ação

    Estratégia de matching:
    1. Código completo `RJ{N}·OF{NN}·MF` → match exato em missao_codigo
       (sem ambiguidade — aluno especificou série)
    2. Número solto / `OF{nn}` → casa com `oficina_numero`. Se >1
       atividade ativa tem mesmo oficina_numero (improvável mas
       possível em aluno multi-série), retorna ambíguo.
    """
    if not atividades_ativas:
        return None, []
    canonical = _extract_missao_canonical(text)
    if canonical:
        for atv in atividades_ativas:
            if atv.missao_codigo == canonical:
                return atv, []
        # Aluno escreveu RJ\d·OF\d\d·MF mas não bate com nenhuma ativa.
        # Caller pode reportar "missão informada não está ativa".
        return None, []

    of_num = _extract_oficina_numero(text)
    if of_num is not None:
        matches = [a for a in atividades_ativas if a.oficina_numero == of_num]
        if len(matches) == 1:
            return matches[0], []
        if len(matches) > 1:
            return None, [of_num]
    return None, []


def _formatar_lista_oficinas(atividades_ativas: list) -> str:
    """Renderiza '4', '4 ou 6', '4, 6 ou 13' a partir de oficina_numero
    das atividades ativas. Ordem ascendente."""
    nums = sorted({int(a.oficina_numero) for a in atividades_ativas})
    if not nums:
        return ""
    if len(nums) == 1:
        return str(nums[0])
    if len(nums) == 2:
        return f"{nums[0]} ou {nums[1]}"
    return ", ".join(str(n) for n in nums[:-1]) + f" ou {nums[-1]}"


# Backward-compat shim: alguns testes/callers antigos chamam
# _extract_missao(text) sem contexto de atividades. Mantém o nome,
# delega para a versão canônica + tenta resolver via número solto
# assumindo prefixo RJ1 (1S) — comportamento prévio era hardcoded 1S.
def _extract_missao(text: str) -> Optional[str]:
    """Compat: tenta extrair canonical SEM contexto de aluno.

    Em produção, o handler novo passa por `_resolver_atividade_por_input`
    com lista de atividades ativas e resolve o prefixo correto. Esta
    função é mantida pra:
    - aceitar código completo em qualquer formato (preserva semântica)
    - testes antigos que dependiam de "número solto → RJ1·OFNN·MF"

    Comportamento conservador: se não houver prefixo RJ\\d explícito e
    o input for número 1-14, ASSUME série 1S (compatibilidade); fora
    disso retorna None pra forçar caller a usar fluxo novo.
    """
    if not text:
        return None
    canonical = _extract_missao_canonical(text)
    if canonical:
        return canonical
    of_num = _extract_oficina_numero(text)
    if of_num is None:
        return None
    # Assume 1S (compat) — só funciona pra OFs históricos da 1ª série.
    if 10 <= of_num <= 14:
        return f"RJ1·OF{_pad2(str(of_num))}·MF"
    return None


def _is_valid_missao(canon: str) -> bool:
    """Verifica formato canonical RJ\\d·OF\\d\\d·MF. Não consulta DB —
    só validação sintática."""
    return bool(re.match(r"^RJ\d·OF\d{2}·MF$", canon or ""))


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

    # Comando especial "cancelar/resetar/sair" — em QUALQUER estado pós-
    # cadastro, volta pra READY. Não interfere com fluxo de cadastro
    # inicial (aluno ainda sem turma) — esse continua exigindo código.
    text_stripped = (msg.text or "").strip()
    if text_stripped and _CANCEL_RE.match(text_stripped):
        # Só permite cancelar quando aluno já tem ao menos 1 vínculo de
        # turma — evita aluno em onboarding inicial sair de loop sem
        # cadastrar.
        if not estado.startswith(AWAITING_CODIGO_TURMA) and \
                not estado.startswith(AWAITING_NOME_ALUNO):
            P.upsert_aluno(msg.phone, estado=READY)
            return [OutboundMessage(MSG.MSG_CANCELADO)]

    # Comando especial "ocr errado" — pode chegar em qualquer estado pós-avaliação
    if msg.text and _is_ocr_errado(msg.text):
        return _handle_ocr_errado(msg, aluno)

    # Comando especial "trocar turma" — em qualquer estado pós-cadastro,
    # limpa escolha persistida e abre nova desambiguação (se aluno tem
    # 2+ vínculos). Sem cadastro completo, o comando é ignorado pra não
    # quebrar onboarding inicial.
    if (text_stripped and _TROCAR_TURMA_RE.match(text_stripped)
            and not estado.startswith(AWAITING_CODIGO_TURMA)
            and not estado.startswith(AWAITING_NOME_ALUNO)):
        return _handle_trocar_turma(msg, aluno)

    # Caso especial: aguardando decisão de duplicata (1=reusar, 2=reavaliar)
    if estado.startswith(AWAITING_DUPLICATE_CHOICE + "|"):
        return _handle_duplicate_choice(msg, aluno)

    # Caso especial: aguardando escolha de turma (aluno em múltiplas).
    # Aceita ambas formas: com payload "AWAITING_TURMA_CHOICE|missao|foto"
    # (vindo de _process_photo) ou sem payload "AWAITING_TURMA_CHOICE"
    # (vindo de _handle_trocar_turma — sem foto pendente).
    if (estado == AWAITING_TURMA_CHOICE
            or estado.startswith(AWAITING_TURMA_CHOICE + "|")):
        return _handle_turma_choice(msg, aluno)

    # Fase 2 passo 4 — fluxo do jogo "Redação em Jogo".
    # Aluno já está numa partida (FSM cacheou partida_id). Trata
    # ANTES do fluxo de foto pra não cair em M9.2 acidentalmente.
    if estado.startswith(AGUARDANDO_CARTAS_PARTIDA + "|"):
        return _handle_aguardando_cartas_partida(msg, aluno, estado)
    if estado.startswith(REVISANDO_TEXTO_MONTADO + "|"):
        return _handle_revisando_texto_montado(msg, aluno, estado)

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

    # Fase 2 passo 4 — entrada em fluxo de partida. Aluno em READY
    # (sem partida ativa em FSM) que tem partida pendente em alguma
    # atividade ativa: redireciona pro fluxo do jogo. Dec G.1.4 (sem
    # partida = fluxo M9.2 normal de foto), então checamos só READY +
    # AWAITING_FOTO/CODIGO sem missão pendente.
    # OBS: chamada blocking de DB. Faz só na entrada do fluxo (uma vez
    # por mensagem). `find_partida_pendente_para_aluno` retorna None
    # rápido quando não há partida.
    if estado in (READY,) or estado.startswith(AWAITING_FOTO):
        try:
            partida_pend = PL.find_partida_pendente_para_aluno(msg.phone)
        except Exception:  # noqa: BLE001
            import logging as _logging
            _logging.getLogger(__name__).exception(
                "find_partida_pendente_para_aluno falhou — fallback fluxo normal",
            )
            partida_pend = None
        if partida_pend is not None:
            return _entrar_fluxo_partida(msg, aluno, partida_pend)

    # Bypass FSM via código completo: se aluno mandou `RJ\d·OF\d\d·MF`
    # explícito (e não está em estado de duplicate/cancel), trata
    # diretamente como nova interação. Limpa pending intermediários.
    if msg.text and not estado.startswith(AWAITING_DUPLICATE_CHOICE) and \
            not estado.startswith(AWAITING_TURMA_CHOICE):
        canonical = _extract_missao_canonical(msg.text)
        if canonical:
            # Reseta pending mas preserva foto pendente se houver
            pending_foto = _get_pending_foto(msg.phone)
            P.upsert_aluno(msg.phone, estado=READY)
            if msg.image_path:
                return _process_photo(msg.phone, msg.image_path,
                                      canonical, aluno)
            if pending_foto:
                return _process_photo(msg.phone, pending_foto,
                                      canonical, aluno)
            # Só código, sem foto — guarda missão e espera foto
            _set_pending_missao(msg.phone, canonical)
            return [OutboundMessage(MSG_FALTA_FOTO.format(missao=canonical))]

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


def _handle_trocar_turma(
    msg: InboundMessage, aluno: Dict[str, Any],
) -> List[OutboundMessage]:
    """Comando "trocar turma" — limpa escolha persistida e abre nova
    desambiguação. Se aluno só tem 1 vínculo ativo, responde que não há
    como trocar.
    """
    from redato_backend.whatsapp import messages as MSG
    from redato_backend.whatsapp import portal_link as PL

    vinculos = PL.list_alunos_ativos_por_telefone(msg.phone)
    if not vinculos:
        return [OutboundMessage(MSG.MSG_ALUNO_NAO_CADASTRADO)]

    # Limpa qualquer atalho persistido — caller vai escolher de novo.
    P.clear_turma_ativa(msg.phone)

    if len(vinculos) == 1:
        unico = vinculos[0]
        # Mantém estado anterior (READY); só informa que não dá pra trocar.
        return [OutboundMessage(MSG.MSG_TROCAR_TURMA_UNICA.format(
            turma_codigo=unico.turma_codigo,
            escola_nome=unico.escola_nome,
        ))]

    # 2+ vínculos: abre nova escolha sem foto pendente. Estado fica
    # AWAITING_TURMA_CHOICE (sem barra de payload — _handle_turma_choice
    # tolera ausência de missao/foto e só confirma).
    P.upsert_aluno(msg.phone, estado=AWAITING_TURMA_CHOICE)
    lista = "\n".join(
        f"{i+1}. {v.turma_codigo} — {v.escola_nome}"
        for i, v in enumerate(vinculos)
    )
    return [OutboundMessage(
        MSG.MSG_TROCAR_TURMA_INICIO.format(lista_turmas=lista)
    )]


def _handle_turma_choice(
    msg: InboundMessage, aluno: Dict[str, Any],
) -> List[OutboundMessage]:
    """Aluno em múltiplas turmas escolheu por número (1, 2, ...).
    Estado: AWAITING_TURMA_CHOICE[|<missao_canon>|<foto_path>]

    Persiste a escolha em `alunos.turma_ativa_id` (TTL via
    `P.TURMA_ATIVA_TTL_HOURS`) — próximas fotos não vão repergumtar
    enquanto válida.

    Guard-rail: se aluno mandar foto sem responder o número, o bot
    re-explica e mantém estado AWAITING_TURMA_CHOICE — não processa
    a foto silenciosamente em turma errada.
    """
    from redato_backend.whatsapp import messages as MSG
    from redato_backend.whatsapp import portal_link as PL

    estado = aluno["estado"]
    parts = estado.split("|", 2)
    # Estado pode ter ou não foto pendente (ex.: vindo de "trocar turma"
    # sem foto). Aceita 1, 2 ou 3 partes.
    missao_canon = parts[1] if len(parts) > 1 else None
    foto_path = parts[2] if len(parts) > 2 else None

    vinculos = PL.list_alunos_ativos_por_telefone(msg.phone)
    if not vinculos:
        # Vínculos perdidos no portal entre setar AWAITING_TURMA_CHOICE
        # e responder. Reset.
        P.upsert_aluno(msg.phone, estado=READY)
        return [OutboundMessage(MSG.MSG_ALUNO_NAO_CADASTRADO)]

    # Guard-rail: aluno mandou FOTO em vez de responder número.
    # Re-explica + mantém estado (não processa silenciosamente).
    if msg.image_path is not None:
        lista = "\n".join(
            f"{i+1}. {v.turma_codigo} — {v.escola_nome}"
            for i, v in enumerate(vinculos)
        )
        return [OutboundMessage(
            MSG.MSG_FOTO_DURANTE_ESCOLHA.format(lista_turmas=lista)
        )]

    text = (msg.text or "").strip()
    if not text.isdigit():
        return [OutboundMessage(MSG.MSG_TURMA_ESCOLHA_INVALIDA)]
    idx = int(text) - 1

    if not (0 <= idx < len(vinculos)):
        return [OutboundMessage(MSG.MSG_TURMA_ESCOLHA_INVALIDA)]

    chosen = vinculos[idx]
    # PERSISTE escolha pra valer pelas próximas TURMA_ATIVA_TTL_HOURS
    # — sem isso, bot pergunta de novo a cada foto.
    P.set_turma_ativa(msg.phone, chosen.turma_id)
    P.upsert_aluno(msg.phone, estado=READY)
    if foto_path and missao_canon:
        return _process_photo_after_validations(
            msg.phone, foto_path, missao_canon, aluno, chosen,
        )
    # Sem foto pendente (ex.: veio de "trocar turma"): confirma escolha
    # com TTL visível pro aluno. Mensagem nova MSG_TURMA_ATIVA_CONFIRMADA
    # padroniza tom em vez do f-string ad-hoc anterior.
    return [OutboundMessage(MSG.MSG_TURMA_ATIVA_CONFIRMADA.format(
        turma_codigo=chosen.turma_codigo,
        escola_nome=chosen.escola_nome,
        ttl_horas=int(P.TURMA_ATIVA_TTL_HOURS),
    ))]


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
    """Fluxo principal de envio (READY/AWAITING_FOTO/AWAITING_CODIGO).

    Mudança M9.2 (2026-04-29): roteamento agora consulta atividades
    ATIVAS da turma do aluno em vez de hardcode 1S. Casos:

    a) Foto sem código + 1 atividade ativa → processa direto
    b) Foto sem código + N atividades ativas → pergunta listando
       oficina_numero reais
    c) Foto sem código + 0 atividades ativas → pede código completo
    d) Código (completo) já foi tratado upstream em handle_inbound
       (bypass via _extract_missao_canonical)
    e) Número solto sem prefixo + 1 atividade ativa que casa com ele
       → processa direto (resolve série pelo contexto)
    """
    from redato_backend.whatsapp import messages as MSG
    from redato_backend.whatsapp import portal_link as PL

    estado = aluno["estado"]
    text = (msg.text or "").strip()
    image_path = msg.image_path

    # Atividades ativas das turmas do aluno (pode ser 0).
    # Falha de DB não trava o fluxo — fallback graceful.
    try:
        atividades_ativas = PL.list_atividades_ativas_por_aluno(msg.phone)
    except Exception:  # noqa: BLE001
        import logging as _logging
        _logging.getLogger(__name__).exception(
            "Falha consultando atividades ativas; usando fluxo legado"
        )
        atividades_ativas = []

    # 1. Resolve via contexto: se aluno mandou número/OF/canonical e
    #    casa com uma atividade ativa, usa direto.
    atividade_resolvida, ambiguos = _resolver_atividade_por_input(
        text, atividades_ativas
    )

    # Caso e1: input casou com atividade ativa
    if atividade_resolvida is not None:
        missao_canon = atividade_resolvida.missao_codigo
        if image_path:
            return _process_photo(msg.phone, image_path, missao_canon, aluno)
        # Sem foto na mensagem — checa pending, ou guarda missão
        pending_foto = _get_pending_foto(msg.phone)
        if pending_foto and estado.startswith(AWAITING_CODIGO):
            return _process_photo(msg.phone, pending_foto, missao_canon, aluno)
        _set_pending_missao(msg.phone, missao_canon)
        return [OutboundMessage(MSG_FALTA_FOTO.format(missao=missao_canon))]

    # Caso e2: número casou com >1 atividade (aluno multi-turma com
    # mesmo oficina_numero em séries diferentes). Pergunta com lista
    # restrita às que bateram.
    if ambiguos:
        # Filtra atividades que tem o número ambíguo
        candidatas = [a for a in atividades_ativas
                      if a.oficina_numero in ambiguos]
        lista = "\n".join(
            f"{i+1}. {a.missao_codigo} ({a.turma_codigo} — {a.escola_nome})"
            for i, a in enumerate(candidatas)
        )
        # Sem state machine extra pra esse caso raro; pede código completo
        if image_path:
            _set_pending_foto(msg.phone, image_path)
        return [OutboundMessage(MSG.MSG_AMBIGUO_PEDE_COMPLETO.format(
            numero=ambiguos[0], lista=lista,
        ))]

    # Sub-caso 4a: nada útil + nada de foto (texto vazio ou irrelevante)
    if not image_path:
        # Tem foto pendente em estado AWAITING_CODIGO — aluno mandou só
        # texto que não casou; insiste pedindo missão.
        if estado.startswith(AWAITING_CODIGO):
            return [OutboundMessage(
                _msg_falta_missao(atividades_ativas)
            )]
        return [OutboundMessage(
            "Pra eu corrigir, preciso da *foto da redação*. "
            "Manda a foto da página do livro com sua redação."
        )]

    # Sub-caso 4b: foto chegou. Resolve por número de atividades ativas.
    pending_missao = _get_pending_missao(msg.phone)
    if pending_missao and estado.startswith(AWAITING_FOTO):
        return _process_photo(msg.phone, image_path, pending_missao, aluno)

    # Caso a: 1 atividade ativa → processa direto, sem perguntar.
    if len(atividades_ativas) == 1:
        unica = atividades_ativas[0]
        return _process_photo(msg.phone, image_path,
                              unica.missao_codigo, aluno)

    # Caso b: >1 atividades ativas → pergunta com lista real.
    # Caso c: 0 atividades ativas → pede código completo.
    _set_pending_foto(msg.phone, image_path)
    return [OutboundMessage(_msg_falta_missao(atividades_ativas))]


def _msg_falta_missao(atividades_ativas: list) -> str:
    """Renderiza a mensagem de 'foto sem código' adequada ao contexto."""
    from redato_backend.whatsapp import messages as MSG
    if not atividades_ativas:
        return MSG.MSG_FALTA_MISSAO_SEM_ATIVAS
    nums = _formatar_lista_oficinas(atividades_ativas)
    return MSG.MSG_FALTA_MISSAO_DINAMICO.format(numeros=nums)


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
    """Converte ISO timestamp em 'DD/MM às HH:MM' em horário de
    Brasília (M9.5, 2026-04-29).

    Bug original: fazia `dt.strftime(...)` direto no datetime UTC do
    banco. Aluno mandava às 13:45 BRT (16:45 UTC), bot dizia "Recebi
    em 16:45". Fix: delegar pra `fmt_brt_iso_to_brt` que aplica
    America/Sao_Paulo antes do strftime.
    """
    from redato_backend.utils.timezone import fmt_brt_iso_to_brt
    return fmt_brt_iso_to_brt(iso_str, short=True)


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
    """Formata datetime UTC como '29/04 13:45' em horário de Brasília
    (M9.5). Usado em MSG_ATIVIDADE_AGENDADA / MSG_ATIVIDADE_ENCERRADA.
    Antes fazia strftime direto no UTC — mesmo bug do _format_data_pt."""
    from redato_backend.utils.timezone import fmt_brt
    return fmt_brt(dt, "%d/%m %H:%M")


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
            # 2026-05-01 — Tenta atalho via turma persistida (TTL 2h).
            # Se aluno já escolheu recentemente E a turma persistida
            # ainda bate com algum vínculo ativo, reusa silenciosamente.
            # Senão, pergunta. Vínculo desativado no portal entre escolha
            # e agora invalida o atalho (fail-safe).
            turma_ativa_id = P.get_turma_ativa(phone)
            if turma_ativa_id:
                bater = next(
                    (v for v in vinculos if str(v.turma_id) == str(turma_ativa_id)),
                    None,
                )
                if bater is not None:
                    aluno_vinculo = bater
                else:
                    # Turma persistida não está mais ativa — limpa.
                    P.clear_turma_ativa(phone)

            if aluno_vinculo is None:
                # Encoda missão + foto no estado pra retomar após escolha
                P.upsert_aluno(
                    phone,
                    estado=f"{AWAITING_TURMA_CHOICE}|{missao_canon}|{image_path}",
                )
                return [OutboundMessage(_format_choice_msg(vinculos))]
        else:
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
        # Persiste falha técnica + LOGA pro Railway capturar stack
        logger.exception(
            "OCR failed for %s on %s (foto=%s)",
            phone, missao_canon, image_path,
        )
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
            # Stack trace COMPLETO — antes só print() em dev_offline
            # silenciava em prod async. Agora `_claude_grade_essay` levanta
            # tanto se FT path falhar no parser quanto se Claude path
            # falhar (ex.: ANTHROPIC_API_KEY missing, rate limit, etc.).
            logger.exception(
                "OF14 grading failed for %s on %s (request_id=%s)",
                phone, missao_canon, data["request_id"],
            )
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
            logger.exception(
                "Mission grading failed for %s on %s (request_id=%s)",
                phone, missao_canon, data["request_id"],
            )
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
    # (dashboard, PDF). M9.6 (2026-04-29): se for reavaliação
    # (skip_duplicate_check=True) o Postgres calcula tentativa_n =
    # max+1; em caso de falha, **raise** com log ERROR — antes era
    # warning silencioso que escondia state inconsistente por dias.
    tentativa_n: int = 1
    postgres_falhou = False
    try:
        _, _, tentativa_n = PL.criar_interaction_e_envio_postgres(
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
        _logging.getLogger(__name__).error(
            "Falha ao persistir Interaction/Envio em Postgres "
            "(SQLite legado já salvou): %r", exc,
        )
        postgres_falhou = True

    # Volta pro estado READY (limpa pending)
    P.upsert_aluno(phone, estado=READY)

    return _build_messages_pos_correcao(
        resposta=resposta,
        skip_duplicate_check=skip_duplicate_check,
        postgres_falhou=postgres_falhou,
        tentativa_n=tentativa_n,
    )


def _build_messages_pos_correcao(
    *,
    resposta: str,
    skip_duplicate_check: bool,
    postgres_falhou: bool,
    tentativa_n: int,
) -> List[OutboundMessage]:
    """Monta a sequência de OutboundMessages depois que o pipeline de
    correção terminou. Extraído de `_process_photo` em M9.6 pra ser
    testável sem mockar webhook + Twilio + Anthropic.

    Regra:
    - Sempre retorna ao menos 1 OutboundMessage (a `resposta`).
    - Quando aluno escolheu reavaliação (`skip_duplicate_check=True`)
      E o Postgres registrou nova tentativa (`tentativa_n >= 2` e
      `postgres_falhou=False`), prepende um ack curto avisando o
      número da tentativa. Isso evita o aluno achar que reenviou
      "no vácuo" quando o feedback chega — bug de UX do M9.6.
    - Se Postgres falhou na nova tentativa, NÃO mostra o ack pra
      não comunicar um número que pode estar errado (a contagem em
      Postgres ficou inconsistente).
    """
    msgs: List[OutboundMessage] = []
    if skip_duplicate_check and not postgres_falhou and tentativa_n > 1:
        msgs.append(OutboundMessage(
            f"📬 *Tentativa {tentativa_n} registrada.* Avaliando sua "
            f"nova versão..."
        ))
    msgs.append(OutboundMessage(resposta))
    return msgs


# ──────────────────────────────────────────────────────────────────────
# Fase 2 passo 4 — handlers do jogo "Redação em Jogo"
# ──────────────────────────────────────────────────────────────────────

def _format_prazo_brt(dt: datetime) -> str:
    """Formata datetime aware UTC como '06/05 às 22:00' BRT."""
    from redato_backend.utils.timezone import fmt_brt
    return fmt_brt(dt, "%d/%m às %H:%M")


def _entrar_fluxo_partida(
    msg: InboundMessage, aluno: Dict[str, Any],
    partida: Any,
) -> List[OutboundMessage]:
    """Aluno em READY tem partida pendente — saúda + transição.

    Despacha pra `aguardando_cartas` ou `revisando_texto_montado`
    direto baseado em `estado_partida` da partida (texto_montado já
    foi populado por outra sessão? aluno entra no estado certo).
    """
    if partida.estado_partida == "aguardando_cartas":
        # Saudação inicial + estado encoded com partida_id
        P.upsert_aluno(
            msg.phone,
            estado=f"{AGUARDANDO_CARTAS_PARTIDA}|{partida.partida_id}",
        )
        return [OutboundMessage(MSG_JOGO_SAUDACAO_CARTAS.format(
            missao_titulo=partida.missao_titulo,
            grupo_codigo=partida.grupo_codigo,
            nome_humano_tema=partida.minideck_nome_humano,
        ))]

    # estado_partida == "aguardando_reescrita": cartas já foram
    # validadas (talvez por outro membro do grupo), texto_montado
    # populado. Manda direto pro REVISANDO.
    P.upsert_aluno(
        msg.phone,
        estado=f"{REVISANDO_TEXTO_MONTADO}|{partida.partida_id}",
    )
    return [OutboundMessage(MSG_JOGO_TEXTO_MONTADO.format(
        texto_montado=partida.texto_montado,
    ))]


def _decode_partida_id_do_estado(estado: str) -> Optional[uuid.UUID]:
    """Extrai partida_id de estados encoded como '<PREFIX>|<uuid>'."""
    import uuid as _uuid
    if "|" not in estado:
        return None
    raw = estado.split("|", 1)[1]
    try:
        return _uuid.UUID(raw)
    except (ValueError, TypeError):
        return None


def _handle_aguardando_cartas_partida(
    msg: InboundMessage, aluno: Dict[str, Any], estado: str,
) -> List[OutboundMessage]:
    """Aluno em AGUARDANDO_CARTAS_PARTIDA mandou mensagem.

    Cenários:
    - Imagem (foto) → mensagem MSG_JOGO_FOTO_EM_PARTIDA, estado mantém
    - Texto sem códigos válidos → reitera MSG_JOGO_SAUDACAO_CARTAS
    - Texto com códigos → valida → se erro reporta; se warning aceita
      com aviso; se ok monta texto-base + transição
    """
    from redato_backend.whatsapp import portal_link as PL
    from redato_backend.whatsapp.jogo_partida import (
        montar_texto_montado, parse_codigos, validar_partida,
    )

    partida_id = _decode_partida_id_do_estado(estado)
    if partida_id is None:
        # FSM corrompida — reset.
        P.upsert_aluno(msg.phone, estado=READY)
        return [OutboundMessage(
            "Algo deu errado no estado da partida. Manda *cancelar* "
            "e começa de novo."
        )]

    # Re-resolve partida (pode ter mudado prazo, sido apagada, etc.).
    partida = PL.get_partida_by_id(partida_id, phone=msg.phone)
    if partida is None:
        # Partida não existe mais ou aluno foi removido. Volta READY.
        P.upsert_aluno(msg.phone, estado=READY)
        return [OutboundMessage(
            "Essa partida não está mais ativa pra você. Fala com o "
            "professor."
        )]

    # Prazo expirado?
    if partida.prazo_reescrita < datetime.now(timezone.utc):
        P.upsert_aluno(msg.phone, estado=READY)
        return [OutboundMessage(MSG_JOGO_PRAZO_EXPIRADO.format(
            prazo_pt=_format_prazo_brt(partida.prazo_reescrita),
        ))]

    # Foto em fluxo de cartas?
    if msg.image_path:
        return [OutboundMessage(MSG_JOGO_FOTO_EM_PARTIDA)]

    text = (msg.text or "").strip()
    codigos = parse_codigos(text)
    if not codigos:
        # Texto sem códigos — repete a saudação como prompt.
        return [OutboundMessage(MSG_JOGO_SAUDACAO_CARTAS.format(
            missao_titulo=partida.missao_titulo,
            grupo_codigo=partida.grupo_codigo,
            nome_humano_tema=partida.minideck_nome_humano,
        ))]

    # Carrega catálogo do minideck pra validar
    ctx = PL.carregar_contexto_validacao(partida.minideck_id)
    if ctx is None:
        # Minideck removido — não deveria acontecer em prod, mas
        # cobre catalog drift. Reset estado.
        P.upsert_aluno(msg.phone, estado=READY)
        return [OutboundMessage(
            "Tema da partida não está mais disponível. Fala com o "
            "professor."
        )]

    resultado = validar_partida(codigos, ctx)
    if not resultado.ok:
        return [OutboundMessage(resultado.mensagem_erro or "Validação falhou.")]

    texto_montado = montar_texto_montado(
        resultado.estruturais_em_ordem,
        resultado.lacunas_por_tipo,
        ctx,
        placeholders_vazios=resultado.placeholders_vazios,
    )

    # Persiste cartas + texto_montado
    try:
        # Reordena codigos: estruturais na ordem do tabuleiro + lacunas
        # na ordem que o aluno mandou (preserva intenção).
        codigos_persist: List[str] = list(resultado.estruturais_em_ordem)
        for tipo_lac, codes in resultado.lacunas_por_tipo.items():
            codigos_persist.extend(codes)
        PL.persist_cartas_e_texto(
            partida_id=partida_id,
            codigos=codigos_persist,
            texto_montado=texto_montado,
        )
    except Exception as exc:  # noqa: BLE001
        import logging as _logging
        _logging.getLogger(__name__).exception(
            "persist_cartas_e_texto falhou: %r", exc,
        )
        return [OutboundMessage(
            "Tive um problema pra salvar as cartas. Tenta de novo "
            "em alguns segundos."
        )]

    # Transiciona pra REVISANDO
    P.upsert_aluno(
        msg.phone,
        estado=f"{REVISANDO_TEXTO_MONTADO}|{partida_id}",
    )

    # Resposta: avisos (se houver) + texto montado
    msgs: List[OutboundMessage] = []
    if resultado.warnings:
        msgs.append(OutboundMessage(MSG_JOGO_AVISOS_PRE_TEXTO.format(
            avisos="\n".join(f"• {w}" for w in resultado.warnings),
        )))
    msgs.append(OutboundMessage(MSG_JOGO_TEXTO_MONTADO.format(
        texto_montado=texto_montado,
    )))
    return msgs


def _handle_revisando_texto_montado(
    msg: InboundMessage, aluno: Dict[str, Any], estado: str,
) -> List[OutboundMessage]:
    """Aluno em REVISANDO_TEXTO_MONTADO mandou mensagem — esperamos
    texto da reescrita.

    - Imagem: redireciona ("essa atividade pede texto")
    - Texto >= 50 chars: persiste e volta READY
    - Texto < 50 chars: avisa "tem certeza?" sem persistir (precisa
      reenviar). Bot fica em REVISANDO.

    Avaliação Redato (modo jogo_redacao) é Passo 5 — aqui
    `redato_output` fica null. UI do professor mostra "aguardando
    avaliação".
    """
    from redato_backend.whatsapp import portal_link as PL

    partida_id = _decode_partida_id_do_estado(estado)
    if partida_id is None:
        P.upsert_aluno(msg.phone, estado=READY)
        return [OutboundMessage(
            "Estado da partida corrompido. Manda *cancelar* e começa "
            "de novo."
        )]

    partida = PL.get_partida_by_id(partida_id, phone=msg.phone)
    if partida is None:
        P.upsert_aluno(msg.phone, estado=READY)
        return [OutboundMessage(
            "Essa partida não está mais ativa pra você. Fala com o "
            "professor."
        )]

    # Defesa: aluno já submeteu (caso raro de race condition).
    if PL.find_reescrita_existente(
        partida_id=partida.partida_id,
        aluno_turma_id=partida.aluno_turma_id,
    ):
        P.upsert_aluno(msg.phone, estado=READY)
        return [OutboundMessage(MSG_JOGO_REESCRITA_JA_ENVIADA)]

    # Prazo expirado durante a digitação? Bloqueia.
    if partida.prazo_reescrita < datetime.now(timezone.utc):
        P.upsert_aluno(msg.phone, estado=READY)
        return [OutboundMessage(MSG_JOGO_PRAZO_EXPIRADO.format(
            prazo_pt=_format_prazo_brt(partida.prazo_reescrita),
        ))]

    if msg.image_path:
        return [OutboundMessage(MSG_JOGO_FOTO_EM_REESCRITA)]

    texto = (msg.text or "").strip()
    if not texto:
        return [OutboundMessage(
            "Manda o texto da sua reescrita."
        )]

    n_chars = len(texto)
    # Heurística: < 50 chars muito curto. Bot avisa mas NÃO persiste —
    # aluno reenvia versão completa. Bot fica em REVISANDO.
    if n_chars < 50:
        return [OutboundMessage(MSG_JOGO_REESCRITA_CURTA_AVISO.format(
            n_chars=n_chars,
        ))]

    try:
        reescrita_id = PL.persist_reescrita(
            partida_id=partida.partida_id,
            aluno_turma_id=partida.aluno_turma_id,
            texto=texto,
        )
    except Exception as exc:  # noqa: BLE001
        # IntegrityError aqui é race — outra requisição persistiu
        # primeiro. Resposta neutra: avisa que já foi enviada.
        from sqlalchemy.exc import IntegrityError as _IE
        if isinstance(exc, _IE):
            P.upsert_aluno(msg.phone, estado=READY)
            return [OutboundMessage(MSG_JOGO_REESCRITA_JA_ENVIADA)]
        import logging as _logging
        _logging.getLogger(__name__).exception(
            "persist_reescrita falhou: %r", exc,
        )
        return [OutboundMessage(
            "Tive um problema pra salvar a reescrita. Tenta de novo "
            "em alguns segundos."
        )]

    # Volta o estado pra READY antes de chamar Claude — se Claude
    # demorar ou falhar, aluno já está num estado consistente
    # (reescrita persistida, sem FSM travada). Próxima mensagem do
    # aluno cai em fluxo normal.
    P.upsert_aluno(msg.phone, estado=READY)

    # Fase 2 passo 5 — avaliação SÍNCRONA via Claude. Bot bloqueia
    # ~30s aguardando resposta. Decisão Daniel 2026-04-29: padrão
    # dos outros modos (foco_c2/c3/c4/c5/completo_parcial), familiar
    # pro aluno.
    return _avaliar_reescrita_e_responder(
        msg=msg,
        partida=partida,
        reescrita_id=reescrita_id,
        reescrita_texto=texto,
        n_chars=n_chars,
    )


def _avaliar_reescrita_e_responder(
    *,
    msg: InboundMessage,
    partida: Any,
    reescrita_id: uuid.UUID,
    reescrita_texto: str,
    n_chars: int,
) -> List[OutboundMessage]:
    """Chama o pipeline Redato modo jogo_redacao, persiste o
    `redato_output` na reescrita e retorna feedback formatado pro
    aluno via WhatsApp.

    Tratamento de erro:
    - Timeout/erro Anthropic: bot avisa "estamos avaliando, você
      receberá em alguns minutos" — reescrita já está persistida com
      `redato_output=null`, professor pode reprocessar via UI futura
      (Passo 6).
    - Erro genérico: log + mensagem genérica + reescrita continua
      no DB.
    """
    import time as _time

    from redato_backend.whatsapp import portal_link as PL
    from redato_backend.whatsapp.render import render_aluno_whatsapp

    logger = _get_logger()

    # 1. Carrega contexto (catálogo do minideck) + partida atualizada
    ctx = PL.carregar_contexto_validacao(partida.minideck_id)
    if ctx is None:
        logger.error(
            "carregar_contexto_validacao retornou None — minideck %s",
            partida.minideck_id,
        )
        return [OutboundMessage(
            f"Sua reescrita ({n_chars} caracteres) foi recebida, "
            "mas não consegui avaliar agora porque o tema da partida "
            "não está disponível. Fala com o professor."
        )]

    # codigos_escolhidos vem da partida atualizada — re-resolve pra
    # garantir snapshot consistente com texto_montado.
    codigos_escolhidos: List[str] = []
    try:
        partida_atual = PL.get_partida_by_id(
            partida.partida_id, phone=msg.phone,
        )
        if partida_atual is not None and isinstance(
            getattr(partida_atual, "texto_montado", None), str,
        ):
            # Acessar `cartas_escolhidas.codigos` direto via DB já que
            # PartidaPendenteContext não expõe — fazemos query auxiliar.
            from sqlalchemy.orm import Session as _Session
            from redato_backend.portal.db import get_engine as _ge
            from redato_backend.portal.models import PartidaJogo as _PJ
            with _Session(_ge()) as _s:
                _p = _s.get(_PJ, partida.partida_id)
                if _p is not None:
                    raw = _p.cartas_escolhidas or {}
                    if isinstance(raw, dict):
                        codigos_escolhidos = list(raw.get("codigos") or [])
    except Exception:  # noqa: BLE001
        logger.exception(
            "Falha ao re-resolver codigos_escolhidos da partida %s",
            partida.partida_id,
        )

    # 2. Chama Claude
    from redato_backend.missions.router import grade_jogo_redacao

    payload = {
        "tema_minideck": ctx.minideck_tema,
        "nome_humano_tema": ctx.minideck_nome_humano,
        # cartas_lacuna_full: lista de snapshots — render_minideck_block
        # precisa de objetos com .codigo/.tipo/.conteudo. ContextoValidacao
        # tem isso em `lacunas_por_codigo.values()`.
        "cartas_lacuna_full": list(ctx.lacunas_por_codigo.values()),
        "codigos_escolhidos": codigos_escolhidos,
        "estruturais_por_codigo": ctx.estruturais_por_codigo,
        "lacunas_por_codigo": ctx.lacunas_por_codigo,
        "texto_montado": partida.texto_montado or "",
        "reescrita_texto": reescrita_texto,
    }

    t0 = _time.monotonic()
    tool_args: Optional[Dict[str, Any]] = None
    erro_temporario = False
    try:
        tool_args = grade_jogo_redacao(payload)
    except Exception as exc:  # noqa: BLE001
        # Timeout/rate-limit/connection: tratamento específico pra o
        # aluno saber que vai receber depois. Avaliação real será
        # reprocessada manualmente pelo professor (Passo 6 implementa
        # "rerodar avaliação" via UI).
        import anthropic
        if isinstance(exc, (anthropic.APITimeoutError,
                              anthropic.APIConnectionError,
                              anthropic.RateLimitError)):
            erro_temporario = True
        logger.exception(
            "grade_jogo_redacao falhou pra reescrita_id=%s: %r",
            reescrita_id, exc,
        )

    elapsed_ms = int((_time.monotonic() - t0) * 1000)

    if tool_args is None:
        if erro_temporario:
            return [OutboundMessage(
                f"📨 Sua reescrita ({n_chars} caracteres) foi recebida! "
                "A avaliação está demorando — você receberá o feedback "
                "em alguns minutos quando o sistema processar. Pode "
                "guardar o WhatsApp."
            )]
        return [OutboundMessage(
            f"📨 Sua reescrita ({n_chars} caracteres) foi recebida! "
            "Tive um problema técnico pra avaliar agora — o professor "
            "pode reprocessar pelo portal."
        )]

    # 3. Persiste redato_output
    try:
        PL.update_reescrita_redato_output(
            reescrita_id=reescrita_id,
            redato_output=tool_args,
            elapsed_ms=elapsed_ms,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "update_reescrita_redato_output falhou: %r", exc,
        )
        # Continua e mostra feedback ao aluno mesmo assim — pior
        # caso é redato_output ficar null no DB e professor reprocessar.

    # 4. Renderiza feedback WhatsApp + responde
    feedback = render_aluno_whatsapp(tool_args, texto_transcrito=None)
    return [OutboundMessage(feedback)]


def _get_logger():
    import logging as _logging
    return _logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Compatibilidade: handle_message simples (text-only)
# ──────────────────────────────────────────────────────────────────────

def handle_message(phone: str, text: Optional[str] = None,
                   image_path: Optional[str] = None) -> List[str]:
    """Entry point conveniente — retorna lista de strings."""
    msg = InboundMessage(phone=phone, text=text, image_path=image_path)
    return [m.text for m in handle_inbound(msg)]
