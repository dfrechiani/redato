"""Pipeline de inferência de diagnóstico cognitivo via GPT-4.1.

Recebe:
    - texto da redação (já transcrito do OCR)
    - redato_output (saída da correção, com cN_audit)
    - tema da proposta

Devolve:
    Dict estruturado com 40 descritores classificados (status =
    dominio | lacuna | incerto), evidências por descritor, top-5
    lacunas prioritárias, resumo qualitativo + recomendação breve.

Política de erro:
    Falhas (timeout OpenAI, key missing, schema inválido, parser
    falha) retornam None — caller registra log e segue sem persistir
    diagnóstico. NÃO bloqueia o pipeline principal de correção.

Modelo padrão:
    gpt-4.1-2025-04-14 (base, não FT). Override via env
    REDATO_DIAGNOSTICO_MODELO. Pricing usado pra estimativa de custo
    bate com a tabela OpenAI vigente em 2026-05.

Forçar schema via tool_use:
    Em vez de pedir JSON cru e parsear, declaramos uma tool
    `registrar_diagnostico` com schema obrigatório (40 itens, IDs
    válidos, status enum, etc.). OpenAI valida o schema antes de
    devolver — reduz drasticamente o "schema drift" que pegamos no
    FT grader (parser_status=partial em ~5% dos casos).
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from redato_backend.diagnostico.descritores import (
    Descritor,
    descritores_por_id,
    load_descritores,
    versao_carregada,
)

logger = logging.getLogger(__name__)


SCHEMA_VERSION = "1.0"

DEFAULT_MODEL = "gpt-4.1-2025-04-14"
"""GPT-4.1 base. Daniel decidiu usar base (não FT) — descritor é
genérico, não exige fine-tuning."""

DEFAULT_TIMEOUT_SECONDS = 90.0
"""Timeout generoso pq tool_use com 40 itens custa mais output tokens
que o FT grader (5 cN_audit). Latência típica observada: 10-15s."""

TEMPERATURE = 0
"""Determinístico — diagnóstico não é criativo, é classificatório."""

MAX_OUTPUT_TOKENS = 8000
"""40 descritores × ~150 tokens por entry (id + status + 3 evidências
+ confiança) + lacunas + resumo + recomendação = ~6500 tokens. Margem
de 23% pra evitar truncamento."""

# Pricing GPT-4.1 (USD por 1M tokens, tabela OpenAI vigente em 2026-05).
# Mantido em const pra ser fácil ajustar quando OpenAI muda preço.
PRICE_INPUT_PER_MILLION_USD = 2.0
PRICE_OUTPUT_PER_MILLION_USD = 8.0


VALID_STATUS = {"dominio", "lacuna", "incerto"}
VALID_CONFIANCA = {"alta", "media", "baixa"}
MAX_EVIDENCIAS = 3
MAX_LACUNAS_PRIORITARIAS = 5


# ──────────────────────────────────────────────────────────────────────
# Cliente OpenAI — injetável pra tests (factory pattern)
# ──────────────────────────────────────────────────────────────────────

ClientFactory = Callable[[], Any]


class DiagnosticoError(RuntimeError):
    """Falha na inferência. Carrega contexto pra debug."""

    def __init__(
        self,
        msg: str,
        *,
        raw_output: Optional[str] = None,
        latencia_ms: Optional[int] = None,
    ) -> None:
        super().__init__(msg)
        self.raw_output = raw_output
        self.latencia_ms = latencia_ms


def _default_client_factory() -> Any:
    """Cliente OpenAI default — lê OPENAI_API_KEY do env.

    Mesma estratégia do `openai_ft_grader._default_client_factory`.
    Erros viram DiagnosticoError com mensagem clara pra log Railway.
    """
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise DiagnosticoError(
            "OPENAI_API_KEY não setada — diagnóstico cognitivo desabilitado. "
            "Setar no Railway dashboard ou desabilitar via "
            "REDATO_DIAGNOSTICO_HABILITADO=false."
        )
    try:
        from openai import OpenAI
    except ImportError as e:
        raise DiagnosticoError(
            "OpenAI SDK não instalado (necessário openai>=1.50)."
        ) from e
    return OpenAI(api_key=key)


# ──────────────────────────────────────────────────────────────────────
# Prompt construction
# ──────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "Você é um especialista em avaliação de redação ENEM. Sua tarefa é "
    "fazer DIAGNÓSTICO COGNITIVO: para cada um dos 40 descritores "
    "observáveis fornecidos (8 por competência C1-C5), classificar se o "
    "aluno demonstra domínio, tem lacuna, ou se há sinal insuficiente "
    "pra decidir.\n\n"
    "Princípios:\n"
    "1. Use EVIDÊNCIA TEXTUAL. Cite trechos literais da redação que "
    "comprovem cada classificação.\n"
    "2. Diferencie 'lacuna' (erro/ausência clara) de 'incerto' (sinal "
    "ambíguo ou texto curto demais pra avaliar).\n"
    "3. Considere o redato_output (notas + feedback INEP) como contexto, "
    "mas avalie INDEPENDENTEMENTE o texto da redação por descritor — "
    "o redato_output usa rubrica INEP de 5 níveis, descritores são mais "
    "granulares.\n"
    "4. Confiança 'alta' quando há 2+ evidências claras; 'media' quando "
    "há 1 evidência ou padrão sutil; 'baixa' quando texto não fornece "
    "sinal suficiente.\n"
    "5. Lacunas prioritárias (top 5) ordenadas por impacto pedagógico — "
    "competências de baixa nota pesam mais.\n"
    "6. Resumo qualitativo: 3-5 linhas em português natural, voz de "
    "professor falando pro outro professor (não pro aluno).\n"
    "7. Recomendação breve: 2-3 linhas apontando reforço prioritário."
)


def _build_user_prompt(
    *, texto_redacao: str, redato_output: Dict[str, Any],
    tema: str, descritores: List[Descritor],
) -> str:
    """Monta o prompt do usuário com texto numerado por linha,
    redato_output formatado e a lista dos 40 descritores."""
    # Numera linhas (1-indexed) pra LLM citar evidência precisa.
    linhas = texto_redacao.splitlines() if texto_redacao else []
    texto_numerado = "\n".join(
        f"{i+1:02d}| {linha}" for i, linha in enumerate(linhas)
    )

    # Formata redato_output em tabela legível. Cobre os formatos do
    # FT grader (cN_audit) e do completo_parcial (notas_enem).
    redato_resumo = _formatar_redato_output(redato_output or {})

    # Lista os 40 descritores no prompt — LLM precisa ver definição +
    # indicador_lacuna + exemplo pra classificar com fidelidade.
    descs_txt = "\n".join(
        f"  [{d.id}] {d.nome} (categoria INEP: {d.categoria_inep})\n"
        f"      DEFINIÇÃO: {d.definicao}\n"
        f"      INDICADOR DE LACUNA: {d.indicador_lacuna}\n"
        f"      EXEMPLO DE LACUNA: {d.exemplo_lacuna}"
        for d in descritores
    )

    return (
        f"TEMA DA PROPOSTA:\n{tema}\n\n"
        f"REDAÇÃO DO ALUNO (linhas numeradas pra você citar evidência):\n"
        f"\"\"\"\n{texto_numerado}\n\"\"\"\n\n"
        f"SAÍDA DO CORRETOR (redato_output, contexto):\n{redato_resumo}\n\n"
        f"40 DESCRITORES OBSERVÁVEIS (8 por competência, INEP-aligned):\n"
        f"{descs_txt}\n\n"
        f"Para CADA UM dos 40 descritores acima, classifique status, "
        f"liste 0-3 evidências textuais (trechos literais) e dê confiança. "
        f"Depois identifique as 5 lacunas prioritárias, escreva resumo "
        f"qualitativo e recomendação breve. "
        f"Use a tool `registrar_diagnostico` — não responda em texto livre."
    )


def _formatar_redato_output(out: Dict[str, Any]) -> str:
    """Resumo legível do redato_output pro prompt (não JSON cru pra
    economizar tokens)."""
    if not out:
        return "(redato_output vazio — sem contexto adicional)"
    if "error" in out:
        return f"(redato_output com erro: {out.get('error', '')[:100]})"

    linhas: List[str] = []
    # Modo
    modo = out.get("modo")
    if modo:
        linhas.append(f"  modo: {modo}")
    # Notas top-level
    nt = out.get("nota_total_enem")
    if nt is not None:
        linhas.append(f"  nota_total_enem: {nt}/1000")

    # cN_audit (formato OF14)
    for ck in ("c1_audit", "c2_audit", "c3_audit", "c4_audit", "c5_audit"):
        bloco = out.get(ck)
        if isinstance(bloco, dict):
            nota = bloco.get("nota")
            fb = bloco.get("feedback_text") or bloco.get("feedback") or ""
            fb_clip = (fb[:300] + "…") if len(fb) > 300 else fb
            linhas.append(f"  {ck}: nota={nota} — {fb_clip}")

    # foco_c{N} (modo focado)
    if isinstance(modo, str) and modo.startswith("foco_c"):
        n = modo[len("foco_"):]  # "c2"
        v = out.get(f"nota_{n}_enem")
        if v is not None:
            linhas.append(f"  nota_{n}_enem: {v}/200 (modo {modo})")

    # notas_enem (completo_parcial)
    notas_enem = out.get("notas_enem")
    if isinstance(notas_enem, dict):
        pares = ", ".join(f"{k}={v}" for k, v in notas_enem.items())
        linhas.append(f"  notas_enem: {pares}")

    if not linhas:
        return f"(redato_output sem campos reconhecidos: {list(out.keys())[:5]})"
    return "\n".join(linhas)


# ──────────────────────────────────────────────────────────────────────
# Tool schema — força saída estruturada pelos 40 descritores
# ──────────────────────────────────────────────────────────────────────

def _build_tool_schema(descritor_ids: List[str]) -> Dict[str, Any]:
    """JSON schema da tool `registrar_diagnostico`.

    Inclui enum de IDs válidos no schema do `id` por descritor — isso
    impede o LLM de inventar IDs novos no nível do schema validator
    da OpenAI (defesa em profundidade; ainda validamos no Python).
    """
    return {
        "type": "function",
        "function": {
            "name": "registrar_diagnostico",
            "description": (
                "Registra diagnóstico cognitivo da redação: classifica "
                "cada um dos 40 descritores e produz lacunas prioritárias "
                "+ resumo + recomendação."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "descritores": {
                        "type": "array",
                        "minItems": 40,
                        "maxItems": 40,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "id": {
                                    "type": "string",
                                    "enum": descritor_ids,
                                },
                                "status": {
                                    "type": "string",
                                    "enum": sorted(VALID_STATUS),
                                },
                                "evidencias": {
                                    "type": "array",
                                    "maxItems": MAX_EVIDENCIAS,
                                    "items": {"type": "string"},
                                },
                                "confianca": {
                                    "type": "string",
                                    "enum": sorted(VALID_CONFIANCA),
                                },
                            },
                            "required": [
                                "id", "status", "evidencias", "confianca",
                            ],
                        },
                    },
                    "lacunas_prioritarias": {
                        "type": "array",
                        "maxItems": MAX_LACUNAS_PRIORITARIAS,
                        "items": {"type": "string", "enum": descritor_ids},
                    },
                    "resumo_qualitativo": {
                        "type": "string",
                        "minLength": 30,
                    },
                    "recomendacao_breve": {
                        "type": "string",
                        "minLength": 20,
                    },
                },
                "required": [
                    "descritores", "lacunas_prioritarias",
                    "resumo_qualitativo", "recomendacao_breve",
                ],
            },
        },
    }


# ──────────────────────────────────────────────────────────────────────
# Validação da resposta
# ──────────────────────────────────────────────────────────────────────

def _validar_diagnostico(
    args: Dict[str, Any], expected_ids: List[str],
) -> Dict[str, Any]:
    """Valida o output do tool_call e devolve dict normalizado.

    Levanta DiagnosticoError com mensagem clara em caso de schema
    inválido. Defensa em profundidade (schema da OpenAI já valida
    enum/required, mas latência da rede pode entregar payload
    estranho — checamos sempre).
    """
    if not isinstance(args, dict):
        raise DiagnosticoError(
            f"args do tool não é dict: tipo {type(args).__name__}"
        )

    # 1. Descritores: 40 entries, IDs únicos no set válido
    descs = args.get("descritores")
    if not isinstance(descs, list):
        raise DiagnosticoError("descritores ausente ou não é lista")
    if len(descs) != 40:
        raise DiagnosticoError(
            f"esperava 40 descritores, recebi {len(descs)}"
        )

    expected_set = set(expected_ids)
    seen_ids: set = set()
    out_descs: List[Dict[str, Any]] = []
    for i, entry in enumerate(descs):
        if not isinstance(entry, dict):
            raise DiagnosticoError(f"descritor[{i}] não é dict")
        did = entry.get("id")
        if did not in expected_set:
            raise DiagnosticoError(
                f"descritor[{i}].id inválido: {did!r} (não está no YAML)"
            )
        if did in seen_ids:
            raise DiagnosticoError(f"descritor duplicado: {did}")
        seen_ids.add(did)

        status = entry.get("status")
        if status not in VALID_STATUS:
            raise DiagnosticoError(
                f"{did}.status inválido: {status!r} (esperado {VALID_STATUS})"
            )
        confianca = entry.get("confianca")
        if confianca not in VALID_CONFIANCA:
            raise DiagnosticoError(
                f"{did}.confianca inválido: {confianca!r}"
            )
        evidencias = entry.get("evidencias", [])
        if not isinstance(evidencias, list):
            raise DiagnosticoError(
                f"{did}.evidencias não é lista (tipo {type(evidencias).__name__})"
            )
        # Trunca defensivamente (schema OpenAI já limita; protege
        # contra payload corrompido).
        evidencias = [str(e) for e in evidencias[:MAX_EVIDENCIAS]]

        out_descs.append({
            "id": did,
            "status": status,
            "evidencias": evidencias,
            "confianca": confianca,
        })

    if seen_ids != expected_set:
        faltando = expected_set - seen_ids
        raise DiagnosticoError(
            f"descritores faltando ({len(faltando)}): "
            f"{sorted(faltando)[:10]}…"
        )

    # 2. Lacunas prioritárias: subset dos IDs válidos, max 5
    lacunas = args.get("lacunas_prioritarias", [])
    if not isinstance(lacunas, list):
        raise DiagnosticoError("lacunas_prioritarias não é lista")
    if len(lacunas) > MAX_LACUNAS_PRIORITARIAS:
        raise DiagnosticoError(
            f"lacunas_prioritarias tem {len(lacunas)}, "
            f"máx {MAX_LACUNAS_PRIORITARIAS}"
        )
    for lid in lacunas:
        if lid not in expected_set:
            raise DiagnosticoError(
                f"lacunas_prioritarias contém ID inválido: {lid!r}"
            )

    # 3. Strings curtas obrigatórias
    resumo = args.get("resumo_qualitativo", "")
    if not isinstance(resumo, str) or len(resumo.strip()) < 20:
        raise DiagnosticoError("resumo_qualitativo vazio ou curto demais")
    recom = args.get("recomendacao_breve", "")
    if not isinstance(recom, str) or len(recom.strip()) < 10:
        raise DiagnosticoError("recomendacao_breve vazio ou curto demais")

    return {
        "descritores": out_descs,
        "lacunas_prioritarias": list(lacunas),
        "resumo_qualitativo": resumo.strip(),
        "recomendacao_breve": recom.strip(),
    }


def _calcular_custo_usd(
    *, input_tokens: int, output_tokens: int,
) -> float:
    """Custo estimado em USD pelo pricing GPT-4.1."""
    custo_input = input_tokens * (PRICE_INPUT_PER_MILLION_USD / 1_000_000)
    custo_output = output_tokens * (PRICE_OUTPUT_PER_MILLION_USD / 1_000_000)
    return round(custo_input + custo_output, 6)


# ──────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────

def inferir_diagnostico(
    *,
    texto_redacao: str,
    redato_output: Dict[str, Any],
    tema: str,
    modelo: Optional[str] = None,
    client_factory: ClientFactory = _default_client_factory,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> Optional[Dict[str, Any]]:
    """Gera diagnóstico cognitivo pra uma redação.

    Args:
        texto_redacao: texto OCR-ado.
        redato_output: saída da correção (cN_audit, notas_enem etc).
            Pode ser dict vazio — diagnóstico ainda roda só com
            texto da redação.
        tema: tema da proposta (string curta).
        modelo: override do modelo. Default ``REDATO_DIAGNOSTICO_MODELO``
            ou ``DEFAULT_MODEL``.
        client_factory: factory que retorna cliente OpenAI. Tests
            injetam mock.
        timeout_seconds: timeout da chamada OpenAI.

    Returns:
        Dict estruturado conforme schema do diagnóstico; ou ``None``
        se inferência falhou (caller registra log e segue sem
        persistir — falha NÃO bloqueia pipeline principal).

    Schema do retorno:
        {
          "schema_version": "1.0",
          "modelo_usado": "gpt-4.1-2025-04-14",
          "descritores_versao": "1.0",
          "gerado_em": "ISO timestamp",
          "latencia_ms": int,
          "custo_estimado_usd": float,
          "input_tokens": int,
          "output_tokens": int,
          "descritores": [40 entries],
          "lacunas_prioritarias": [...top5],
          "resumo_qualitativo": "...",
          "recomendacao_breve": "..."
        }
    """
    started = time.time()
    modelo_real = (
        modelo
        or os.environ.get("REDATO_DIAGNOSTICO_MODELO")
        or DEFAULT_MODEL
    )

    if not (texto_redacao or "").strip():
        logger.warning(
            "diagnostico: texto_redacao vazio — pulando inferência"
        )
        return None

    try:
        descritores = load_descritores()
    except Exception:  # noqa: BLE001
        logger.exception(
            "diagnostico: falha ao carregar descritores.yaml"
        )
        return None

    expected_ids = [d.id for d in descritores]
    tool_schema = _build_tool_schema(expected_ids)
    user_prompt = _build_user_prompt(
        texto_redacao=texto_redacao,
        redato_output=redato_output or {},
        tema=tema or "",
        descritores=descritores,
    )

    try:
        client = client_factory()
    except DiagnosticoError:
        # API key missing já dá log claro no _default_client_factory.
        logger.exception("diagnostico: client_factory falhou")
        return None
    except Exception:  # noqa: BLE001
        logger.exception("diagnostico: erro inesperado em client_factory")
        return None

    logger.info(
        "diagnostico: chamando %s, redacao_chars=%d, tema_chars=%d, timeout=%.0fs",
        modelo_real, len(texto_redacao), len(tema or ""), timeout_seconds,
    )

    try:
        response = client.chat.completions.create(
            model=modelo_real,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            tools=[tool_schema],
            tool_choice={
                "type": "function",
                "function": {"name": "registrar_diagnostico"},
            },
            temperature=TEMPERATURE,
            max_tokens=MAX_OUTPUT_TOKENS,
            timeout=timeout_seconds,
        )
    except Exception as exc:  # noqa: BLE001
        # Timeout, rate limit, key inválida, modelo inexistente, rede.
        # Stack trace via logger.exception garante visibilidade em Railway.
        logger.exception(
            "diagnostico: chamada OpenAI falhou (%s)", type(exc).__name__,
        )
        return None

    latencia_ms = int((time.time() - started) * 1000)

    # Extrai tool_call args
    try:
        choice = response.choices[0]
        tool_calls = getattr(choice.message, "tool_calls", None) or []
        if not tool_calls:
            logger.error(
                "diagnostico: resposta sem tool_calls (latencia=%dms)",
                latencia_ms,
            )
            return None
        args_raw = tool_calls[0].function.arguments
    except Exception:  # noqa: BLE001
        logger.exception(
            "diagnostico: estrutura de resposta inesperada",
        )
        return None

    try:
        args = json.loads(args_raw)
    except json.JSONDecodeError:
        logger.exception(
            "diagnostico: tool args não é JSON válido (raw[:200]=%r)",
            (args_raw or "")[:200],
        )
        return None

    try:
        validado = _validar_diagnostico(args, expected_ids)
    except DiagnosticoError as exc:
        logger.error(
            "diagnostico: validação falhou (latencia=%dms): %s",
            latencia_ms, exc,
        )
        return None

    # Tokens — OpenAI devolve em response.usage; fallback p/ 0 se ausente
    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    custo = _calcular_custo_usd(
        input_tokens=input_tokens, output_tokens=output_tokens,
    )

    diagnostico = {
        "schema_version": SCHEMA_VERSION,
        "modelo_usado": modelo_real,
        "descritores_versao": versao_carregada(),
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "latencia_ms": latencia_ms,
        "custo_estimado_usd": custo,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        **validado,
    }

    logger.info(
        "diagnostico: ok (latencia=%dms, custo=$%.4f, "
        "lacunas=%d, top=%s)",
        latencia_ms, custo,
        sum(1 for d in validado["descritores"] if d["status"] == "lacuna"),
        validado["lacunas_prioritarias"][:3],
    )
    return diagnostico


def diagnostico_habilitado() -> bool:
    """True se a flag global está ON. Default true; rollback rápido
    via ``REDATO_DIAGNOSTICO_HABILITADO=false``."""
    val = os.environ.get("REDATO_DIAGNOSTICO_HABILITADO", "true")
    return val.strip().lower() not in {"false", "0", "no", ""}
