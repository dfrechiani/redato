"""Helper de leitura do `mapeamento_livro_descritores.json` (Fase 5A.1).

Lê o JSON estático gerado pelo script de batch e oferece função pra
sugerir oficinas DO LIVRO baseado nas lacunas do diagnóstico do
aluno + série da turma.

Diferencia da `sugestoes.py` (Fase 3):
- `sugestoes.py` puxa do BANCO (tabela `missoes`) — só oficinas
  AVALIÁVEIS pelo Redato (~23 oficinas)
- `oficinas_livro.py` puxa do JSON do livro — TODAS as oficinas
  pedagógicas (~42 oficinas), incluindo conceituais, jogos,
  diagnósticos, exercícios não-avaliáveis

Cache em memória module-level com mtime check (mesmo padrão de
`descritores.py`). Em prod o JSON não muda em runtime — cache
fica quente após primeira chamada.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Resolução do caminho do JSON
# ──────────────────────────────────────────────────────────────────────

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = _BACKEND_ROOT.parent.parent  # redato_hash/

# Mesma estratégia do descritores.py: bundle dentro do package
# (pra Docker, COPY . . já cobre) + fallback pro path canônico em
# docs/.
PACKAGE_JSON_PATH = str(
    Path(__file__).resolve().parent / "mapeamento_livro_descritores.json"
)
REPO_JSON_PATH = str(
    _REPO_ROOT / "docs/redato/v3/diagnostico/mapeamento_livro_descritores.json"
)


def _resolver_json_path() -> Optional[str]:
    """Retorna path do JSON.

    Ordem:
        1. env REDATO_MAPEAMENTO_LIVROS_JSON (override) — retorna
           SEMPRE, mesmo se file não existir. Caller (carregar_mapeamento)
           detecta a ausência via getmtime/OSError. Isso permite
           testes apontarem o env var pra path inexistente e validarem
           o caminho de "JSON ausente".
        2. PACKAGE_JSON_PATH (bundle pro Docker)
        3. REPO_JSON_PATH (canônico em dev)
        4. None (nada disponível — `carregar_mapeamento` retorna None)
    """
    override = os.environ.get("REDATO_MAPEAMENTO_LIVROS_JSON")
    if override:
        return override  # sempre — override é absoluto
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


def carregar_mapeamento(*, force_reload: bool = False) -> Optional[Dict[str, Any]]:
    """Carrega JSON do mapeamento (cache mtime).

    Returns:
        Dict com a estrutura completa do JSON, ou None se o arquivo
        não existe (caller decide o que mostrar — UI mostra estado
        "mapeamento ainda não gerado, rode o script").
    """
    global _cache_path, _cache_mtime, _cache_data
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
                "[oficinas_livro] falha ao ler %s — JSON corrompido?",
                path,
            )
            return None

        if not isinstance(data, dict) or not isinstance(data.get("oficinas"), list):
            logger.warning(
                "[oficinas_livro] %s tem estrutura inesperada (sem chave 'oficinas')",
                path,
            )
            return None

        _cache_path = path
        _cache_mtime = mtime
        _cache_data = data
        logger.info(
            "[oficinas_livro] cache atualizado: %d oficinas (status=%s, versao=%s)",
            len(data["oficinas"]), data.get("status"), data.get("versao"),
        )
        return _cache_data


# ──────────────────────────────────────────────────────────────────────
# Sugestão por lacunas
# ──────────────────────────────────────────────────────────────────────

# Pesos pra ranking — alta = 3, media = 2, baixa = 1
_PESO_INTENSIDADE = {"alta": 3, "media": 2, "baixa": 1}

MAX_OFICINAS_LIVRO = 5
"""Cap total de sugestões de oficinas do livro pra UI não saturar."""

MAX_POR_DESCRITOR = 3
"""Briefing: max 3 oficinas por descritor."""


@dataclass
class OficinaLivroSugerida:
    """Oficina do livro sugerida pra fechar lacuna específica."""
    codigo: str
    serie: str
    oficina_numero: int
    titulo: str
    tipo_atividade: Optional[str]   # "conceitual" | "pratica" | etc
    tem_redato_avaliavel: bool
    intensidade: str                # "alta" | "media" | "baixa"
    razao: str                      # justificativa do mapeamento (LLM)
    descritor_id: str               # qual lacuna ela ajuda a resolver
    competencias_principais: List[str]
    status_revisao: str             # "em_revisao" | "revisado"

    def to_dict(self) -> dict:
        return {
            "codigo": self.codigo,
            "serie": self.serie,
            "oficina_numero": self.oficina_numero,
            "titulo": self.titulo,
            "tipo_atividade": self.tipo_atividade,
            "tem_redato_avaliavel": self.tem_redato_avaliavel,
            "intensidade": self.intensidade,
            "razao": self.razao,
            "descritor_id": self.descritor_id,
            "competencias_principais": self.competencias_principais,
            "status_revisao": self.status_revisao,
        }


def sugerir_oficinas_livro(
    *,
    lacunas_prioritarias: List[str],
    serie_aluno: str,
    max_por_descritor: int = MAX_POR_DESCRITOR,
    max_total: int = MAX_OFICINAS_LIVRO,
    intensidade_minima: str = "media",
) -> List[OficinaLivroSugerida]:
    """Pra cada lacuna prioritária, busca oficinas do livro
    (filtrado pela série) que trabalhem aquele descritor com
    intensidade >= `intensidade_minima`.

    Args:
        lacunas_prioritarias: IDs de descritores em ordem de
            prioridade (output da Fase 2/3).
        serie_aluno: "1S" | "2S" | "3S".
        max_por_descritor: max 3 oficinas por descritor.
        max_total: cap global na lista final (default 5).
        intensidade_minima: "alta" | "media" | "baixa". "media" é
            sensato — descritores com intensidade "baixa" da oficina
            são sinal fraco (conteúdo tangencial).

    Returns:
        Lista deduplicada de OficinaLivroSugerida ordenada por:
        1. Posição da lacuna no top (mais prioritárias primeiro)
        2. Intensidade (alta > media > baixa)
        3. Oficina avaliável antes de não-avaliável (preferência
           pedagógica — aluno produz texto)
        4. oficina_numero ascendente (curso seguindo ordem do livro)

        Vazia se mapeamento ainda não foi gerado (script não rodou).
    """
    data = carregar_mapeamento()
    if data is None:
        return []

    if serie_aluno not in ("1S", "2S", "3S"):
        return []

    # Filtros básicos: série certa + sem mapeamento_falhou
    oficinas_serie = [
        o for o in data["oficinas"]
        if isinstance(o, dict)
        and o.get("serie") == serie_aluno
        and not o.get("mapeamento_falhou", False)
    ]
    if not oficinas_serie:
        return []

    # Threshold de intensidade
    minimo = _PESO_INTENSIDADE.get(intensidade_minima, 2)

    # Itera lacunas EM ORDEM (prioridade preservada). Pra cada,
    # acha oficinas que trabalham aquele descritor com peso >= minimo.
    out: List[OficinaLivroSugerida] = []
    vistas: set = set()
    status_global = data.get("status", "em_revisao")
    for did in lacunas_prioritarias:
        if not isinstance(did, str):
            continue
        candidatas: List[Dict[str, Any]] = []
        for o in oficinas_serie:
            for dt in o.get("descritores_trabalhados", []) or []:
                if not isinstance(dt, dict):
                    continue
                if dt.get("id") != did:
                    continue
                peso = _PESO_INTENSIDADE.get(dt.get("intensidade", ""), 0)
                if peso < minimo:
                    continue
                candidatas.append({
                    "oficina": o,
                    "descritor": dt,
                    "peso": peso,
                })
        # Ordena candidatas: peso desc, avaliável antes, num asc
        candidatas.sort(key=lambda c: (
            -c["peso"],
            0 if c["oficina"].get("tem_redato_avaliavel") else 1,
            c["oficina"].get("oficina_numero", 99),
        ))
        # Adiciona até max_por_descritor (dedup global por código)
        adicionadas = 0
        for c in candidatas:
            if adicionadas >= max_por_descritor:
                break
            if len(out) >= max_total:
                break
            of = c["oficina"]
            codigo = of.get("codigo")
            if not codigo or codigo in vistas:
                continue
            vistas.add(codigo)
            out.append(OficinaLivroSugerida(
                codigo=codigo,
                serie=of.get("serie", serie_aluno),
                oficina_numero=int(of.get("oficina_numero", 0)),
                titulo=of.get("titulo", ""),
                tipo_atividade=of.get("tipo_atividade"),
                tem_redato_avaliavel=bool(of.get("tem_redato_avaliavel")),
                intensidade=c["descritor"].get("intensidade", "media"),
                razao=c["descritor"].get("razao", ""),
                descritor_id=did,
                competencias_principais=list(
                    of.get("competencias_principais", []) or []
                ),
                status_revisao=status_global,
            ))
            adicionadas += 1
        if len(out) >= max_total:
            break

    return out


def sugestoes_to_dicts(s: List[OficinaLivroSugerida]) -> List[Dict[str, Any]]:
    return [x.to_dict() for x in s]


def status_mapeamento() -> Dict[str, Any]:
    """Retorna metadata do JSON pra UI mostrar 'mapeamento gerado em
    DD/MM, status: em_revisao'. Estado vazio se JSON não existe."""
    data = carregar_mapeamento()
    if data is None:
        return {
            "disponivel": False,
            "status": None,
            "gerado_em": None,
            "total_oficinas": 0,
        }
    return {
        "disponivel": True,
        "status": data.get("status"),
        "gerado_em": data.get("gerado_em"),
        "total_oficinas": len(data.get("oficinas", [])),
    }
