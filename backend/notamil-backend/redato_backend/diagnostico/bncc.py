"""Helper de leitura do `mapeamento_descritores_bncc.json` (Fase 5A.2).

Lê o JSON estático gerado pelo script de batch e oferece:
- `get_habilidades_bncc_por_descritor(descritor_id)`: usado pelo
  endpoint /perfil pra enriquecer cards de lacuna com habilidades BNCC
- `get_descritores_por_habilidade_bncc(codigo)`: inversa, útil pra
  relatórios "habilidade EM13LP02 é trabalhada nos descritores X, Y"

Cache em memória module-level com mtime check (mesmo padrão de
`oficinas_livro.py`). Em prod o JSON não muda em runtime.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Resolução do caminho do JSON
# ──────────────────────────────────────────────────────────────────────

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = _BACKEND_ROOT.parent.parent

PACKAGE_JSON_PATH = str(
    Path(__file__).resolve().parent / "mapeamento_descritores_bncc.json"
)
REPO_JSON_PATH = str(
    _REPO_ROOT / "docs/redato/v3/diagnostico/mapeamento_descritores_bncc.json"
)


def _resolver_json_path() -> Optional[str]:
    """Ordem de prioridade idêntica ao oficinas_livro.py:
        1. env REDATO_MAPEAMENTO_BNCC_JSON (override absoluto)
        2. PACKAGE_JSON_PATH (bundle pro Docker)
        3. REPO_JSON_PATH (canônico em dev)
    """
    override = os.environ.get("REDATO_MAPEAMENTO_BNCC_JSON")
    if override:
        return override  # sempre — caller falha em getmtime se não existe
    if os.path.exists(PACKAGE_JSON_PATH):
        return PACKAGE_JSON_PATH
    if os.path.exists(REPO_JSON_PATH):
        return REPO_JSON_PATH
    return None


# ──────────────────────────────────────────────────────────────────────
# Cache module-level
# ──────────────────────────────────────────────────────────────────────

_lock = threading.Lock()
_cache_path: Optional[str] = None
_cache_mtime: Optional[float] = None
_cache_data: Optional[Dict[str, Any]] = None
# Index por descritor_id (built lazy quando precisar)
_index_por_descritor: Optional[Dict[str, List[Dict[str, Any]]]] = None
# Index inversa: codigo BNCC → list de descritores
_index_por_habilidade: Optional[Dict[str, List[Dict[str, Any]]]] = None


def carregar_mapeamento(*, force_reload: bool = False) -> Optional[Dict[str, Any]]:
    """Carrega JSON com cache mtime. Retorna None se arquivo ausente
    ou status='nao_gerado_ainda' (placeholder bootstrap)."""
    global _cache_path, _cache_mtime, _cache_data
    global _index_por_descritor, _index_por_habilidade

    path = _resolver_json_path()
    if path is None:
        return None

    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None

    with _lock:
        cache_valid = (
            not force_reload
            and _cache_path == path
            and _cache_mtime == mtime
            and _cache_data is not None
        )
        if cache_valid:
            return _cache_data

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            logger.exception(
                "[bncc] falha ao ler %s — JSON corrompido?", path,
            )
            return None

        if not isinstance(data, dict):
            return None

        # Status placeholder: pipeline não rodou ainda → considera
        # ausente. UI mostra estado vazio (sem habilidades_bncc).
        if data.get("status") == "nao_gerado_ainda":
            logger.info(
                "[bncc] %s tem status='nao_gerado_ainda' — pipeline LLM "
                "precisa ser rodado pelo Daniel pra preencher.", path,
            )
            _cache_path = path
            _cache_mtime = mtime
            _cache_data = data
            _index_por_descritor = {}
            _index_por_habilidade = {}
            return data

        if not isinstance(data.get("mapeamentos"), list):
            logger.warning(
                "[bncc] %s sem chave 'mapeamentos' como lista", path,
            )
            return None

        _cache_path = path
        _cache_mtime = mtime
        _cache_data = data

        # (Re)construção dos índices
        _index_por_descritor = {}
        _index_por_habilidade = defaultdict(list)
        for m in data["mapeamentos"]:
            if not isinstance(m, dict):
                continue
            if m.get("mapeamento_falhou"):
                continue
            desc_id = m.get("descritor_id")
            if not desc_id:
                continue
            habs = m.get("habilidades_bncc", []) or []
            _index_por_descritor[desc_id] = habs
            for h in habs:
                cod = h.get("codigo")
                if cod:
                    _index_por_habilidade[cod].append({
                        "descritor_id": desc_id,
                        "descritor_nome": m.get("descritor_nome", ""),
                        "descritor_competencia": m.get(
                            "descritor_competencia", "",
                        ),
                        "intensidade": h.get("intensidade"),
                        "razao": h.get("razao"),
                    })
        # defaultdict → dict imutável pra evitar criação de keys vazias
        _index_por_habilidade = dict(_index_por_habilidade)

        logger.info(
            "[bncc] cache atualizado: %d descritores mapeados, "
            "%d habilidades únicas (status=%s)",
            len(_index_por_descritor),
            len(_index_por_habilidade),
            data.get("status"),
        )
        return _cache_data


# ──────────────────────────────────────────────────────────────────────
# Lookup APIs
# ──────────────────────────────────────────────────────────────────────

def get_habilidades_bncc_por_descritor(
    descritor_id: str,
) -> List[Dict[str, Any]]:
    """Retorna habilidades BNCC trabalhadas pelo descritor.

    Args:
        descritor_id: ex.: "C5.001"

    Returns:
        Lista de {codigo, intensidade, razao}. Vazia se descritor
        não está mapeado, JSON não existe, ou status='nao_gerado_ainda'.
    """
    carregar_mapeamento()  # popula índices se necessário
    if _index_por_descritor is None:
        return []
    return list(_index_por_descritor.get(descritor_id, []))


def get_descritores_por_habilidade_bncc(
    codigo: str,
) -> List[Dict[str, Any]]:
    """Inversa: descritores que trabalham aquela habilidade BNCC.

    Args:
        codigo: ex.: "EM13LP02"

    Returns:
        Lista de {descritor_id, descritor_nome, descritor_competencia,
        intensidade, razao}. Vazia se nenhum descritor mapeia pra
        essa habilidade.
    """
    carregar_mapeamento()
    if _index_por_habilidade is None:
        return []
    return list(_index_por_habilidade.get(codigo, []))


def status_mapeamento() -> Dict[str, Any]:
    """Metadata do JSON pra UI mostrar 'mapeamento gerado em DD/MM,
    em revisão' ou 'pipeline ainda não rodou'."""
    data = carregar_mapeamento()
    if data is None:
        return {
            "disponivel": False,
            "status": None,
            "gerado_em": None,
            "total_descritores": 0,
        }
    if data.get("status") == "nao_gerado_ainda":
        return {
            "disponivel": False,
            "status": "nao_gerado_ainda",
            "gerado_em": None,
            "total_descritores": 0,
        }
    return {
        "disponivel": True,
        "status": data.get("status"),
        "gerado_em": data.get("gerado_em"),
        "total_descritores": len(data.get("mapeamentos", [])),
    }
