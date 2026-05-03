"""Loader dos 40 descritores observáveis pro diagnóstico cognitivo.

Lê ``docs/redato/v3/diagnostico/descritores.yaml`` (Fase 1, commit
010686c) e devolve lista tipada de Descritor.

Cache em memória module-level com mtime check — reload acontece só
se o arquivo for modificado entre chamadas. Em prod (Railway) o YAML
não muda em runtime, então o cache fica quente após a primeira
chamada e custa ~zero.

Caminho configurável via env ``REDATO_DIAGNOSTICO_YAML``. Default:
caminho relativo à raiz do repo. No container Docker o YAML é copiado
em ``/app/docs/redato/v3/diagnostico/descritores.yaml`` (`COPY . .`
no Dockerfile já cobre).
"""
from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


# Resolução do YAML em ordem de prioridade:
#   1. env REDATO_DIAGNOSTICO_YAML (override absoluto)
#   2. PACKAGE: redato_backend/diagnostico/descritores.yaml (sempre presente
#      no container Docker pq `COPY . .` inclui o package todo)
#   3. REPO: docs/redato/v3/diagnostico/descritores.yaml (canônico pra docs;
#      em dev/CI vale; em Docker o context não cobre — usa #2)
#
# A versão "package" é uma cópia da "repo". Mantemos as duas em sincronia
# via test smoke (`test_descritores_yaml_em_sincronia`). Não fazemos
# symlink pq Docker COPY não atravessa cross-context.
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT_LOCAL = _BACKEND_ROOT.parent.parent  # redato_hash/

PACKAGE_YAML_PATH = str(Path(__file__).resolve().parent / "descritores.yaml")
"""Caminho da cópia bundled dentro do package — funciona em prod Docker."""

REPO_YAML_PATH = str(_REPO_ROOT_LOCAL / "docs/redato/v3/diagnostico/descritores.yaml")
"""Caminho canônico da Fase 1 (commit 010686c) — fonte da verdade pra
docs e versionamento. Cópia em PACKAGE_YAML_PATH é mantida em sync."""

# Mantido como alias retro-compatível (nome usado em docs antes do bundle).
DEFAULT_YAML_PATH = PACKAGE_YAML_PATH
"""Caminho default usado pelo loader (= PACKAGE_YAML_PATH).
Override via env ``REDATO_DIAGNOSTICO_YAML`` (path absoluto)."""


@dataclass(frozen=True)
class Descritor:
    """Descritor observável (1 dos 40 da Fase 1).

    Frozen pra dar segurança ao cache module-level (não muta após
    carregamento). Os 7 campos batem 1:1 com o YAML.
    """
    id: str
    competencia: str  # "C1" .. "C5"
    categoria_inep: str
    nome: str
    definicao: str
    indicador_lacuna: str
    exemplo_lacuna: str

    @property
    def comp_num(self) -> int:
        """Número da competência (1..5) — útil pra ordenação."""
        return int(self.competencia[1:])


# ──────────────────────────────────────────────────────────────────────
# Cache module-level
# ──────────────────────────────────────────────────────────────────────

_lock = threading.Lock()
_cache_path: Optional[str] = None
_cache_mtime: Optional[float] = None
_cache_descritores: Optional[List[Descritor]] = None
_cache_versao: Optional[str] = None


class DescritoresInvalidosError(RuntimeError):
    """YAML não passa validação básica (estrutura, campos, contagem).

    Levantada cedo no startup pra evitar pipeline rodar com schema
    quebrado em silêncio."""


def _resolve_yaml_path() -> str:
    """Resolve path do YAML, respeitando override do env.

    Ordem de prioridade:
        1. env REDATO_DIAGNOSTICO_YAML (override absoluto)
        2. PACKAGE_YAML_PATH (cópia bundled — sempre presente em prod Docker)
        3. REPO_YAML_PATH (canônico em dev/CI quando o package não existe)
    """
    override = os.environ.get("REDATO_DIAGNOSTICO_YAML")
    if override:
        return override
    if os.path.exists(PACKAGE_YAML_PATH):
        return PACKAGE_YAML_PATH
    return REPO_YAML_PATH


def _validate_and_parse(data: Dict[str, Any]) -> List[Descritor]:
    """Valida estrutura + campos obrigatórios + contagem 40.

    Erros viram DescritoresInvalidosError com mensagem clara.
    Validações duplicam o que o teste smoke do YAML já faz —
    aqui é defensa em runtime caso alguém edite o YAML em prod
    sem rodar os testes.
    """
    if not isinstance(data, dict):
        raise DescritoresInvalidosError(
            f"YAML root não é dict: tipo {type(data).__name__}"
        )
    descs_raw = data.get("descritores")
    if not isinstance(descs_raw, list):
        raise DescritoresInvalidosError(
            "YAML.descritores ausente ou não é lista"
        )
    if len(descs_raw) != 40:
        raise DescritoresInvalidosError(
            f"YAML deve ter exatamente 40 descritores, tem {len(descs_raw)}"
        )

    required = {
        "id", "competencia", "categoria_inep", "nome",
        "definicao", "indicador_lacuna", "exemplo_lacuna",
    }
    seen_ids: set = set()
    descs: List[Descritor] = []
    for i, d in enumerate(descs_raw):
        if not isinstance(d, dict):
            raise DescritoresInvalidosError(
                f"descritor[{i}] não é dict"
            )
        missing = required - set(d.keys())
        if missing:
            raise DescritoresInvalidosError(
                f"descritor[{i}] (id={d.get('id','?')}) sem campos: {missing}"
            )
        did = d["id"]
        if did in seen_ids:
            raise DescritoresInvalidosError(f"ID duplicado: {did}")
        seen_ids.add(did)
        comp = d["competencia"]
        if comp not in {"C1", "C2", "C3", "C4", "C5"}:
            raise DescritoresInvalidosError(
                f"{did}: competencia inválida {comp!r}"
            )
        for f in ("definicao", "indicador_lacuna", "exemplo_lacuna",
                  "nome", "categoria_inep"):
            if not isinstance(d[f], str) or not d[f].strip():
                raise DescritoresInvalidosError(
                    f"{did}.{f} vazio ou tipo inválido"
                )
        descs.append(Descritor(
            id=did, competencia=comp,
            categoria_inep=d["categoria_inep"],
            nome=d["nome"],
            definicao=d["definicao"].strip(),
            indicador_lacuna=d["indicador_lacuna"].strip(),
            exemplo_lacuna=d["exemplo_lacuna"].strip(),
        ))

    # Distribuição: 8 por competência
    from collections import Counter
    dist = Counter(d.competencia for d in descs)
    for comp in ("C1", "C2", "C3", "C4", "C5"):
        if dist[comp] != 8:
            raise DescritoresInvalidosError(
                f"competencia {comp} tem {dist[comp]} descritores, esperado 8"
            )
    return descs


def load_descritores(*, force_reload: bool = False) -> List[Descritor]:
    """Retorna lista dos 40 descritores carregada do YAML.

    Cache em memória com mtime check — só relê o arquivo se ele
    mudou no disco desde a última leitura. Thread-safe.

    Args:
        force_reload: ignora cache e recarrega sempre. Útil em
            testes que reescrevem o YAML.

    Raises:
        FileNotFoundError: YAML não encontrado no path resolvido.
        DescritoresInvalidosError: YAML existe mas não passa validação.
    """
    global _cache_path, _cache_mtime, _cache_descritores, _cache_versao
    path = _resolve_yaml_path()
    mtime = os.path.getmtime(path)  # FileNotFoundError se faltar

    with _lock:
        cache_valid = (
            not force_reload
            and _cache_path == path
            and _cache_mtime == mtime
            and _cache_descritores is not None
        )
        if cache_valid:
            return _cache_descritores  # type: ignore[return-value]

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        descs = _validate_and_parse(data or {})
        _cache_path = path
        _cache_mtime = mtime
        _cache_descritores = descs
        _cache_versao = (data or {}).get("versao") if isinstance(data, dict) else None
        logger.info(
            "diagnostico: carregou %d descritores de %s (versao=%s)",
            len(descs), path, _cache_versao,
        )
        return descs


def descritores_por_id() -> Dict[str, Descritor]:
    """Lookup map id → Descritor. Reusa o cache de load_descritores."""
    return {d.id: d for d in load_descritores()}


def descritor_ids() -> List[str]:
    """Lista de IDs ordenada por competência+número (C1.001..C5.008)."""
    return [d.id for d in sorted(
        load_descritores(),
        key=lambda d: (d.comp_num, d.id),
    )]


def versao_carregada() -> Optional[str]:
    """Versão do YAML atualmente em cache. Retorna None se ainda não
    foi carregado ou se o YAML não tinha campo `versao`."""
    return _cache_versao
