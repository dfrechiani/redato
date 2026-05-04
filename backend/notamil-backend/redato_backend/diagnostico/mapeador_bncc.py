"""Mapeador LLM: descritor → habilidades BNCC EM (Fase 5A.2).

Recebe um descritor do `descritores.yaml` (Fase 1) e chama GPT-4.1
com tool_use forçado pra identificar 1-3 habilidades BNCC EM-LP que
o descritor exercita, com intensidade e justificativa.

Output alimenta `mapeamento_descritores_bncc.json`, lido em runtime
pelo helper `bncc.py` que enriquece o payload do endpoint /perfil
(Fase 3) com as habilidades BNCC dentro de cada lacuna prioritária.

Mesmo padrão arquitetural de Fase 5A.1 (`mapeador.py`):
- Tool schema com enum dos 54 códigos válidos (BNCC_LP_EM)
- Validação dupla: schema OpenAI + python defensivo
- None em falha (não bloqueia pipeline)
- Pricing GPT-4.1 padrão pra estimar custo

Custo médio esperado: ~$0.01/descritor × 40 = ~$0.40 total.
Latência típica: ~5s/descritor (prompt menor que mapeador.py).
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from redato_backend.diagnostico.bncc_referencia import (
    BNCC_LP_EM, listar_codigos_ordenados, is_codigo_valido,
)
from redato_backend.diagnostico.descritores import Descritor

logger = logging.getLogger(__name__)


SCHEMA_VERSION = "1.0"
DEFAULT_MODEL = "gpt-4.1-2025-04-14"
DEFAULT_TIMEOUT_SECONDS = 30.0
TEMPERATURE = 0
MAX_OUTPUT_TOKENS = 1000

PRICE_INPUT_PER_MILLION_USD = 2.0
PRICE_OUTPUT_PER_MILLION_USD = 8.0

VALID_INTENSIDADE = {"alta", "media", "baixa"}
MAX_HABILIDADES_POR_DESCRITOR = 3


# ──────────────────────────────────────────────────────────────────────
# Cliente OpenAI (factory injetável pra tests)
# ──────────────────────────────────────────────────────────────────────

ClientFactory = Callable[[], Any]


class MapeadorBnccError(RuntimeError):
    """Falha no mapeamento BNCC. Carrega contexto pra debug."""

    def __init__(
        self, msg: str, *, raw_output: Optional[str] = None,
    ) -> None:
        super().__init__(msg)
        self.raw_output = raw_output


def _default_client_factory() -> Any:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise MapeadorBnccError(
            "OPENAI_API_KEY não setada — script de mapeamento BNCC "
            "exige chave OpenAI. Setar antes de rodar."
        )
    try:
        from openai import OpenAI
    except ImportError as e:
        raise MapeadorBnccError(
            "OpenAI SDK não instalado (necessário openai>=1.50)."
        ) from e
    return OpenAI(api_key=key)


# ──────────────────────────────────────────────────────────────────────
# Tipos do mapeamento
# ──────────────────────────────────────────────────────────────────────

@dataclass
class HabilidadeMapeada:
    """1 habilidade BNCC mapeada pro descritor com intensidade."""
    codigo: str
    intensidade: str       # "alta" | "media" | "baixa"
    razao: str             # 1-2 frases justificando

    def to_dict(self) -> dict:
        return {
            "codigo": self.codigo,
            "intensidade": self.intensidade,
            "razao": self.razao,
        }


@dataclass
class MapeamentoDescritorBncc:
    """Output do mapeador pra UM descritor."""
    descritor_id: str
    descritor_nome: str
    descritor_competencia: str    # "C1".."C5"
    habilidades_bncc: List[HabilidadeMapeada]
    area: str = "Linguagens, Códigos e suas Tecnologias"
    componente: str = "Língua Portuguesa"
    modelo_usado: str = DEFAULT_MODEL
    latencia_ms: int = 0
    custo_estimado_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0

    def to_dict(self) -> dict:
        return {
            "descritor_id": self.descritor_id,
            "descritor_nome": self.descritor_nome,
            "descritor_competencia": self.descritor_competencia,
            "habilidades_bncc": [h.to_dict() for h in self.habilidades_bncc],
            "area": self.area,
            "componente": self.componente,
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
    "Você é um especialista em currículo de Língua Portuguesa pra "
    "Ensino Médio brasileiro. Sua tarefa: ler um descritor "
    "observável de redação ENEM e identificar quais habilidades BNCC "
    "do Ensino Médio (componente Língua Portuguesa) o descritor "
    "exercita.\n\n"
    "Princípios:\n"
    "1. SEJA SELETIVO. Listar muitas habilidades fracas dilui a "
    "justificativa pedagógica. Liste só as habilidades que o "
    "descritor exercita DIRETAMENTE — máx 3.\n"
    "2. INTENSIDADE 'alta' quando o descritor é trabalho central da "
    "habilidade. 'media' quando é parte da habilidade. 'baixa' "
    "quando é tangencial.\n"
    "3. JUSTIFIQUE com 1-2 frases mencionando o que do descritor "
    "trabalha aquela habilidade BNCC.\n"
    "4. Use APENAS códigos do catálogo fornecido (EM13LP01-EM13LP54). "
    "Não invente códigos nem use de outros componentes (LGG, MAT).\n\n"
    "Use a tool `registrar_mapeamento_bncc` — não responda em texto livre."
)


def _build_user_prompt(descritor: Descritor) -> str:
    """Constrói prompt do usuário com descritor + lista completa
    BNCC EM-LP como referência."""
    bncc_txt = "\n".join(
        f"  [{h.codigo}] ({h.eixo}) {h.descricao}"
        for h in BNCC_LP_EM.values()
    )
    return (
        f"DESCRITOR A MAPEAR:\n"
        f"  ID: {descritor.id}\n"
        f"  Nome: {descritor.nome}\n"
        f"  Competência ENEM: {descritor.competencia}\n"
        f"  Categoria INEP: {descritor.categoria_inep}\n"
        f"  Definição: {descritor.definicao}\n"
        f"  Indicador de lacuna: {descritor.indicador_lacuna}\n"
        f"  Exemplo de lacuna: {descritor.exemplo_lacuna}\n\n"
        f"54 HABILIDADES BNCC EM — LÍNGUA PORTUGUESA:\n"
        f"{bncc_txt}\n\n"
        f"Identifique até {MAX_HABILIDADES_POR_DESCRITOR} habilidades "
        f"BNCC que esse descritor trabalha, com intensidade e "
        f"justificativa. Use a tool `registrar_mapeamento_bncc`."
    )


def _build_tool_schema() -> Dict[str, Any]:
    """JSON schema da tool. Enum codigos_validos no schema-level
    impede o LLM de inventar códigos novos (defesa em profundidade)."""
    codigos_validos = listar_codigos_ordenados()
    return {
        "type": "function",
        "function": {
            "name": "registrar_mapeamento_bncc",
            "description": (
                "Registra mapeamento do descritor pras habilidades "
                "BNCC EM-LP que ele trabalha."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "habilidades_bncc": {
                        "type": "array",
                        "minItems": 0,
                        "maxItems": MAX_HABILIDADES_POR_DESCRITOR,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "codigo": {
                                    "type": "string",
                                    "enum": codigos_validos,
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
                            "required": ["codigo", "intensidade", "razao"],
                        },
                    },
                },
                "required": ["habilidades_bncc"],
            },
        },
    }


# ──────────────────────────────────────────────────────────────────────
# Validação
# ──────────────────────────────────────────────────────────────────────

def _validar_args(args: Dict[str, Any]) -> List[HabilidadeMapeada]:
    """Valida output do tool_call. Levanta MapeadorBnccError em
    inconsistências. Defesa em profundidade — schema OpenAI já cobre
    enum/required."""
    if not isinstance(args, dict):
        raise MapeadorBnccError(
            f"args não é dict: tipo {type(args).__name__}"
        )
    habs_raw = args.get("habilidades_bncc")
    if not isinstance(habs_raw, list):
        raise MapeadorBnccError("habilidades_bncc não é lista")
    if len(habs_raw) > MAX_HABILIDADES_POR_DESCRITOR:
        raise MapeadorBnccError(
            f"max {MAX_HABILIDADES_POR_DESCRITOR} habilidades, "
            f"recebi {len(habs_raw)}"
        )
    seen: set = set()
    out: List[HabilidadeMapeada] = []
    for i, e in enumerate(habs_raw):
        if not isinstance(e, dict):
            raise MapeadorBnccError(f"habilidade[{i}] não é dict")
        codigo = e.get("codigo")
        if not is_codigo_valido(codigo):
            raise MapeadorBnccError(
                f"habilidade[{i}].codigo inválido: {codigo!r} "
                f"(fora do catálogo EM13LP01-EM13LP54)"
            )
        if codigo in seen:
            raise MapeadorBnccError(f"habilidade duplicada: {codigo}")
        seen.add(codigo)
        intensidade = e.get("intensidade")
        if intensidade not in VALID_INTENSIDADE:
            raise MapeadorBnccError(
                f"{codigo}.intensidade inválida: {intensidade!r}"
            )
        razao = e.get("razao", "")
        if not isinstance(razao, str) or len(razao.strip()) < 10:
            raise MapeadorBnccError(f"{codigo}.razao vazia ou curta")
        out.append(HabilidadeMapeada(
            codigo=codigo, intensidade=intensidade, razao=razao.strip(),
        ))
    return out


def _calcular_custo_usd(input_tokens: int, output_tokens: int) -> float:
    custo_input = input_tokens * (PRICE_INPUT_PER_MILLION_USD / 1_000_000)
    custo_output = output_tokens * (PRICE_OUTPUT_PER_MILLION_USD / 1_000_000)
    return round(custo_input + custo_output, 6)


# ──────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────

def mapear_descritor_para_bncc(
    descritor: Descritor,
    *,
    modelo: Optional[str] = None,
    client_factory: ClientFactory = _default_client_factory,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> Optional[MapeamentoDescritorBncc]:
    """Mapeia 1 descritor pras habilidades BNCC que trabalha.

    Args:
        descritor: Descritor (Fase 1) carregado do YAML.
        modelo: override; default usa env REDATO_DIAGNOSTICO_MODELO
            ou DEFAULT_MODEL.
        client_factory: factory injetável pra tests.
        timeout_seconds: timeout da chamada OpenAI.

    Returns:
        MapeamentoDescritorBncc ou None em falha (caller deve logar
        e seguir — falhas individuais não param batch).
    """
    started = time.time()
    modelo_real = (
        modelo
        or os.environ.get("REDATO_DIAGNOSTICO_MODELO")
        or DEFAULT_MODEL
    )

    tool_schema = _build_tool_schema()
    user_prompt = _build_user_prompt(descritor)

    try:
        client = client_factory()
    except MapeadorBnccError:
        logger.exception("[mapper-bncc] client_factory falhou")
        return None
    except Exception:  # noqa: BLE001
        logger.exception("[mapper-bncc] erro inesperado em client_factory")
        return None

    logger.info(
        "[mapper-bncc] %s — chamando %s",
        descritor.id, modelo_real,
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
                "function": {"name": "registrar_mapeamento_bncc"},
            },
            temperature=TEMPERATURE,
            max_tokens=MAX_OUTPUT_TOKENS,
            timeout=timeout_seconds,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "[mapper-bncc] %s — chamada OpenAI falhou (%s: %s)",
            descritor.id, type(exc).__name__, exc,
        )
        return None

    latencia_ms = int((time.time() - started) * 1000)

    try:
        choice = response.choices[0]
        tool_calls = getattr(choice.message, "tool_calls", None) or []
        if not tool_calls:
            logger.error(
                "[mapper-bncc] %s — resposta sem tool_calls", descritor.id,
            )
            return None
        args_raw = tool_calls[0].function.arguments
    except Exception:  # noqa: BLE001
        logger.exception(
            "[mapper-bncc] %s — estrutura inesperada", descritor.id,
        )
        return None

    try:
        args = json.loads(args_raw)
    except json.JSONDecodeError:
        logger.exception(
            "[mapper-bncc] %s — tool args não é JSON válido", descritor.id,
        )
        return None

    try:
        habilidades = _validar_args(args)
    except MapeadorBnccError as exc:
        logger.error(
            "[mapper-bncc] %s — validação falhou: %s",
            descritor.id, exc,
        )
        return None

    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    custo = _calcular_custo_usd(input_tokens, output_tokens)

    logger.info(
        "[mapper-bncc] %s — ok (latencia=%dms, custo=$%.4f, "
        "habilidades=%d)",
        descritor.id, latencia_ms, custo, len(habilidades),
    )

    return MapeamentoDescritorBncc(
        descritor_id=descritor.id,
        descritor_nome=descritor.nome,
        descritor_competencia=descritor.competencia,
        habilidades_bncc=habilidades,
        modelo_usado=modelo_real,
        latencia_ms=latencia_ms,
        custo_estimado_usd=custo,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
