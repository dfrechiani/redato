"""Grader OF14 (modo completo_integral) via GPT fine-tuned.

Modelo: ``ft:gpt-4.1-2025-04-14:redato:redato-enem:BTBOS5VF``
(treinado Apr/2025 — 2.348M tokens, 10 epochs, batch 3, LR 0.95).

Backend de OF14 desde 2026-04-30 baseado em:
- A/B 30/abr (commit 174ceab): FT 21.5% ±40 vs Sonnet 19.3% vs Opus 14.0%
- Experimento prompt-enriched (commit 6080d4d): FT 28.5% ±40, 100% parse_ok,
  custo $0.05/redação, latência 13.8s
- Investigação MIGRATION_FT_OF14_AUDIT.md: gap = 0 campos ativos perdidos
  no `redato_frontend` prod (consome só `cN_audit.nota`)

Schema de retorno (subset audit-enriched do OF14):

    {
      "c1_audit": {"nota": int, "feedback_text": str, "evidencias": [{"trecho": str, "comentario": str}]},
      "c2_audit": { ... },
      ...
      "c5_audit": { ... }
    }

Compatível com `_persist_grading_to_bq` em ``dev_offline.py`` — esse helper
é defensive contra schema parcial (`_dict_or_empty` em campos faltantes).
Os campos top-level do schema v2 (`essay_analysis`, `preanulation_checks`,
`priorization`, `meta_checks`, `feedback_text` solto) **não são retornados**.
Frontend prod (`redato_frontend`) já não os consome pra OF14, então não há
regressão visível.

Política de erro: se OpenAI falhar (timeout, key missing, rate limit) ou
o parser não casar, levanta `OpenAIFTGradingError`. ``dev_offline.py``
captura e faz fallback automático pro Claude Sonnet 4.6 v2 — graceful
degradation. Operador pode forçar fallback permanente via
`REDATO_OF14_BACKEND=claude` (sem deploy).

Dívida técnica: parser ``parse_audit_response`` foi copiado de
``scripts/ab_models/run_ft_with_audit.py`` em vez de extraído pra módulo
compartilhado, porque scripts/ é experimental e standalone (não importa
do backend). Quando o experimento for arquivado, mover parser pra cá
como fonte única.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple


# Logger pro adapter. Em prod (Railway), `print()` em pipeline async
# tem chance de ser silenciado/buferizado — logger.exception garante
# stack trace + flush nos handlers configurados.
logger = logging.getLogger(__name__)


# Modelo FT vencedor do A/B 30/abr. Hardcoded — trocar exige re-treino + A/B.
# Override via REDATO_FT_MODEL pra testes/staging com modelo alternativo.
DEFAULT_FT_MODEL = "ft:gpt-4.1-2025-04-14:redato:redato-enem:BTBOS5VF"

# Hyperparâmetros do experimento que deu 28.5% ±40 (commit 6080d4d).
TEMPERATURE = 0
MAX_TOKENS = 4000  # briefing pediu 4000; experimento usou 6000 mas 4000 cabe
                   # no audit típico (3 evidências por competência)
DEFAULT_TIMEOUT_SECONDS = 60.0


# Schema retornado: 5 cN_audit, cada um com {nota, feedback_text, evidencias}.
COMPETENCIAS = ("c1_audit", "c2_audit", "c3_audit", "c4_audit", "c5_audit")
CAMPOS_OBRIGATORIOS = ("nota", "feedback_text", "evidencias")
NOTAS_VALIDAS = (0, 40, 80, 120, 160, 200)


class OpenAIFTGradingError(RuntimeError):
    """Levantada quando o FT falha ou retorna payload não-parseável.

    Carrega o ``raw_output`` original (caso houver) pra debug —
    ``dev_offline.py`` loga + faz fallback pro Claude.
    """

    def __init__(
        self,
        msg: str,
        *,
        raw_output: Optional[str] = None,
        parse_status: Optional[str] = None,
        missing_fields: Optional[List[str]] = None,
    ) -> None:
        super().__init__(msg)
        self.raw_output = raw_output
        self.parse_status = parse_status
        self.missing_fields = missing_fields or []


# ──────────────────────────────────────────────────────────────────────
# Prompt enriquecido — idêntico ao do experimento 6080d4d
# ──────────────────────────────────────────────────────────────────────

USER_MSG_TEMPLATE = """TEMA: {tema}

REDAÇÃO DO ALUNO:
\"\"\"
{texto}
\"\"\"

Avalie a redação acima pelas 5 competências ENEM. Retorne EXCLUSIVAMENTE \
um JSON com esta estrutura (sem texto antes/depois, sem markdown fence):

{{
  "c1_audit": {{
    "nota": <0|40|80|120|160|200>,
    "feedback_text": "<2-3 parágrafos explicando a nota; mencione pontos \
fortes E pontos a melhorar; tom construtivo, voz de professor>",
    "evidencias": [
      {{"trecho": "<citação literal do texto>", "comentario": "<por que \
esse trecho é problema ou acerto>"}}
    ]
  }},
  "c2_audit": {{...mesmo formato...}},
  "c3_audit": {{...mesmo formato...}},
  "c4_audit": {{...mesmo formato...}},
  "c5_audit": {{...mesmo formato...}}
}}

Diretrizes:
- "nota" precisa ser exatamente um dos valores: 0, 40, 80, 120, 160 ou 200
- "feedback_text" tem 2-3 parágrafos (não 1 frase). Português natural, \
sem jargão acadêmico. Aluno deve entender.
- "evidencias" tem 1-3 itens por competência. Use trechos LITERAIS do \
texto (copy/paste de partes da redação).
- NÃO retorne nenhum texto fora do JSON. NÃO use markdown ```json fence.
"""


# ──────────────────────────────────────────────────────────────────────
# Parser semantic-validated (copiado de scripts/ab_models/run_ft_with_audit.py)
# ──────────────────────────────────────────────────────────────────────

def parse_audit_response(
    raw: str,
) -> Tuple[Optional[Dict[str, Any]], str, List[str]]:
    """Tenta extrair audit estruturado da resposta do FT.

    Retorna ``(audit_dict, parse_status, missing_fields)``:

    - ``parse_status="ok"``: JSON válido + 5 cN_audit completos com nota
      válida (em NOTAS_VALIDAS), feedback_text não-vazio e evidencias
      como lista. ``missing_fields`` vazio.
    - ``parse_status="partial"``: JSON válido com as 5 chaves cN_audit,
      mas algum campo interno faltando ou com tipo errado. ``missing_fields``
      lista os problemas (ex.: ``["c2_audit.nota:fora_da_escala_150"]``).
    - ``parse_status="failed"``: JSON não parseou ou faltam chaves cN_audit
      essenciais. ``missing_fields`` traz uma indicação ("json_não_parseou",
      "resposta_vazia").

    Caller decide: aceita partial (notas válidas + tudo presente) ou só ok.
    """
    if not raw or not raw.strip():
        return None, "failed", ["resposta_vazia"]

    audit = _try_balanced_json(raw)
    if audit is None:
        return None, "failed", ["json_não_parseou"]

    missing: List[str] = []
    for c in COMPETENCIAS:
        if c not in audit:
            missing.append(c)
            continue
        block = audit[c]
        if not isinstance(block, dict):
            missing.append(f"{c}:tipo_inválido")
            continue
        for campo in CAMPOS_OBRIGATORIOS:
            if campo not in block:
                missing.append(f"{c}.{campo}")
                continue
            v = block[campo]
            if campo == "nota":
                if not isinstance(v, (int, float)):
                    missing.append(f"{c}.nota:tipo")
                elif int(v) not in NOTAS_VALIDAS:
                    missing.append(f"{c}.nota:fora_da_escala_{v}")
            elif campo == "feedback_text":
                if not isinstance(v, str) or not v.strip():
                    missing.append(f"{c}.feedback_text:vazio")
            elif campo == "evidencias":
                if not isinstance(v, list):
                    missing.append(f"{c}.evidencias:tipo")

    if not missing:
        return audit, "ok", []
    if all(c in audit and isinstance(audit[c], dict) for c in COMPETENCIAS):
        return audit, "partial", missing
    return audit, "partial", missing


def _try_balanced_json(raw: str) -> Optional[Dict[str, Any]]:
    """Estratégias, do mais provável ao menos:
      1. Texto inteiro como JSON.
      2. Maior bloco ``{...}`` balanceado (cobre nested).
      3. Strip de markdown fences ``\\`\\`\\`json ... \\`\\`\\```.
    """
    candidates: List[str] = []
    stripped = raw.strip()

    # Markdown fence (caso o FT ignore a instrução)
    fence_match = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        stripped, re.DOTALL,
    )
    if fence_match:
        candidates.append(fence_match.group(1))

    if stripped.startswith("{"):
        candidates.append(stripped)

    # Maior bloco {...} balanceado
    stack = 0
    start = -1
    for i, ch in enumerate(raw):
        if ch == "{":
            if stack == 0:
                start = i
            stack += 1
        elif ch == "}":
            if stack > 0:
                stack -= 1
                if stack == 0 and start >= 0:
                    candidates.append(raw[start:i + 1])
                    start = -1

    seen: set = set()
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        try:
            data = json.loads(cand)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict):
            return data
    return None


# ──────────────────────────────────────────────────────────────────────
# Cliente OpenAI — injetável pra testes (factory pattern)
# ──────────────────────────────────────────────────────────────────────

ClientFactory = Callable[[], Any]


def _default_client_factory() -> Any:
    """Cria cliente OpenAI default lendo OPENAI_API_KEY do env.

    Levanta ``OpenAIFTGradingError`` com mensagem clara se SDK ou key
    faltarem (fácil de diagnosticar em logs Railway)."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise OpenAIFTGradingError(
            "OPENAI_API_KEY não setada — necessária pra OF14 com "
            "REDATO_OF14_BACKEND=ft. Setar no Railway dashboard ou "
            "rolar pra REDATO_OF14_BACKEND=claude pra rollback."
        )
    try:
        from openai import OpenAI
    except ImportError as e:
        raise OpenAIFTGradingError(
            "OpenAI SDK não instalado. Add `openai>=1.50` ao "
            "requirements.txt e re-rode `pip install -r requirements.txt`."
        ) from e
    return OpenAI(api_key=key)


# ──────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────

def grade_of14_with_ft(
    *,
    content: str,
    theme: str,
    client_factory: ClientFactory = _default_client_factory,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Avalia 1 redação OF14 chamando o FT BTBOS5VF.

    Args:
        content: texto da redação do aluno.
        theme: tema da proposta (título).
        client_factory: factory que retorna cliente OpenAI. Default cria
            via OPENAI_API_KEY do env. Tests injetam mock.
        timeout_seconds: timeout da chamada (default 60s; FT real
            normalmente responde em 13-15s pra audit completo).

    Returns:
        ``Dict[str, Any]`` com 5 cN_audit (nota + feedback_text +
        evidencias). Compatível com `_persist_grading_to_bq` em
        dev_offline.py — campos faltantes (priorization, meta_checks,
        etc.) ficam ausentes e o helper trata defensivamente.

    Raises:
        OpenAIFTGradingError: cliente não criado, timeout, parser não casa,
        ou tipo inválido em algum campo crítico (ex.: nota=null). NÃO
        retorna dict parcial — caller deve fazer fallback.
    """
    user_msg = USER_MSG_TEMPLATE.format(tema=theme, texto=content)
    model = os.getenv("REDATO_FT_MODEL", DEFAULT_FT_MODEL)

    try:
        client = client_factory()
    except OpenAIFTGradingError:
        # Já é o tipo certo (key missing, SDK ausente). Loga + repropaga
        # — caller (dev_offline) faz fallback graceful.
        logger.exception("FT client_factory failed (likely OPENAI_API_KEY missing)")
        raise

    logger.info(
        "calling FT %s, content_len=%d, theme_len=%d, timeout=%.0fs",
        model, len(content), len(theme), timeout_seconds,
    )

    started = time.time()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": user_msg},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            timeout=timeout_seconds,
        )
    except Exception as exc:  # noqa: BLE001
        # Timeout, rate limit, modelo inexistente, autenticação inválida,
        # rede caindo. Stack trace via logger.exception garante visibilidade
        # em Railway (print() silencia em pipelines async).
        logger.exception("FT call failed: %s", exc)
        raise OpenAIFTGradingError(
            f"chamada FT falhou: {type(exc).__name__}: {exc}"
        ) from exc

    elapsed_ms = int((time.time() - started) * 1000)

    if not getattr(response, "choices", None):
        logger.error(
            "FT returned no choices in %dms (resposta vazia da OpenAI)",
            elapsed_ms,
        )
        raise OpenAIFTGradingError(
            "FT retornou sem choices (resposta vazia da OpenAI)"
        )

    raw_text = response.choices[0].message.content or ""
    audit, status, missing = parse_audit_response(raw_text)

    logger.info(
        "FT response in %dms, parse_status=%s, raw_len=%d",
        elapsed_ms, status, len(raw_text),
    )

    # Aceita ok ou partial (com missing leve, ex.: evidencias ausente em
    # 1 competência). Rejeita failed (JSON não parseou ou faltam todas as
    # 5 cN_audit) e partial com nota inválida.
    nota_invalida_critica = any(
        ":fora_da_escala" in m or ".nota:tipo" in m
        for m in missing
    )
    if status == "failed" or nota_invalida_critica:
        # logger.error em vez de exception — não há exceção em
        # parse_audit_response, só status semântico. Truncate raw pra
        # não inundar log. Stack trace virá do raise abaixo se caller
        # logar com logger.exception.
        logger.error(
            "FT parse rejected (status=%s, missing=%s, raw[:200]=%r)",
            status, missing[:5], raw_text[:200],
        )
        raise OpenAIFTGradingError(
            f"parser não casou audit válido. status={status}, "
            f"missing={missing[:5]}",
            raw_output=raw_text,
            parse_status=status,
            missing_fields=missing,
        )

    # Normaliza pra retornar APENAS as 5 chaves cN_audit (audit pode ter
    # campos extras se o FT inventou — ignoramos).
    out: Dict[str, Any] = {}
    for c in COMPETENCIAS:
        bloco = audit[c]  # type: ignore[index]
        out[c] = {
            "nota": int(bloco["nota"]),
            "feedback_text": str(bloco.get("feedback_text") or "").strip(),
            "evidencias": [
                _normalize_evidencia(e)
                for e in (bloco.get("evidencias") or [])
                if isinstance(e, dict)
            ],
        }

    # Bug do portal (01/05): redato_frontend lê tool_args["nota_total"]
    # direto sem fallback de soma — quando FT omitia o campo (frequente
    # — não era exigido pelo prompt de treino), portal mostrava
    # "—/1000". Calcula soma canônica das 5 cN_audit.nota e sobrescreve
    # qualquer valor que o FT tenha emitido. Soma é fonte da verdade
    # (FT pode dar inconsistência tipo c1=160 c2=160 ... mas
    # nota_total=500 — modelo erra aritmética). Discrepâncias logam
    # em DEBUG pra eventual análise de qualidade do FT, sem ruído INFO.
    soma = sum(out[c]["nota"] for c in COMPETENCIAS)
    nota_total_ft = audit.get("nota_total") if isinstance(audit, dict) else None
    if (isinstance(nota_total_ft, (int, float))
            and int(nota_total_ft) != soma):
        logger.debug(
            "FT nota_total inconsistente: ft=%s, soma=%d (sobrescrevendo com soma)",
            nota_total_ft, soma,
        )
    out["nota_total"] = soma

    return out


def _normalize_evidencia(ev: Dict[str, Any]) -> Dict[str, str]:
    return {
        "trecho": str(ev.get("trecho") or "").strip(),
        "comentario": str(ev.get("comentario") or "").strip(),
    }


def _system_prompt() -> str:
    """System prompt do FT.

    Em produção usa `_SYSTEM_PROMPT_BASE` de ``dev_offline.py`` (mesmo
    treino). Lazy import pra evitar carregar dev_offline durante import
    do módulo (dev_offline tem ~3500 linhas e várias dependências).

    Tests injetam ``client_factory`` mockado que ignora o system prompt,
    então não exercitam esse path — não há ciclo de import.
    """
    from redato_backend.dev_offline import _SYSTEM_PROMPT_BASE
    return _SYSTEM_PROMPT_BASE
