"""Mapeador heurístico (Fase 5A.1, fallback sem LLM).

Gera mapeamento inicial baseado em keyword matching no conteúdo
da oficina. NÃO é o caminho preferido — o real é via GPT-4.1
(`mapeador.py`). Este existe pra:

1. **Bootstrap**: gerar JSON baseline antes do Daniel rodar o
   pipeline LLM, pra UI poder funcionar end-to-end durante
   desenvolvimento e validação.
2. **Smoke**: sanity check que o parser está extraindo conteúdo
   suficiente pra mapeamento (se heurístico não bate em nada,
   parser ou conteúdo da oficina estão furados).
3. **Diff baseline**: depois que LLM rodar, dá pra comparar
   heurístico vs LLM pra ver onde LLM agregou valor / errou.

Output marca explicitamente `gerador: 'heuristico'` no JSON pra
diferenciar do output LLM (`gerador: 'gpt-4.1'`). UI mostra aviso
distinto.

Heurística:
- Tabela de keywords → descritores (escrita à mão, baseada nos
  campos `nome` e `definicao` do YAML)
- Pra cada oficina, conta matches e atribui intensidade:
    >= 5 matches por descritor → alta
    2-4 matches → media
    1 match → baixa (filtrado por threshold padrão)
- Sem LLM = sem nuance. Pode dar falsos positivos (oficina que
  menciona "tese" só de passagem) e falsos negativos (oficina
  trabalha estrutura argumentativa sem usar a palavra "tese").
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

from redato_backend.diagnostico.descritores import (
    Descritor, load_descritores,
)
from redato_backend.diagnostico.mapeador import (
    DescritorTrabalhado, MapeamentoOficina,
)
from redato_backend.diagnostico.parser_livros import OficinaLivro

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Keywords → descritores
# ──────────────────────────────────────────────────────────────────────
#
# Heurística manual: pra cada um dos 40 descritores, lista de
# keywords (regex case-insensitive) que sinalizam que a oficina
# trabalha aquele descritor. Match incrementa peso.
#
# Manter sincronizado com descritores.yaml — quando descritor for
# adicionado/removido lá, atualizar aqui.

_KEYWORDS: Dict[str, List[str]] = {
    # ── C1 — Norma culta ──────────────────────────────────────────
    "C1.001": [r"\bsujeito\b", r"\bperíodo\b", r"\bestrutura\s+sintática\b",
               r"\bfragmento\b", r"\boração\b"],
    "C1.002": [r"\bacent(o|uação)\b", r"\bóxiton\b", r"\bproparóxiton\b",
               r"\bporquê\b"],
    "C1.003": [r"\bortografia\b", r"\bmal/mau\b", r"\bmais/mas\b",
               r"\bencima\b", r"\bafim\b"],
    "C1.004": [r"\bvírgula\b", r"\bpontuação\b", r"\bdois.pontos\b",
               r"\bponto.e.vírgula\b"],
    "C1.005": [r"\bconcord(â|a)ncia\b", r"\bsujeito\s+composto\b",
               r"\bhouveram\b", r"\bfazem\s+\d+\s+anos\b"],
    "C1.006": [r"\bregência\b", r"\bpreposição\b", r"\baspirar\s+a\b",
               r"\bpreferir\s+a\b", r"\bobediência\b"],
    "C1.007": [r"\bregistro\s+formal\b", r"\bcoloquial\b", r"\bgíria\b",
               r"\binformal\b", r"\bnorma\s+padrão\b"],
    "C1.008": [r"\bvocabulário\b", r"\bsinônim\b", r"\bpalavra\s+precisa\b",
               r"\brepetição\b"],

    # ── C2 — Compreensão da proposta ──────────────────────────────
    "C2.001": [r"\bpertinência\s+ao\s+tema\b", r"\bfuga\s+do\s+tema\b",
               r"\btangenciar\b", r"\babordagem\s+do\s+tema\b"],
    "C2.002": [r"\brecorte\s+temático\b", r"\bângulo\b",
               r"\bproblemática\s+específica\b"],
    "C2.003": [r"\bdissertativ\b", r"\bargumentativ\b",
               r"\bestrutura\s+textual\b", r"\bintrodução.*conclus(ã|a)o\b",
               r"\bintrodução\s+desenvolvimento\b"],
    "C2.004": [r"\b3ª?\s+pessoa\b", r"\bpresente\s+do\s+indicativo\b",
               r"\bimpessoalidade\b"],
    "C2.005": [r"\brepertório\b", r"\bcitação\b", r"\bautor\b",
               r"\bdado\b", r"\bfato\s+histórico\b", r"\blei\b"],
    "C2.006": [r"\bpertinência\s+do\s+repertório\b",
               r"\brepertório.*tema\b", r"\bdialogar\s+com\s+o\s+tema\b"],
    "C2.007": [r"\brepertório\s+produtivo\b",
               r"\bextrair\s+consequência\b",
               r"\busar\s+o\s+repertório\b"],
    "C2.008": [r"\brepertório\s+de\s+bolso\b",
               r"\bestudos\s+mostram\b", r"\bpesquisas\s+indicam\b",
               r"\bnomeáv\b", r"\bfonte\s+verificáv\b"],

    # ── C3 — Argumentação ─────────────────────────────────────────
    "C3.001": [r"\btese\b", r"\bposicionamento\b", r"\bponto\s+de\s+vista\b"],
    "C3.002": [r"\bsustent(ar|ação)\s+(da\s+)?tese\b",
               r"\bdefend(er|esa)\s+(a\s+)?tese\b",
               r"\bargumento.*tese\b"],
    "C3.003": [r"\btópico\s+frasal\b", r"\bideia.guia\b",
               r"\babertura\s+do\s+parágrafo\b"],
    "C3.004": [r"\bprofundidade\s+do\s+argumento\b",
               r"\bcausa.*consequência\b",
               r"\bmecanismo\b", r"\bargumenta(r|ção)\s+consistent\b"],
    "C3.005": [r"\bdiversidade\s+(de\s+)?argumentos\b",
               r"\bD1\s*≠\s*D2\b", r"\bd1\s+e\s+d2\s+diferentes\b"],
    "C3.006": [r"\barticulação.*(tese|conclusão)\b",
               r"\bfio\s+condutor\b"],
    "C3.007": [r"\bdefesa\s+de\s+ponto\s+de\s+vista\b",
               r"\bredação\s+descritiva\b",
               r"\bjuízo\s+argumentativo\b"],
    "C3.008": [r"\bautoria\b", r"\bvoz\s+própria\b",
               r"\bsenso\s+comum\b"],

    # ── C4 — Coesão textual ───────────────────────────────────────
    "C4.001": [r"\bvariedade\s+de\s+conectivos\b",
               r"\bconectivo\b.*\bcategoria\b",
               r"\balém\s+disso\b"],
    "C4.002": [r"\badequação\s+(do|do\s+)?conectivo\b",
               r"\brelação\s+lógica\b"],
    "C4.003": [r"\bconectivo\s+entre\s+parágrafos\b",
               r"\btransição\s+entre\s+parágrafos\b"],
    "C4.004": [r"\breferenciação\b", r"\banafóric\b",
               r"\bpronome\s+(retomada|anafórico)\b"],
    "C4.005": [r"\bambiguidade\b", r"\bantecedente\s+claro\b",
               r"\b['\"]isso['\"]\s+(sem\s+)?antecedente\b"],
    "C4.006": [r"\bprogressão\s+temática\b",
               r"\binformação\s+nova\b", r"\bd2\s+repete\s+d1\b"],
    "C4.007": [r"\bartic(u|i)lação\s+intraparágrafo\b",
               r"\borações\s+justapostas\b"],
    "C4.008": [r"\btransição\s+estrutural\b",
               r"\bem\s+primeiro\s+lugar\b",
               r"\bademais\b", r"\bdiante\s+(do\s+)?expost\b"],

    # ── C5 — Proposta de intervenção ──────────────────────────────
    "C5.001": [r"\bagente\b.*\bpropost\b", r"\bquem\s+vai\s+executar\b",
               r"\bministério\b.*\bpropost\b"],
    "C5.002": [r"\bação\s+da\s+propost\b", r"\bverbo\s+de\s+ação\b",
               r"\bcombater\b", r"\blutar\s+contra\b"],
    "C5.003": [r"\bmeio.*propost\b", r"\bcomo\s+a\s+ação\b",
               r"\bpor\s+meio\s+de\b", r"\batravés\s+de\b"],
    "C5.004": [r"\bfinalidade\s+da\s+propost\b", r"\bpara\s+que\b",
               r"\ba\s+fim\s+de\b"],
    "C5.005": [r"\bdetalhamento\s+(da\s+)?propost\b",
               r"\bexpandir\s+o\s+elemento\b"],
    "C5.006": [r"\bpropost(a|as)?\s+articulada\b",
               r"\bpropost.*problema\s+discutido\b"],
    "C5.007": [r"\bdireitos\s+humanos\b",
               r"\bpunitivismo\b", r"\bviolência\s+institucional\b"],
    "C5.008": [r"\b5\s+elementos\s+da\s+propost\b",
               r"\bcompletude\s+da\s+propost\b",
               r"\bagente\s+\+\s+ação\s+\+\s+meio\b"],
}


# ──────────────────────────────────────────────────────────────────────
# Inferência de tipo da atividade por keywords
# ──────────────────────────────────────────────────────────────────────

_TIPO_KEYWORDS: List[tuple] = [
    (r"\bdiagnóstico\b|\bautoavaliação\b|\bsondagem\b", "diagnostico"),
    (r"\bsimulado\b|\bredação\s+completa\b|\bavaliação\b", "avaliativa"),
    (r"\bjogo\b|\bdinâmica\b|\bcartas?\b|\bleilão\b", "jogo"),
    (r"\bprática\b|\bexercício\b|\bproduç(ã|a)o\s+text\b", "pratica"),
]


def _inferir_tipo(oficina: OficinaLivro) -> str:
    """Heurística simples baseada em título + conteúdo."""
    texto = (oficina.titulo + " " + oficina.conteudo_consolidado(2000)).lower()
    for pattern, tipo in _TIPO_KEYWORDS:
        if re.search(pattern, texto, re.IGNORECASE):
            return tipo
    # Fallback: se tem mf-redato-page, é avaliativa; senão conceitual
    return "avaliativa" if oficina.tem_redato_avaliavel else "conceitual"


# ──────────────────────────────────────────────────────────────────────
# Mapeamento principal
# ──────────────────────────────────────────────────────────────────────

def _intensidade_por_score(score: int) -> Optional[str]:
    """Score = número de matches de keywords distintos.
    >=5 alta, 2-4 media, 1 baixa, 0 não inclui.
    """
    if score >= 5:
        return "alta"
    if score >= 2:
        return "media"
    if score >= 1:
        return "baixa"
    return None


def mapear_oficina_heuristico(
    oficina: OficinaLivro,
    *,
    descritores_yaml: Optional[List[Descritor]] = None,
    incluir_baixa: bool = False,
) -> MapeamentoOficina:
    """Versão heurística do mapper. NÃO chama LLM.

    Args:
        oficina: extraída pelo parser.
        descritores_yaml: lista dos 40. Se None, carrega.
        incluir_baixa: se True, inclui descritores com 1 match.
            Default False — filtra ruído.

    Returns:
        MapeamentoOficina com modelo_usado='heuristico-v1' pra
        distinguir do output LLM. latencia/custo = 0.
    """
    if descritores_yaml is None:
        descritores_yaml = load_descritores()
    yaml_ids = {d.id for d in descritores_yaml}

    # Texto consolidado pra busca (lower pra case-insensitive já no regex)
    texto = (
        oficina.titulo + " "
        + oficina.conteudo_consolidado(8000)
    )

    # Conta matches por descritor
    matches: Dict[str, int] = {}
    razoes: Dict[str, List[str]] = {}
    for did, patterns in _KEYWORDS.items():
        if did not in yaml_ids:
            continue
        score = 0
        razoes_id: List[str] = []
        for p in patterns:
            try:
                hits = re.findall(p, texto, re.IGNORECASE)
            except re.error:
                continue
            if hits:
                score += len(hits)
                # Pega 1 termo representativo pra justificar
                term = hits[0] if isinstance(hits[0], str) else str(hits[0])
                razoes_id.append(term.strip())
        if score > 0:
            matches[did] = score
            razoes[did] = razoes_id[:3]

    # Constrói descritores_trabalhados (cap 8, ordenado por score desc)
    descritores_trabalhados: List[DescritorTrabalhado] = []
    yaml_lookup = {d.id: d for d in descritores_yaml}
    candidatos = sorted(matches.items(), key=lambda kv: -kv[1])
    for did, score in candidatos[:8]:
        intensidade = _intensidade_por_score(score)
        if intensidade is None:
            continue
        if intensidade == "baixa" and not incluir_baixa:
            continue
        nome = yaml_lookup[did].nome if did in yaml_lookup else did
        razao = (
            f"Heurística (NÃO-LLM): {score} matches em keywords "
            f"associados a '{nome}' — termos: {', '.join(razoes.get(did, [])[:3])}"
        )
        descritores_trabalhados.append(DescritorTrabalhado(
            id=did, intensidade=intensidade, razao=razao,
        ))

    # Competências principais: top 3 que têm pelo menos 1 descritor
    contagem_comp: Dict[str, int] = {}
    for d in descritores_trabalhados:
        comp = d.id[:2]
        contagem_comp[comp] = contagem_comp.get(comp, 0) + (
            3 if d.intensidade == "alta" else 2 if d.intensidade == "media" else 1
        )
    top_comps = sorted(contagem_comp.items(), key=lambda kv: -kv[1])[:3]
    competencias = [c for c, _ in top_comps]

    return MapeamentoOficina(
        codigo=oficina.codigo,
        serie=oficina.serie,
        oficina_numero=oficina.oficina_numero,
        titulo=oficina.titulo,
        tem_redato_avaliavel=oficina.tem_redato_avaliavel,
        descritores_trabalhados=descritores_trabalhados,
        competencias_principais=competencias,
        tipo_atividade=_inferir_tipo(oficina),
        modelo_usado="heuristico-v1",
        latencia_ms=0,
        custo_estimado_usd=0.0,
        input_tokens=0,
        output_tokens=0,
    )
