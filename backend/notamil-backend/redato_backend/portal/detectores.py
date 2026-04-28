"""Catálogo canônico de detectores pedagógicos (M7).

A correção da Redato pode acionar detectores estruturais, argumentativos,
linguísticos e de forma. Em M6 a UI tratava qualquer chave do
`redato_output` que começasse com `flag_`/`detector_`/`alerta_`/`aviso_`
como detector e humanizava substituindo `_` por espaço.

Em M7, formalizamos a lista. Filtros do dashboard mostram só detectores
canônicos no top-N; chaves desconhecidas vão pra agregado "outros". A
função `humanize_detector` segue funcionando pra detectores não
cadastrados (fallback gracioso) — útil em testes piloto onde
detectores experimentais aparecem antes de virarem canônicos.

Convenções:
- `codigo`: snake_case ASCII, prefixo `flag_`/`detector_`/`alerta_`/
  `aviso_` opcional. Mantemos prefix-stripping em humanize.
- `nome_humano`: título em português, sem ponto final.
- `categoria`: 'estrutural' | 'argumentativo' | 'linguistico' |
  'ortografico' | 'forma'.
- `severidade`: 'alta' | 'media' | 'baixa'. Indica o peso pedagógico —
  alta sinaliza problema que invalida competência inteira, média afeta
  parcialmente, baixa é nuance.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional


SEVERIDADES = ("alta", "media", "baixa")
CATEGORIAS = (
    "estrutural", "argumentativo", "linguistico", "ortografico", "forma",
)


@dataclass(frozen=True)
class DetectorCanonico:
    codigo: str
    nome_humano: str
    categoria: str
    severidade: str


# ──────────────────────────────────────────────────────────────────────
# Lista canônica (fonte de verdade)
# ──────────────────────────────────────────────────────────────────────

_CANONICOS: List[DetectorCanonico] = [
    # — Estrutural —
    DetectorCanonico("estrutura_dissertativa_falha", "Estrutura dissertativa falha",
                     "estrutural", "alta"),
    DetectorCanonico("titulo_inadequado", "Título inadequado",
                     "estrutural", "baixa"),
    DetectorCanonico("introducao_fraca", "Introdução fraca",
                     "estrutural", "media"),
    DetectorCanonico("conclusao_ausente", "Conclusão ausente",
                     "estrutural", "alta"),
    DetectorCanonico("proposta_vaga", "Proposta de intervenção vaga",
                     "estrutural", "alta"),
    DetectorCanonico("proposta_ausente", "Proposta de intervenção ausente",
                     "estrutural", "alta"),
    DetectorCanonico("texto_curto", "Texto muito curto",
                     "estrutural", "alta"),

    # — Argumentativo —
    DetectorCanonico("tese_ausente", "Tese ausente",
                     "argumentativo", "alta"),
    DetectorCanonico("argumentacao_circular", "Argumentação circular",
                     "argumentativo", "media"),
    DetectorCanonico("argumentacao_previsivel", "Argumentação previsível",
                     "argumentativo", "baixa"),
    DetectorCanonico("repertorio_ausente", "Repertório ausente",
                     "argumentativo", "media"),
    DetectorCanonico("repertorio_fraco", "Repertório fraco",
                     "argumentativo", "baixa"),
    DetectorCanonico("falacia_argumentativa", "Falácia argumentativa",
                     "argumentativo", "media"),
    DetectorCanonico("generalizacao_indevida", "Generalização indevida",
                     "argumentativo", "media"),
    DetectorCanonico("andaime_copiado", "Andaime copiado do enunciado",
                     "argumentativo", "alta"),

    # — Linguístico —
    DetectorCanonico("repeticao_lexical", "Repetição lexical",
                     "linguistico", "baixa"),
    DetectorCanonico("conectivos_insuficientes", "Conectivos insuficientes",
                     "linguistico", "media"),
    DetectorCanonico("coesao_problematica", "Coesão problemática",
                     "linguistico", "media"),
    DetectorCanonico("vocabulario_pobre", "Vocabulário pobre",
                     "linguistico", "baixa"),
    DetectorCanonico("registro_inadequado", "Registro linguístico inadequado",
                     "linguistico", "media"),

    # — Ortográfico —
    DetectorCanonico("erros_ortograficos_leves", "Erros ortográficos leves",
                     "ortografico", "baixa"),
    DetectorCanonico("erros_ortograficos_graves", "Erros ortográficos graves",
                     "ortografico", "media"),
    DetectorCanonico("pontuacao_problematica", "Pontuação problemática",
                     "ortografico", "baixa"),

    # — Forma / qualidade da imagem —
    DetectorCanonico("ilegivel_parcial", "Trecho ilegível",
                     "forma", "alta"),
    DetectorCanonico("letra_ruim", "Letra de difícil leitura",
                     "forma", "baixa"),
    DetectorCanonico("rasura_excessiva", "Rasura excessiva",
                     "forma", "baixa"),
]


# Index por código pra lookup O(1).
_BY_CODIGO: Dict[str, DetectorCanonico] = {d.codigo: d for d in _CANONICOS}


def canonical_detectores() -> Dict[str, DetectorCanonico]:
    """Retorna dict imutável codigo → DetectorCanonico."""
    return dict(_BY_CODIGO)


def is_canonical(codigo: str) -> bool:
    """`codigo` pode vir cru (ex.: 'flag_proposta_vaga') ou já normalizado
    ('proposta_vaga'). Considera ambos."""
    return _normalize_codigo(codigo) in _BY_CODIGO


def get_canonical(codigo: str) -> Optional[DetectorCanonico]:
    return _BY_CODIGO.get(_normalize_codigo(codigo))


_PREFIX_RE = re.compile(r"^(flag|detector|alerta|aviso)_", re.IGNORECASE)


def _normalize_codigo(raw: str) -> str:
    """Remove prefixos `flag_`/`detector_`/`alerta_`/`aviso_` e
    normaliza pra lowercase. Retorna string vazia se input inválido."""
    if not isinstance(raw, str):
        return ""
    s = _PREFIX_RE.sub("", raw.strip()).lower()
    # tolera espaços/hífens vindos de input humano
    s = s.replace(" ", "_").replace("-", "_")
    # remove duplos underscores
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_")


def humanize_detector(codigo: str) -> str:
    """Devolve nome legível.

    - Se o código está no catálogo canônico, usa `nome_humano`.
    - Senão, faz fallback gracioso: tira prefixos, troca `_` por espaço,
      capitaliza primeiro caractere. Ex.: `flag_proposta_irregular`
      → 'Proposta irregular'.
    """
    norm = _normalize_codigo(codigo)
    if not norm:
        return "Detector"
    canon = _BY_CODIGO.get(norm)
    if canon is not None:
        return canon.nome_humano
    # Fallback: capitaliza só primeira letra, mantém resto em
    # minúsculas (estilo "Proposta irregular"), troca _ por espaço.
    espacado = norm.replace("_", " ")
    return espacado[0].upper() + espacado[1:] if espacado else "Detector"


def severidade_de(codigo: str) -> str:
    """Severidade canônica ou 'media' como default seguro."""
    canon = get_canonical(codigo)
    return canon.severidade if canon else "media"


def categoria_de(codigo: str) -> str:
    """Categoria canônica ou 'forma' como default genérico."""
    canon = get_canonical(codigo)
    return canon.categoria if canon else "forma"
