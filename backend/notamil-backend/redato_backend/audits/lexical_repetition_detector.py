"""
lexical_repetition_detector.py

Detector mecânico de repetição lexical para a Redato.

Roda ANTES da chamada à API da Anthropic e injeta um addendum no contexto
da atividade. Objetivo: corrigir o bias sistemático em que o Sonnet 4.6
confunde repetição lexical (problema de C4) com falta de progressão
semântica (problema de C3) — observado de forma estável em teste_04 mesmo
com ensemble N=3.

A solução é mudar o framing antes do raciocínio do Claude:
em vez de instruir negativamente ("não confunda"), pré-classificamos a
repetição mecanicamente e dizemos afirmativamente ao modelo que ela é
problema de C4 e que ele deve avaliar progressão pela semântica dos
argumentos, não pela diversidade vocabular.

Uso:
    from redato_backend.audits.lexical_repetition_detector import (
        detect_lexical_repetition,
        build_repetition_addendum,
    )

    report = detect_lexical_repetition(student_text)
    addendum = build_repetition_addendum(report)
    if addendum:
        activity_context = f"{activity_context}\n\n{addendum}"

Limiares calibrados via scripts/calibrate_repetition_threshold.py contra os
canários da v2 do calibration set + textos sintéticos com ground truth.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Optional


# ──────────────────────────────────────────────────────────────────────
# CONFIG (resultado da calibração — ver scripts/calibrate_repetition_threshold.py)
# ──────────────────────────────────────────────────────────────────────

# Limiar mínimo de ocorrências de um lemma para entrar no relatório.
# Calibrado 2026-04-25 contra 11 canários v2 + 5 textos sintéticos via
# scripts/calibrate_repetition_threshold.py — min_occ=6 maximiza F1 (0.571).
# Textos de 350+ palavras têm 4-5 ocorrências naturais de palavras-chave do
# tema sem ser repetição mecânica; elevamos o limiar para reduzir FPs.
DEFAULT_MIN_OCCURRENCES = 6

# Para count == 3, exigir que as posições estejam espalhadas pelo texto
# (não cluster local) — span > MIN_SPAN_FOR_TRIPLE entre primeira e última.
MIN_SPAN_FOR_TRIPLE = 50  # em palavras

# Disparar o addendum quando há pelo menos N termos qualificados.
MIN_QUALIFYING_TERMS_TO_FLAG = 1

# Type-token ratio: se TTR for alto demais, suprime o flag mesmo com
# repetições isoladas (texto longo e diverso pode ter 1 termo repetido
# legitimamente, sem ser problema de coesão).
SUPPRESS_FLAG_IF_TTR_ABOVE: Optional[float] = None  # None = sem supressão

# Stopwords PT-BR (sem acentos, lowercased).
# Lista enxuta — pronomes, artigos, preposições, conectivos comuns,
# verbos auxiliares. Não inclui substantivos/verbos lexicais.
_STOPWORDS_PT = frozenset({
    'a', 'o', 'as', 'os', 'um', 'uma', 'uns', 'umas',
    'de', 'da', 'do', 'das', 'dos', 'em', 'na', 'no', 'nas', 'nos',
    'para', 'por', 'com', 'sem', 'sobre', 'sob', 'entre', 'ate', 'desde',
    'e', 'ou', 'mas', 'que', 'se', 'como', 'porem', 'porque', 'pois',
    'eh', 'foi', 'sao', 'ser', 'esta', 'estao', 'ter', 'tem', 'tinha',
    'sua', 'seu', 'suas', 'seus', 'este', 'essa', 'esse', 'esses', 'essas',
    'isto', 'isso', 'aquilo', 'tambem', 'ja', 'ainda', 'mais', 'menos',
    'muito', 'pouco', 'todo', 'toda', 'todos', 'todas', 'cada', 'qual',
    'quando', 'onde', 'aqui', 'ali', 'assim', 'sim', 'nao',
    'eu', 'tu', 'ele', 'ela', 'nos', 'voces', 'eles', 'elas',
    'meu', 'minha', 'teu', 'tua', 'nosso', 'nossa',
    'lhe', 'lhes', 'me', 'te', 'vos',
    'qual', 'quais', 'cujo', 'cuja',
})


# ──────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ──────────────────────────────────────────────────────────────────────

@dataclass
class LexicalRepetition:
    """Um termo repetido com suas ocorrências."""
    term: str
    occurrences: int
    positions: list[int]  # índices em palavras (após filtragem de stopwords)
    spread: bool          # True se as posições não estão clustered

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RepetitionReport:
    """Relatório completo da análise de repetição lexical."""
    has_significant_repetition: bool
    repetitions: list[LexicalRepetition] = field(default_factory=list)
    most_repeated_term: Optional[str] = None
    most_repeated_count: int = 0
    total_unique_lemmas: int = 0
    total_words: int = 0
    total_content_words: int = 0
    type_token_ratio: float = 0.0
    qualifying_count: int = 0  # quantos termos qualificam para o flag

    def to_dict(self) -> dict:
        return {
            'has_significant_repetition': self.has_significant_repetition,
            'repetitions': [r.to_dict() for r in self.repetitions],
            'most_repeated_term': self.most_repeated_term,
            'most_repeated_count': self.most_repeated_count,
            'total_unique_lemmas': self.total_unique_lemmas,
            'total_words': self.total_words,
            'total_content_words': self.total_content_words,
            'type_token_ratio': self.type_token_ratio,
            'qualifying_count': self.qualifying_count,
        }


# ──────────────────────────────────────────────────────────────────────
# TEXT NORMALIZATION
# ──────────────────────────────────────────────────────────────────────

_ACCENT_TABLE = str.maketrans(
    'áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇñÑ',
    'aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUCnN'
)


def _strip_accents(text: str) -> str:
    return text.translate(_ACCENT_TABLE)


def _lemmatize_pt(word: str) -> str:
    """
    Pseudo-lemmatization heurística para PT-BR.
    Não pretende ser linguisticamente correto — só agrupar variações
    flexionais comuns (plural, gênero) sob a mesma chave.
    """
    if len(word) < 5:
        return word
    # Plurais regulares
    if word.endswith('coes'):
        return word[:-4] + 'cao'
    if word.endswith('oes'):
        return word[:-3] + 'ao'
    if word.endswith('ais'):
        return word[:-3] + 'al'
    if word.endswith('eis'):
        return word[:-3] + 'el'
    if word.endswith('ies'):
        return word[:-3] + 'ie'
    if word.endswith('s') and len(word) > 4:
        return word[:-1]
    # Gênero (heurística: feminino → masculino)
    if word.endswith('a') and len(word) > 5:
        return word[:-1] + 'o'
    return word


def _tokenize(text: str) -> list[str]:
    """Tokeniza texto em palavras-conteúdo (sem stopwords, sem pontuação)."""
    cleaned = _strip_accents(text.lower())
    cleaned = re.sub(r'[^\w\s]', ' ', cleaned)
    return [t for t in cleaned.split() if t]


# ──────────────────────────────────────────────────────────────────────
# DETECTOR
# ──────────────────────────────────────────────────────────────────────

def detect_lexical_repetition(
    text: str,
    min_occurrences: int = DEFAULT_MIN_OCCURRENCES,
    min_qualifying_to_flag: int = MIN_QUALIFYING_TERMS_TO_FLAG,
    suppress_above_ttr: Optional[float] = SUPPRESS_FLAG_IF_TTR_ABOVE,
) -> RepetitionReport:
    """
    Analisa repetição lexical no texto. Retorna RepetitionReport.

    Args:
        text: texto da redação
        min_occurrences: mínimo de ocorrências de um lemma para qualificar
        min_qualifying_to_flag: quantos termos qualificados são necessários
            para disparar o flag (has_significant_repetition = True)
        suppress_above_ttr: se TTR > esse valor, suprime o flag mesmo com
            repetições. None = sem supressão.

    Notas:
        - Lemmas com count == 3 só qualificam se as 3 ocorrências estão
          espalhadas pelo texto (span > MIN_SPAN_FOR_TRIPLE entre 1ª e 3ª)
        - Lemmas com count >= min_occurrences sempre qualificam
    """
    tokens = _tokenize(text)

    # Mapeia lemma → {count, positions} considerando só palavras-conteúdo
    lemma_data: dict[str, dict] = {}
    content_idx = 0  # índice em palavras-conteúdo (não conta stopwords)
    for token in tokens:
        if token in _STOPWORDS_PT:
            continue
        if len(token) < 4:
            continue
        lemma = _lemmatize_pt(token)
        entry = lemma_data.setdefault(lemma, {'count': 0, 'positions': []})
        entry['count'] += 1
        entry['positions'].append(content_idx)
        content_idx += 1

    # Identifica repetições qualificadas
    repetitions: list[LexicalRepetition] = []
    for lemma, data in lemma_data.items():
        count = data['count']
        positions = data['positions']
        if count >= min_occurrences:
            repetitions.append(LexicalRepetition(
                term=lemma, occurrences=count, positions=positions, spread=True
            ))
        elif count == 3 and min_occurrences <= 3:
            # Caso especial: triplo só qualifica se espalhado
            span = positions[-1] - positions[0]
            if span > MIN_SPAN_FOR_TRIPLE:
                repetitions.append(LexicalRepetition(
                    term=lemma, occurrences=3, positions=positions, spread=True
                ))

    repetitions.sort(key=lambda r: -r.occurrences)

    total_content = sum(d['count'] for d in lemma_data.values())
    ttr = len(lemma_data) / max(total_content, 1)

    # Decisão de flag
    qualifying = len(repetitions)
    flag = qualifying >= min_qualifying_to_flag
    if flag and suppress_above_ttr is not None and ttr > suppress_above_ttr:
        flag = False

    return RepetitionReport(
        has_significant_repetition=flag,
        repetitions=repetitions[:10],  # top 10
        most_repeated_term=repetitions[0].term if repetitions else None,
        most_repeated_count=repetitions[0].occurrences if repetitions else 0,
        total_unique_lemmas=len(lemma_data),
        total_words=len(tokens),
        total_content_words=total_content,
        type_token_ratio=round(ttr, 3),
        qualifying_count=qualifying,
    )


# ──────────────────────────────────────────────────────────────────────
# ADDENDUM PARA O PROMPT
# ──────────────────────────────────────────────────────────────────────

def build_repetition_addendum(report: RepetitionReport) -> str:
    """
    Constrói o addendum que será injetado no contexto da atividade.

    Retorna string vazia se não há repetição significativa — caller
    deve testar `if addendum:` antes de concatenar.

    O texto é DELIBERADAMENTE AFIRMATIVO (não usa "não confunda" ou
    "evite"). Instruções negativas são ignoradas por LLMs; instruções
    afirmativas com classificação prévia funcionam.
    """
    if not report.has_significant_repetition:
        return ''

    term_list = ', '.join(
        f'"{r.term}" ({r.occurrences}×)' for r in report.repetitions
    )

    return f"""## Diagnóstico mecânico pré-correção

Análise lexical determinística do texto identificou as seguintes repetições:

- Termos repetidos: {term_list}
- Termo mais frequente: "{report.most_repeated_term}" ({report.most_repeated_count} ocorrências)
- Diversidade lexical (type-token ratio): {report.type_token_ratio:.3f}

**Diretriz para esta correção:**

Estas repetições são problema da Competência 4 (coesão lexical), não da Competência 3.

Ao avaliar a Competência 3 (argumentação e progressão):
- Avalie progressão pelo conteúdo semântico dos argumentos, não pela diversidade vocabular.
- Um texto pode ter argumentos que avançam (progressão presente) usando termos repetidos (problema de C4 isolado).
- Marque `c3_audit.progressivas = true` se os argumentos avançam semanticamente, mesmo com repetição lexical.

Ao avaliar a Competência 4 (coesão):
- Esses termos repetidos devem aparecer em `c4_audit.most_used_connector_count` ou em `c4_audit.has_mechanical_repetition` quando aplicável.
- Penalize a repetição em C4 conforme a rubrica."""


# ──────────────────────────────────────────────────────────────────────
# INTEGRAÇÃO COM dev_offline.py
# ──────────────────────────────────────────────────────────────────────

def maybe_inject_repetition_addendum(activity_context: str, student_text: str) -> str:
    """
    Helper de uma chamada para uso direto no _call_claude_with_tool.

    Exemplo de integração:

        # Em _call_claude_with_tool_inner ou onde activity_context é montado:
        from .audits.lexical_repetition_detector import maybe_inject_repetition_addendum
        activity_context = maybe_inject_repetition_addendum(activity_context, student_text)
    """
    report = detect_lexical_repetition(student_text)
    addendum = build_repetition_addendum(report)
    if not addendum:
        return activity_context
    return f"{activity_context}\n\n{addendum}"
