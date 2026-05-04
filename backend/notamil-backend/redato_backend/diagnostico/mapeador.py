"""Mapeador LLM: oficina do livro → descritores trabalhados (Fase 5A.1).

Recebe um `OficinaLivro` (parsed por `parser_livros.py`) e chama
GPT-4.1 com tool_use forçado pra classificar quais dos 40
descritores aquela oficina exercita + qual a intensidade.

Política de erro:
- Falhas (timeout OpenAI, key missing, schema inválido, parser fail)
  retornam `None` — caller (script de batch) registra log e segue
  com a próxima oficina. NÃO bloqueia pipeline inteiro por causa
  de 1 oficina problemática.
- Schema invalidation é defesa em profundidade — OpenAI tools já
  validam enum/required antes de devolver.

Modelo padrão: `gpt-4.1-2025-04-14` (mesmo da Fase 2). Temperatura 0
(determinístico).

NÃO usa cache OpenAI — chamada é one-shot (rodada em batch via script
manual, não em prod).
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
    Descritor, load_descritores,
)
from redato_backend.diagnostico.parser_livros import OficinaLivro

logger = logging.getLogger(__name__)


SCHEMA_VERSION = "1.0"
DEFAULT_MODEL = "gpt-4.1-2025-04-14"
DEFAULT_TIMEOUT_SECONDS = 60.0
TEMPERATURE = 0
MAX_OUTPUT_TOKENS = 2000

# Pricing (mesmo da Fase 2 — atualizar quando mudar)
PRICE_INPUT_PER_MILLION_USD = 2.0
PRICE_OUTPUT_PER_MILLION_USD = 8.0

VALID_INTENSIDADE = {"alta", "media", "baixa"}
VALID_TIPO_ATIVIDADE = {"conceitual", "pratica", "avaliativa", "jogo", "diagnostico"}
MAX_DESCRITORES_POR_OFICINA = 8
MAX_COMPETENCIAS_POR_OFICINA = 3


# ──────────────────────────────────────────────────────────────────────
# Cliente OpenAI (factory injetável pra tests)
# ──────────────────────────────────────────────────────────────────────

ClientFactory = Callable[[], Any]


class MapeadorError(RuntimeError):
    """Falha no mapeamento. Carrega contexto pra debug."""

    def __init__(
        self, msg: str, *, raw_output: Optional[str] = None,
        latencia_ms: Optional[int] = None,
    ) -> None:
        super().__init__(msg)
        self.raw_output = raw_output
        self.latencia_ms = latencia_ms


def _default_client_factory() -> Any:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise MapeadorError(
            "OPENAI_API_KEY não setada — script de mapeamento exige "
            "chave OpenAI. Setar antes de rodar."
        )
    try:
        from openai import OpenAI
    except ImportError as e:
        raise MapeadorError(
            "OpenAI SDK não instalado (necessário openai>=1.50)."
        ) from e
    return OpenAI(api_key=key)


# ──────────────────────────────────────────────────────────────────────
# Schemas internos
# ──────────────────────────────────────────────────────────────────────

@dataclass
class DescritorTrabalhado:
    id: str               # ex.: "C4.001"
    intensidade: str      # "alta" | "media" | "baixa"
    razao: str            # 1-2 frases justificando

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "intensidade": self.intensidade,
            "razao": self.razao,
        }


@dataclass
class MapeamentoOficina:
    """Output do mapeador pra UMA oficina."""
    codigo: str
    serie: str
    oficina_numero: int
    titulo: str
    tem_redato_avaliavel: bool
    descritores_trabalhados: List[DescritorTrabalhado]
    competencias_principais: List[str]
    tipo_atividade: str
    modelo_usado: str
    latencia_ms: int
    custo_estimado_usd: float
    input_tokens: int
    output_tokens: int

    def to_dict(self) -> dict:
        return {
            "codigo": self.codigo,
            "serie": self.serie,
            "oficina_numero": self.oficina_numero,
            "titulo": self.titulo,
            "tem_redato_avaliavel": self.tem_redato_avaliavel,
            "descritores_trabalhados": [
                d.to_dict() for d in self.descritores_trabalhados
            ],
            "competencias_principais": self.competencias_principais,
            "tipo_atividade": self.tipo_atividade,
            "modelo_usado": self.modelo_usado,
            "latencia_ms": self.latencia_ms,
            "custo_estimado_usd": self.custo_estimado_usd,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }


# ──────────────────────────────────────────────────────────────────────
# Prompt
# ──────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "Você é um especialista em pedagogia da escrita argumentativa "
    "ENEM. Sua tarefa: ler o conteúdo de uma oficina pedagógica do "
    "livro do professor e identificar quais dos 40 descritores "
    "observáveis a oficina trabalha.\n\n"
    "Princípios:\n"
    "1. SEJA SELETIVO. Listar muitos descritores fracos polui a "
    "recomendação. Liste só os descritores que a oficina exercita "
    "DELIBERADAMENTE — máx 8.\n"
    "2. INTENSIDADE 'alta' quando o descritor é foco principal da "
    "oficina (ex.: oficina sobre conectivos → C4.001 alta). "
    "'media' quando é tema secundário ou parte da prática. "
    "'baixa' quando é tangencial.\n"
    "3. JUSTIFIQUE com 1-2 frases mencionando o que da oficina "
    "treina o descritor (ex.: 'A oficina pede aluno reescrever 5 "
    "frases trocando conectivos repetitivos').\n"
    "4. COMPETÊNCIAS PRINCIPAIS = no máx 3 das 5 competências ENEM "
    "(C1-C5) onde a oficina mais atua. Se a oficina é diagnóstica "
    "ou cobre tudo, escolha as 3 mais centrais.\n"
    "5. TIPO DA ATIVIDADE — escolha 1:\n"
    "   - 'conceitual': teoria, leitura, explicação (ex.: aula "
    "sobre o que é proposta de intervenção)\n"
    "   - 'pratica': exercício de produção curta ou parcial\n"
    "   - 'avaliativa': redação completa avaliada por rubrica\n"
    "   - 'jogo': dinâmica lúdica (jogo de cartas, simulação)\n"
    "   - 'diagnostico': autoavaliação, mapeamento inicial\n\n"
    "Use a tool `registrar_mapeamento` — não responda em texto livre."
)


def _build_user_prompt(
    oficina: OficinaLivro, descritores: List[Descritor],
) -> str:
    """Constrói prompt do usuário com conteúdo da oficina + lista
    completa dos 40 descritores como referência."""
    descs_txt = "\n".join(
        f"  [{d.id}] {d.competencia} — {d.nome}: {d.definicao[:120]}"
        for d in descritores
    )
    return (
        f"OFICINA A MAPEAR:\n"
        f"{oficina.conteudo_consolidado()}\n\n"
        f"40 DESCRITORES OBSERVÁVEIS (referência completa):\n"
        f"{descs_txt}\n\n"
        f"Identifique até {MAX_DESCRITORES_POR_OFICINA} descritores "
        f"que a oficina trabalha deliberadamente, com intensidade e "
        f"justificativa. Identifique até "
        f"{MAX_COMPETENCIAS_POR_OFICINA} competências principais e "
        f"o tipo da atividade. Use a tool `registrar_mapeamento`."
    )


def _build_tool_schema(descritor_ids: List[str]) -> Dict[str, Any]:
    """JSON schema da tool. Enum de IDs válidos no schema-level
    impede o LLM de inventar IDs novos (defesa em profundidade)."""
    return {
        "type": "function",
        "function": {
            "name": "registrar_mapeamento",
            "description": (
                "Registra mapeamento da oficina pros descritores "
                "observáveis que ela trabalha."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "descritores_trabalhados": {
                        "type": "array",
                        "minItems": 0,
                        "maxItems": MAX_DESCRITORES_POR_OFICINA,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "id": {
                                    "type": "string",
                                    "enum": descritor_ids,
                                },
                                "intensidade": {
                                    "type": "string",
                                    "enum": sorted(VALID_INTENSIDADE),
                                },
                                "razao": {
                                    "type": "string",
                                    "minLength": 10,
                                },
                            },
                            "required": ["id", "intensidade", "razao"],
                        },
                    },
                    "competencias_principais": {
                        "type": "array",
                        "maxItems": MAX_COMPETENCIAS_POR_OFICINA,
                        "items": {
                            "type": "string",
                            "enum": ["C1", "C2", "C3", "C4", "C5"],
                        },
                    },
                    "tipo_atividade": {
                        "type": "string",
                        "enum": sorted(VALID_TIPO_ATIVIDADE),
                    },
                },
                "required": [
                    "descritores_trabalhados",
                    "competencias_principais",
                    "tipo_atividade",
                ],
            },
        },
    }


# ──────────────────────────────────────────────────────────────────────
# Validação
# ──────────────────────────────────────────────────────────────────────

def _validar_args(
    args: Dict[str, Any], expected_ids: List[str],
) -> Dict[str, Any]:
    """Valida output do tool_call. Levanta MapeadorError em qualquer
    inconsistência. Defesa em profundidade — schema OpenAI já cobre
    enum/required, mas latência da rede pode entregar payload
    estranho."""
    if not isinstance(args, dict):
        raise MapeadorError(
            f"args não é dict: tipo {type(args).__name__}"
        )
    descs = args.get("descritores_trabalhados")
    if not isinstance(descs, list):
        raise MapeadorError("descritores_trabalhados não é lista")
    if len(descs) > MAX_DESCRITORES_POR_OFICINA:
        raise MapeadorError(
            f"max {MAX_DESCRITORES_POR_OFICINA} descritores, "
            f"recebi {len(descs)}"
        )
    expected_set = set(expected_ids)
    seen: set = set()
    out_descs: List[DescritorTrabalhado] = []
    for i, e in enumerate(descs):
        if not isinstance(e, dict):
            raise MapeadorError(f"descritor[{i}] não é dict")
        did = e.get("id")
        if did not in expected_set:
            raise MapeadorError(
                f"descritor[{i}].id inválido: {did!r}"
            )
        if did in seen:
            raise MapeadorError(f"descritor duplicado: {did}")
        seen.add(did)
        intensidade = e.get("intensidade")
        if intensidade not in VALID_INTENSIDADE:
            raise MapeadorError(
                f"{did}.intensidade inválida: {intensidade!r}"
            )
        razao = e.get("razao", "")
        if not isinstance(razao, str) or len(razao.strip()) < 10:
            raise MapeadorError(
                f"{did}.razao vazia ou curta demais"
            )
        out_descs.append(DescritorTrabalhado(
            id=did, intensidade=intensidade, razao=razao.strip(),
        ))

    comps = args.get("competencias_principais", [])
    if not isinstance(comps, list):
        raise MapeadorError("competencias_principais não é lista")
    if len(comps) > MAX_COMPETENCIAS_POR_OFICINA:
        raise MapeadorError(
            f"max {MAX_COMPETENCIAS_POR_OFICINA} competências, "
            f"recebi {len(comps)}"
        )
    for c in comps:
        if c not in {"C1", "C2", "C3", "C4", "C5"}:
            raise MapeadorError(f"competencia inválida: {c!r}")

    tipo = args.get("tipo_atividade")
    if tipo not in VALID_TIPO_ATIVIDADE:
        raise MapeadorError(f"tipo_atividade inválido: {tipo!r}")

    return {
        "descritores_trabalhados": out_descs,
        "competencias_principais": list(comps),
        "tipo_atividade": tipo,
    }


def _calcular_custo_usd(input_tokens: int, output_tokens: int) -> float:
    custo_input = input_tokens * (PRICE_INPUT_PER_MILLION_USD / 1_000_000)
    custo_output = output_tokens * (PRICE_OUTPUT_PER_MILLION_USD / 1_000_000)
    return round(custo_input + custo_output, 6)


# ──────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────

def mapear_oficina_para_descritores(
    oficina: OficinaLivro,
    *,
    descritores_yaml: Optional[List[Descritor]] = None,
    modelo: Optional[str] = None,
    client_factory: ClientFactory = _default_client_factory,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> Optional[MapeamentoOficina]:
    """Mapeia 1 oficina pros descritores que ela trabalha.

    Args:
        oficina: OficinaLivro extraído do parser.
        descritores_yaml: lista dos 40. Se None, carrega via load_descritores().
        modelo: override; default usa env var REDATO_DIAGNOSTICO_MODELO
            ou DEFAULT_MODEL.
        client_factory: pra tests injetarem mock.
        timeout_seconds: timeout da chamada OpenAI.

    Returns:
        MapeamentoOficina ou None em falha (caller deve logar).
    """
    started = time.time()
    modelo_real = (
        modelo or os.environ.get("REDATO_DIAGNOSTICO_MODELO") or DEFAULT_MODEL
    )

    if descritores_yaml is None:
        descritores_yaml = load_descritores()

    expected_ids = [d.id for d in descritores_yaml]
    tool_schema = _build_tool_schema(expected_ids)
    user_prompt = _build_user_prompt(oficina, descritores_yaml)

    try:
        client = client_factory()
    except MapeadorError:
        logger.exception("[mapper] client_factory falhou")
        return None
    except Exception:  # noqa: BLE001
        logger.exception("[mapper] erro inesperado em client_factory")
        return None

    logger.info(
        "[mapper] %s — chamando %s, prompt_chars=%d",
        oficina.codigo, modelo_real, len(user_prompt),
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
                "function": {"name": "registrar_mapeamento"},
            },
            temperature=TEMPERATURE,
            max_tokens=MAX_OUTPUT_TOKENS,
            timeout=timeout_seconds,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "[mapper] %s — chamada OpenAI falhou (%s: %s)",
            oficina.codigo, type(exc).__name__, exc,
        )
        return None

    latencia_ms = int((time.time() - started) * 1000)

    try:
        choice = response.choices[0]
        tool_calls = getattr(choice.message, "tool_calls", None) or []
        if not tool_calls:
            logger.error(
                "[mapper] %s — resposta sem tool_calls", oficina.codigo,
            )
            return None
        args_raw = tool_calls[0].function.arguments
    except Exception:  # noqa: BLE001
        logger.exception(
            "[mapper] %s — estrutura de resposta inesperada", oficina.codigo,
        )
        return None

    try:
        args = json.loads(args_raw)
    except json.JSONDecodeError:
        logger.exception(
            "[mapper] %s — tool args não é JSON válido", oficina.codigo,
        )
        return None

    try:
        validado = _validar_args(args, expected_ids)
    except MapeadorError as exc:
        logger.error(
            "[mapper] %s — validação falhou: %s",
            oficina.codigo, exc,
        )
        return None

    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    custo = _calcular_custo_usd(input_tokens, output_tokens)

    logger.info(
        "[mapper] %s — ok (latencia=%dms, custo=$%.4f, "
        "descritores=%d, comps=%s, tipo=%s)",
        oficina.codigo, latencia_ms, custo,
        len(validado["descritores_trabalhados"]),
        validado["competencias_principais"],
        validado["tipo_atividade"],
    )

    return MapeamentoOficina(
        codigo=oficina.codigo,
        serie=oficina.serie,
        oficina_numero=oficina.oficina_numero,
        titulo=oficina.titulo,
        tem_redato_avaliavel=oficina.tem_redato_avaliavel,
        descritores_trabalhados=validado["descritores_trabalhados"],
        competencias_principais=validado["competencias_principais"],
        tipo_atividade=validado["tipo_atividade"],
        modelo_usado=modelo_real,
        latencia_ms=latencia_ms,
        custo_estimado_usd=custo,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
