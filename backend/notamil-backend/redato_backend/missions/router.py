"""Roteamento por activity_id para os modos REJ 1S + 2S.

Spec: docs/redato/v3/redato_1S_criterios.md (1S),
docs/redato/v3/proposta_flags_foco_c1_c2.md (foco_c2 — 2026-04-28).

Activity IDs no formato `RJ{N}·OFXX·MF·<modo>` (separador é U+00B7 MIDDLE DOT):
- RJ1·OF10·MF·Foco C3        → foco_c3
- RJ1·OF11·MF·Foco C4        → foco_c4
- RJ1·OF12·MF·Foco C5        → foco_c5
- RJ1·OF13·MF·Correção 5 comp. → completo_parcial
- RJ1·OF14·MF·Correção 5 comp. → completo_integral (pipeline v2 padrão)
- RJ2·OF04·MF·Foco C2        → foco_c2 (2S, M9.1)
- RJ2·OF06·MF·Foco C2        → foco_c2 (2S, M9.1)

Aceita também variantes com separador `_` ou `-` ou `.` para robustez de
chamadas vindas do app.
"""
from __future__ import annotations

import os
import re
from enum import Enum
from typing import Any, Dict, Optional

from redato_backend.missions.schemas import TOOLS_BY_MODE
from redato_backend.missions.prompts import (
    system_prompt_for,
    context_block_for,
    feedback_aluno_registro_block,
    render_minideck_block,
    render_cartas_escolhidas_block,
)
from redato_backend.missions.detectors import (
    compute_pre_flags,
    render_pre_flags_block,
    palavra_dia_presente,
)


class MissionMode(str, Enum):
    # foco_c1 ADIADO (Daniel, 2026-04-28). Quando ativar, adicionar
    # FOCO_C1 = "foco_c1" + entrada em _MISSAO_TO_MODE +
    # _DEFAULT_MODEL_BY_MODE + branch em scoring.apply_override.
    FOCO_C2 = "foco_c2"
    FOCO_C3 = "foco_c3"
    FOCO_C4 = "foco_c4"
    FOCO_C5 = "foco_c5"
    COMPLETO_PARCIAL = "completo_parcial"
    COMPLETO_INTEGRAL = "completo_integral"
    # Fase 2 passo 5 (2S, OF13 jogo de redação) — Daniel 2026-04-29.
    # NÃO entra em _MISSAO_TO_MODE porque não é resolvido por
    # activity_id sozinho — o caller (bot) decide chamar
    # `grade_jogo_redacao` em vez de `grade_mission` quando há
    # partida ativa. activity_id da atividade pode ser RJ2_OF13_MF
    # mas o roteamento pra esse modo depende do estado da partida.
    JOGO_REDACAO = "jogo_redacao"


_MISSAO_TO_MODE: Dict[str, MissionMode] = {
    "RJ1_OF10_MF": MissionMode.FOCO_C3,
    "RJ1_OF11_MF": MissionMode.FOCO_C4,
    "RJ1_OF12_MF": MissionMode.FOCO_C5,
    "RJ1_OF13_MF": MissionMode.COMPLETO_PARCIAL,
    "RJ1_OF14_MF": MissionMode.COMPLETO_INTEGRAL,
    # 2S — M9.1 (foco_c2 desbloqueado).
    "RJ2_OF04_MF": MissionMode.FOCO_C2,    # Fontes e Citações
    "RJ2_OF06_MF": MissionMode.FOCO_C2,    # Da Notícia ao Artigo
    # 3S — 2026-05-02 (migration j0a1b2c3d4e5_seed_missoes_3s).
    # 11 das 15 oficinas do livro. Pendentes (ver
    # docs/redato/v3/oficinas_3s_status.md):
    # - OF02 (chat-only, sem produção avaliável)
    # - OF08 (foco_c1, modo ainda adiado — exige enum + tool schema
    #   + scoring branch + DEFAULT_MODEL; sessão dedicada futura)
    # - OF12, OF13 (jogos com cartas argumentativas — sistema 3S
    #   diferente do 1S)
    # Os Simulados (OF09/OF11/OF14/OF15) usam COMPLETO_INTEGRAL —
    # passam pelo path do FT BTBOS5VF (rollback REDATO_OF14_BACKEND=
    # claude também aplica).
    "RJ3_OF01_MF": MissionMode.COMPLETO_PARCIAL,  # Redato — corretor de bolso
    "RJ3_OF03_MF": MissionMode.FOCO_C2,           # Dossiê: Repertório + Análise
    "RJ3_OF04_MF": MissionMode.FOCO_C2,           # Dossiê: Tema + Problemática
    "RJ3_OF05_MF": MissionMode.FOCO_C5,           # Dossiê: Agentes + Proposta
    "RJ3_OF06_MF": MissionMode.FOCO_C5,           # Dossiê: Proposta Completa
    "RJ3_OF07_MF": MissionMode.COMPLETO_PARCIAL,  # Jogo do Corretor
    "RJ3_OF09_MF": MissionMode.COMPLETO_INTEGRAL, # Simulado 1
    "RJ3_OF10_MF": MissionMode.COMPLETO_PARCIAL,  # Revisão Cooperativa
    "RJ3_OF11_MF": MissionMode.COMPLETO_INTEGRAL, # Simulado 2 + IA
    "RJ3_OF14_MF": MissionMode.COMPLETO_INTEGRAL, # Simulado Final 1
    "RJ3_OF15_MF": MissionMode.COMPLETO_INTEGRAL, # Simulado Final 2
}


# Modelo default por modo. Sonnet 4.6 nos Modos Foco (problema mais
# restrito — avalia apenas 1 competência num parágrafo curto, modelo menor
# é suficiente). Opus 4.7 no Completo Parcial (avalia 4 competências, mais
# perto de redação completa). Override via REDATO_CLAUDE_MODEL afeta
# todos os modos uniformemente — útil pra eval mas não pra produção.
_DEFAULT_MODEL_BY_MODE: Dict[MissionMode, str] = {
    MissionMode.FOCO_C2: "claude-sonnet-4-6",   # M9.1 — mesmo padrão dos foco
    MissionMode.FOCO_C3: "claude-sonnet-4-6",
    MissionMode.FOCO_C4: "claude-sonnet-4-6",
    MissionMode.FOCO_C5: "claude-sonnet-4-6",
    MissionMode.COMPLETO_PARCIAL: "claude-opus-4-7",
    MissionMode.JOGO_REDACAO: "claude-sonnet-4-6",   # 5 comp + cartas + texto montado — Sonnet basta
    # COMPLETO_INTEGRAL não passa por este router — usa pipeline v2.
}


def _canonicalize(activity_id: str) -> str:
    """Normaliza separadores diversos (·, _, -, espaços) para `_` e
    extrai o prefixo `RJ1_OFXX_MF`. Tolerante a sufixo descritivo
    'Foco C3' / 'Correção 5 comp.' que o app pode anexar."""
    if not activity_id:
        return ""
    s = activity_id.strip()
    # Substitui middle dot (·, U+00B7), bullet, dash, dot, espaços por _
    s = re.sub(r"[·•\-\.\s]+", "_", s)
    s = s.upper()
    # Captura RJ1_OFXX_MF como prefixo
    m = re.match(r"^(RJ\d+_OF\d+_MF)", s)
    return m.group(1) if m else s


def resolve_mode(activity_id: Optional[str]) -> Optional[MissionMode]:
    """Resolve activity_id → MissionMode. Retorna None se não for missão REJ 1S."""
    if not activity_id:
        return None
    canon = _canonicalize(activity_id)
    return _MISSAO_TO_MODE.get(canon)


def is_mission_activity(activity_id: Optional[str]) -> bool:
    return resolve_mode(activity_id) is not None


def _missao_id_for(mode: MissionMode) -> str:
    """Inverso do _MISSAO_TO_MODE — devolve o PRIMEIRO missao_id que
    mapeia pro modo. Útil quando há relação 1:1 modo ↔ missão (foco_c3,
    foco_c4, foco_c5, completo_parcial).

    ATENÇÃO: para foco_c2 há 2 missões (RJ2_OF04_MF, RJ2_OF06_MF) —
    use `_canonicalize(activity_id)` em vez disso pra preservar a
    missão real. Manter esta função pra retrocompat (testes antigos
    podem chamar)."""
    for missao, m in _MISSAO_TO_MODE.items():
        if m == mode:
            return missao
    raise ValueError(f"sem missao_id para {mode}")


# ──────────────────────────────────────────────────────────────────────
# Construção do user_msg — função pura, testável
# ──────────────────────────────────────────────────────────────────────

def _build_user_msg(
    *,
    mode: MissionMode,
    activity_id: str,
    content: str,
    theme: str,
    pre_flags_block: str = "",
    palavra_dia_block: str = "",
) -> str:
    """Monta o user_msg enviado ao Claude. Função pura — testável sem
    mock de SDK.

    Bug que motivou (interaction id=3, 2026-04-29): foco_c2 tem 2
    missões no enum (RJ2_OF04_MF, RJ2_OF06_MF). O contexto da oficina
    em prompts.py menciona AMBAS, então o LLM podia escolher a errada.

    Fix: injetar header explícito com a `missao_id` específica no topo
    do user_msg + reforçar a instrução final. Defesa em profundidade
    porque o router também sobrescreve `tool_args['missao_id']` pós-
    resposta (ver `_enforce_missao_id`).
    """
    canonical = _canonicalize(activity_id)
    canonical_dotted = canonical.replace("_", "·") if canonical else activity_id
    tool = TOOLS_BY_MODE[mode.value]

    # Header explícito da missão a avaliar — reduz ambiguidade quando
    # o tool tem >1 valor no enum de `missao_id` (caso foco_c2).
    header = (
        f"## Missão a avaliar\n\n"
        f"Esta correção é especificamente da **`{canonical_dotted}`** "
        f"(missao_id no tool: `{canonical}`).\n\n"
        f"---\n\n"
    )

    return (
        f"{header}"
        f"{context_block_for(mode.value)}\n"
        f"---\n\n"
        f"{feedback_aluno_registro_block()}\n"
        f"---\n\n"
        f"## Texto do aluno\n\n"
        f"**Tema/contexto:** {theme}\n\n"
        f"```\n{content}\n```\n"
        f"{palavra_dia_block}"
        f"{pre_flags_block}"
        f"\n---\n\n"
        f"Avalie agora chamando a ferramenta `{tool['name']}` "
        f"com TODOS os campos obrigatórios. "
        f"**`missao_id` DEVE ser exatamente `{canonical}`** — é a "
        f"missão declarada no topo deste prompt."
    )


# ──────────────────────────────────────────────────────────────────────
# Defesa em profundidade — força missao_id correto se LLM divergir
# ──────────────────────────────────────────────────────────────────────

def _enforce_missao_id(
    tool_args: Dict[str, Any], activity_id: str,
) -> Optional[Dict[str, Any]]:
    """Garante que `tool_args['missao_id']` bate com a missão que o bot
    decidiu processar (vinda de activity_id).

    Bug que motivou (interaction id=3, 2026-04-29): bot resolveu
    RJ2·OF06·MF como atividade ativa, mas LLM emitiu RJ2_OF04_MF no
    tool_use porque o enum aceitava ambos. Resultado: campo
    `interactions.missao_id` (pelo bot) divergente do JSON
    `redato_output.missao_id` (do LLM) na mesma row.

    Fix: sobrescrever in-place. Caller loga divergência separadamente
    via `_log_missao_id_divergence` pra auditoria.

    Retorna None se não houve divergência, dict com info caso contrário.
    """
    expected = _canonicalize(activity_id)
    if not expected:
        return None
    emitted = tool_args.get("missao_id")
    if emitted == expected:
        return None
    tool_args["missao_id"] = expected
    return {"emitido": emitted, "esperado": expected}


# ──────────────────────────────────────────────────────────────────────
# Entry point — chamado por dev_offline._claude_grade_essay
# ──────────────────────────────────────────────────────────────────────

def grade_mission(data: Dict[str, Any]) -> Dict[str, Any]:
    """Grade um exercício REJ 1S em modo Foco ou Completo Parcial.

    Modo Completo Integral (OF14) NÃO passa por aqui — usa o pipeline v2
    padrão. Caller (`_claude_grade_essay`) decide o roteamento.

    Retorna o tool_args do schema correspondente, com chave extra
    `_mission` contendo metadata (mode, missao_id, pre_flags).
    """
    import anthropic

    activity_id = data.get("activity_id") or ""
    mode = resolve_mode(activity_id)
    if mode is None or mode == MissionMode.COMPLETO_INTEGRAL:
        raise ValueError(
            f"grade_mission não aceita activity_id={activity_id!r} (mode={mode}). "
            "Modos Foco/Parcial apenas; Completo Integral usa pipeline v2."
        )

    content = (data.get("content") or "").strip()
    theme = (data.get("theme") or "").strip() or "Tema livre"

    pre_flags = compute_pre_flags(mode.value, content)
    pre_flags_block = render_pre_flags_block(mode.value, pre_flags)

    palavra_dia_block = ""
    if mode == MissionMode.FOCO_C4:
        presentes = palavra_dia_presente(content)
        if presentes:
            palavra_dia_block = (
                "\n### Palavras do Dia detectadas no texto\n\n"
                + ", ".join(f"`{p}`" for p in presentes)
                + "\n\nAvalie se o uso é correto/adequado e marque "
                  "`palavra_dia_uso_errado` accordingly.\n"
            )

    user_msg = _build_user_msg(
        mode=mode, activity_id=activity_id, content=content, theme=theme,
        pre_flags_block=pre_flags_block, palavra_dia_block=palavra_dia_block,
    )

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    # Modelo é decidido pelo modo (foco=Sonnet, parcial=Opus). Override via
    # REDATO_MISSION_MODEL útil pra eval. REDATO_CLAUDE_MODEL é override do
    # pipeline v2 (OF14) e NÃO afeta os modos missions — isolamento
    # deliberado pra não acoplar custo dos foco com decisões de produção
    # do completo integral.
    model = os.getenv("REDATO_MISSION_MODEL") or _DEFAULT_MODEL_BY_MODE[mode]

    tool = TOOLS_BY_MODE[mode.value]
    message = client.messages.create(
        model=model,
        max_tokens=8000,
        # Nota: temperature=0 foi deprecada no Opus 4.7. A redução de
        # variabilidade vem agora do schema 0-100 + heurística de banda
        # inequívoca no PERSONA + caps semânticos.
        system=[
            {
                "type": "text",
                "text": system_prompt_for(mode.value),
                "cache_control": {"type": "ephemeral", "ttl": "1h"},
            },
        ],
        tools=[tool],
        tool_choice={"type": "tool", "name": tool["name"]},
        messages=[{"role": "user", "content": user_msg}],
    )

    # Extrai tool_use block correspondente.
    tool_args: Optional[Dict[str, Any]] = None
    for block in message.content:
        btype = getattr(block, "type", None)
        if btype == "tool_use" and getattr(block, "name", None) == tool["name"]:
            tool_args = dict(getattr(block, "input", {}) or {})
            break

    if tool_args is None:
        raise RuntimeError(
            f"Claude não invocou {tool['name']}. Blocos: "
            + ", ".join(str(getattr(b, "type", "?")) for b in message.content)
        )

    # Defesa em profundidade — força missao_id correto quando o LLM
    # diverge (caso foco_c2 com 2 valores no enum). Aplicar ANTES do
    # apply_override porque a nota emitida pode depender de qual
    # missão o LLM achou que estava avaliando — log preserva ambos.
    missao_id_div = _enforce_missao_id(tool_args, activity_id)
    if missao_id_div:
        _log_missao_id_divergence(
            mode.value, activity_id, missao_id_div, tool_args,
        )

    # Override determinístico: nota ENEM final é Python, não LLM. Reduz
    # oscilação onde scores REJ idênticos geravam notas distintas
    # (incidente real id=9/id=10, 2026-04-27).
    from redato_backend.missions.scoring import apply_override
    override_result = apply_override(mode.value, tool_args)
    if override_result["divergiu"]:
        _log_divergence(mode.value, activity_id, override_result, tool_args)

    # Anexa metadata pra debug/auditoria. Usa o canonicalizado do
    # activity_id (validado por resolve_mode acima) em vez de
    # _missao_id_for(mode) — porque foco_c2 tem 2 missões e precisamos
    # preservar qual delas foi de fato (OF04 vs OF06).
    tool_args["_mission"] = {
        "mode": mode.value,
        "missao_id": _canonicalize(activity_id),
        "activity_id": activity_id,
        "pre_flags": pre_flags,
        "model": model,
        "nota_emitida_llm": override_result["nota_emitida_llm"],
        "nota_final_python": override_result["nota_final_python"],
        "divergiu": override_result["divergiu"],
    }
    return tool_args


def _log_missao_id_divergence(
    mode: str, activity_id: str, divergence: Dict[str, Any],
    tool_args: Dict[str, Any],
) -> None:
    """Auditoria de divergência LLM × bot na chave `missao_id`.

    Mesmo arquivo `data/whatsapp/divergences.jsonl` do `_log_divergence`
    (notas), distinguido por `kind: "missao_id"`. Útil pra detectar
    oscilação do LLM quando há ambiguidade no enum (caso foco_c2)
    e calibrar o prompt se a frequência subir.
    """
    import json as _json
    from datetime import datetime as _datetime, timezone as _tz
    from pathlib import Path as _Path

    backend = _Path(__file__).resolve().parents[1]
    default_path = backend.parent / "data" / "whatsapp" / "divergences.jsonl"
    log_path = _Path(os.getenv("REDATO_DIVERGENCES_FILE", str(default_path)))
    log_path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "ts": _datetime.now(_tz.utc).isoformat(),
        "kind": "missao_id",
        "mode": mode,
        "activity_id": activity_id,
        "missao_id_emitido_llm": divergence.get("emitido"),
        "missao_id_esperado": divergence.get("esperado"),
        "rubrica_rej": tool_args.get("rubrica_rej"),
        "flags": tool_args.get("flags"),
    }
    try:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(_json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception as exc:  # noqa: BLE001
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "Falha ao registrar missao_id divergence: %r", exc
        )


def _log_divergence(
    mode: str, activity_id: str, override_result: Dict[str, Any],
    tool_args: Dict[str, Any],
) -> None:
    """Persiste divergência LLM × Python pra auditoria. Append-only JSONL.

    Local: data/whatsapp/divergences.jsonl (relativo ao backend).
    Override via env REDATO_DIVERGENCES_FILE.
    """
    import json as _json
    from datetime import datetime as _datetime, timezone as _tz
    from pathlib import Path as _Path

    backend = _Path(__file__).resolve().parents[1]
    default_path = backend.parent / "data" / "whatsapp" / "divergences.jsonl"
    log_path = _Path(os.getenv("REDATO_DIVERGENCES_FILE", str(default_path)))
    log_path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "ts": _datetime.now(_tz.utc).isoformat(),
        "kind": "nota",   # M9.2 — distingue de divergências de missao_id
        "mode": mode,
        "activity_id": activity_id,
        "nota_emitida_llm": override_result["nota_emitida_llm"],
        "nota_final_python": override_result["nota_final_python"],
        "rubrica_rej": tool_args.get("rubrica_rej"),
        "flags": tool_args.get("flags"),
        "articulacao_a_discussao": tool_args.get("articulacao_a_discussao"),
        "detalhe_notas_emitidas": override_result.get("detalhe_notas_emitidas"),
        "detalhe_notas_python": override_result.get("detalhe_notas_python"),
    }
    try:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(_json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception as exc:  # noqa: BLE001
        # Não quebra grade_mission por falha de log.
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "Falha ao registrar divergência: %r", exc
        )


# ──────────────────────────────────────────────────────────────────────
# Fase 2 passo 5 — entry point pro modo jogo_redacao
# ──────────────────────────────────────────────────────────────────────
#
# Formato de input separado de `grade_mission` porque jogo_redacao
# precisa de muito mais contexto: catálogo do minideck (104 cartas) +
# cartas escolhidas pelo grupo + texto montado + reescrita autoral.
# O caller (bot quando aluno em REVISANDO_TEXTO_MONTADO) carrega
# tudo do DB via `whatsapp/portal_link.py` e passa snapshots aqui.
#
# Esta função NÃO toca DB — pura. Caller persiste `redato_output`
# em `reescritas_individuais.redato_output` depois.

def _build_jogo_redacao_user_msg(
    *,
    nome_humano_tema: str,
    cartas_lacuna_full: list,
    codigos_escolhidos: list,
    estruturais_por_codigo: dict,
    lacunas_por_codigo: dict,
    texto_montado: str,
    reescrita_texto: str,
) -> str:
    """Monta o user_msg pro modo jogo_redacao. Função pura — testável
    sem mock de SDK.

    Estrutura (ordem importa pro Claude):
    1. Header: missão a avaliar
    2. Contexto da oficina (rubrica jogo_redacao)
    3. CARTAS DO MINIDECK (catálogo completo do tema, ~104 cartas)
    4. CARTAS QUE O GRUPO ESCOLHEU (com placeholders preenchidos)
    5. TEXTO MONTADO (redação cooperativa)
    6. REESCRITA INDIVIDUAL (texto a avaliar)
    7. Instruções finais explicitas
    """
    tool = TOOLS_BY_MODE[MissionMode.JOGO_REDACAO.value]

    header = (
        f"## Missão a avaliar\n\n"
        f"Modo: jogo_redacao | Tema: {nome_humano_tema} | "
        f"Atividade: RJ2·OF13·MF\n\n"
        f"---\n\n"
    )

    # Contexto da rubrica
    contexto = context_block_for(MissionMode.JOGO_REDACAO.value)

    # Catálogo do minideck — ~8 KB. Cache TTL=1h vai cobrir múltiplos
    # alunos do mesmo grupo + grupos diferentes do mesmo tema.
    bloco_catalogo = render_minideck_block(
        nome_humano_tema, cartas_lacuna_full,
    )

    # Cartas escolhidas — ~1 KB. Varia por partida.
    bloco_escolhidas = render_cartas_escolhidas_block(
        codigos_escolhidos,
        estruturais_por_codigo,
        lacunas_por_codigo,
    )

    return (
        f"{header}"
        f"{contexto}\n"
        f"---\n\n"
        f"{feedback_aluno_registro_block()}\n"
        f"---\n\n"
        f"{bloco_catalogo}\n"
        f"---\n\n"
        f"{bloco_escolhidas}\n"
        f"---\n\n"
        f"### TEXTO MONTADO (redação cooperativa expandida)\n\n"
        f"```\n{texto_montado}\n```\n\n"
        f"---\n\n"
        f"### REESCRITA INDIVIDUAL (texto a avaliar)\n\n"
        f"```\n{reescrita_texto}\n```\n\n"
        f"---\n\n"
        f"## Avaliação\n\n"
        f"Avalie agora chamando a ferramenta `{tool['name']}` com "
        f"TODOS os campos obrigatórios.\n\n"
        f"**Lembre-se:**\n"
        f"1. As 5 competências ENEM avaliam A REESCRITA AUTORAL — "
        f"não o TEXTO MONTADO.\n"
        f"2. `transformacao_cartas` (0-100) mede quanto a reescrita "
        f"superou o esqueleto. Use o continuum, não só extremos.\n"
        f"3. `sugestoes_cartas_alternativas` é DINÂMICA (0-2 itens). "
        f"Lista vazia é feedback positivo legítimo. NÃO force "
        f"sugestões se o grupo escolheu bem.\n"
        f"4. `tema_minideck` no output deve ser exatamente o slug "
        f"que veio no header desta missão (ex.: 'saude_mental').\n"
        f"5. `feedback_aluno` (acertos + ajustes) DEVE seguir a "
        f"guideline 'Registro do feedback_aluno' acima — vocabulário "
        f"acessível, trecho específico citado, caminho concreto pra "
        f"melhorar. `feedback_professor` continua técnico."
    )


def grade_jogo_redacao(data: Dict[str, Any]) -> Dict[str, Any]:
    """Grade uma reescrita individual no modo jogo_redacao.

    `data` (dict) precisa conter:
        - tema_minideck (str): slug, ex.: "saude_mental"
        - nome_humano_tema (str): display, ex.: "Saúde Mental"
        - cartas_lacuna_full (list): catálogo do minideck (objetos
          com .codigo, .tipo, .conteudo). Caller carrega via
          `portal_link.carregar_contexto_validacao(minideck_id)`.
        - codigos_escolhidos (list[str]): codes que o grupo escolheu
        - estruturais_por_codigo (dict): catálogo das estruturais
        - lacunas_por_codigo (dict): catálogo das lacunas do minideck
          (mesmas 104 cartas de cartas_lacuna_full mas indexadas)
        - texto_montado (str): redação cooperativa expandida
        - reescrita_texto (str): texto autoral do aluno (a avaliar)

    Retorna `tool_args` com:
        - 5 competências ENEM, nota_total_enem
        - transformacao_cartas, sugestoes_cartas_alternativas
        - flags do jogo
        - feedback_aluno + feedback_professor
        - `_mission` metadata (mode, model, override info)

    Levanta:
        - RuntimeError se Claude não invocar o tool
        - anthropic.* exceptions (timeout, rate limit) propagadas
          pro caller decidir UX
    """
    import anthropic

    # Validações mínimas — caller (bot) deve garantir, mas defesa.
    nome_tema = (data.get("nome_humano_tema") or "").strip()
    tema_slug = (data.get("tema_minideck") or "").strip().lower()
    reescrita = (data.get("reescrita_texto") or "").strip()
    texto_montado = (data.get("texto_montado") or "").strip()
    if not nome_tema or not tema_slug or not reescrita:
        raise ValueError(
            "grade_jogo_redacao: campos obrigatórios vazios "
            "(nome_humano_tema, tema_minideck, reescrita_texto)",
        )

    user_msg = _build_jogo_redacao_user_msg(
        nome_humano_tema=nome_tema,
        cartas_lacuna_full=data.get("cartas_lacuna_full") or [],
        codigos_escolhidos=data.get("codigos_escolhidos") or [],
        estruturais_por_codigo=data.get("estruturais_por_codigo") or {},
        lacunas_por_codigo=data.get("lacunas_por_codigo") or {},
        texto_montado=texto_montado,
        reescrita_texto=reescrita,
    )

    model = (
        os.getenv("REDATO_MISSION_MODEL")
        or _DEFAULT_MODEL_BY_MODE[MissionMode.JOGO_REDACAO]
    )
    tool = TOOLS_BY_MODE[MissionMode.JOGO_REDACAO.value]

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model=model,
        max_tokens=8000,
        # System + catálogo cacheados (TTL=1h). Quando outro aluno do
        # mesmo grupo (ou outro grupo do mesmo tema) submeter, cache
        # hit no system+catálogo (~10 KB) e só user_msg variável paga.
        system=[
            {
                "type": "text",
                "text": system_prompt_for(MissionMode.JOGO_REDACAO.value),
                "cache_control": {"type": "ephemeral", "ttl": "1h"},
            },
        ],
        tools=[tool],
        tool_choice={"type": "tool", "name": tool["name"]},
        messages=[{"role": "user", "content": user_msg}],
    )

    tool_args: Optional[Dict[str, Any]] = None
    for block in message.content:
        btype = getattr(block, "type", None)
        if btype == "tool_use" and getattr(block, "name", None) == tool["name"]:
            tool_args = dict(getattr(block, "input", {}) or {})
            break
    if tool_args is None:
        raise RuntimeError(
            f"Claude não invocou {tool['name']}. Blocos: "
            + ", ".join(str(getattr(b, "type", "?")) for b in message.content)
        )

    # Garante que o `tema_minideck` no output bate com o slug que veio
    # no input — defesa contra Claude inventando outro slug.
    if tool_args.get("tema_minideck") != tema_slug:
        tool_args["tema_minideck"] = tema_slug

    # Override determinístico via scoring (caps por flags).
    from redato_backend.missions.scoring import apply_override
    override_result = apply_override(
        MissionMode.JOGO_REDACAO.value, tool_args,
    )

    # Validação adicional das sugestões (defesa contra Claude
    # alucinar codes que não estão no minideck).
    _sanear_sugestoes(
        tool_args,
        codigos_escolhidos=data.get("codigos_escolhidos") or [],
        lacunas_por_codigo=data.get("lacunas_por_codigo") or {},
    )

    tool_args["_mission"] = {
        "mode": MissionMode.JOGO_REDACAO.value,
        "tema_minideck": tema_slug,
        "model": model,
        "nota_emitida_llm": override_result.get("nota_emitida_llm"),
        "nota_final_python": override_result.get("nota_final_python"),
        "divergiu": override_result.get("divergiu", False),
    }
    return tool_args


def _sanear_sugestoes(
    tool_args: Dict[str, Any],
    *,
    codigos_escolhidos: list,
    lacunas_por_codigo: dict,
) -> None:
    """Filtra `sugestoes_cartas_alternativas` removendo entries
    inválidos (in-place):
    - codigo_original tem que estar entre os codes do grupo
    - codigo_sugerido tem que estar no minideck (catálogo)
    - codigos diferentes (não sugerir o que já foi escolhido)
    - mesmo TIPO entre original e sugerida

    Claude pode alucinar codes; defesa-em-camada antes de retornar
    pro caller / persistir em DB.
    """
    sug = tool_args.get("sugestoes_cartas_alternativas")
    if not isinstance(sug, list):
        tool_args["sugestoes_cartas_alternativas"] = []
        return

    codes_grupo = set(codigos_escolhidos)
    saneadas: list = []
    for item in sug:
        if not isinstance(item, dict):
            continue
        orig = (item.get("codigo_original") or "").upper()
        sugerida = (item.get("codigo_sugerido") or "").upper()
        motivo = (item.get("motivo") or "").strip()
        if not orig or not sugerida or not motivo:
            continue
        if orig == sugerida:
            continue
        if orig not in codes_grupo:
            continue
        if sugerida not in lacunas_por_codigo:
            continue
        # Mesmo tipo: só compara P/R/K/A/AC/ME/F entre lacunas.
        # E## (estruturais) não devem aparecer aqui — sugestão é só
        # de cartas temáticas.
        orig_lac = lacunas_por_codigo.get(orig)
        sug_lac = lacunas_por_codigo.get(sugerida)
        if orig_lac is None or sug_lac is None:
            continue
        if orig_lac.tipo != sug_lac.tipo:
            continue
        saneadas.append({
            "codigo_original": orig,
            "codigo_sugerido": sugerida,
            "motivo": motivo,
        })
        if len(saneadas) >= 2:
            break  # maxItems=2 do schema

    tool_args["sugestoes_cartas_alternativas"] = saneadas
