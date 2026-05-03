"""Sugestões pedagógicas pra cada um dos 40 descritores.

Dicionário fixo descritor → sugestão concreta de COMO o professor
trabalha aquela lacuna com o aluno. 1-2 frases por entrada,
linguagem direta de orientação didática.

Decisões de design (Daniel, fix Fase 3 #3):
- Linguagem voz-de-mentor pra professor (não pro aluno).
- Sugestão acionável: "Mostre exemplos de X" / "Exercite Y" /
  "Trabalhe com aluno Z".
- Pequenas o suficiente pra caber num card de UI sem rolagem.
- Manter sincronizado com docs/redato/v3/diagnostico/descritores.yaml
  e com metas.py — atualizações coordenadas via PR.

Uso:
    from redato_backend.diagnostico.sugestoes_pedagogicas import (
        get_sugestao_pedagogica,
    )
    texto = get_sugestao_pedagogica("C5.001")
"""
from __future__ import annotations

import logging
from typing import Dict

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Dicionário 40 descritores → sugestão pedagógica
# ──────────────────────────────────────────────────────────────────────
#
# Estrutura: cada string é 1-2 frases. Pode incluir indicação de
# exercício específico ("Exercite pergunta 'mas por quê?'") ou
# referência a material ("Liste exemplos da própria redação dele").
# Quando houver oficinas dedicadas no livro, mencionar — mas o
# mapping descritor→oficina fica em `sugestoes.py` (entregável
# separado da UI).

_SUGESTOES: Dict[str, str] = {
    # ── C1 — Norma culta ──────────────────────────────────────────
    "C1.001": (
        "Trabalhe identificação de sujeito + verbo + complemento em "
        "frases reais. Peça pro aluno marcar essas 3 partes em 5 "
        "frases da própria redação — fragmentos ficam evidentes."
    ),
    "C1.002": (
        "Revise as regras de acentuação por grupos (oxítonas, "
        "paroxítonas, casos especiais como porquê). Liste os erros "
        "do aluno pra ele ver o padrão dele e corrigir o subset."
    ),
    "C1.003": (
        "Faça lista das confusões clássicas (mal/mau, mais/mas, "
        "há/a) com 1 frase de exemplo de cada. Aluno reescreve as "
        "frases trocando intencionalmente — fixa pelo contraste."
    ),
    "C1.004": (
        "Mostre os 4 casos onde NÃO se usa vírgula (sujeito-verbo, "
        "verbo-complemento, etc.) E os 4 onde SE USA (oração "
        "subordinada deslocada, vocativo). Depois exercite na "
        "redação dele."
    ),
    "C1.005": (
        "Concordância tem padrões previsíveis: revise com aluno os "
        "casos clássicos (sujeito posposto, expressões de "
        "quantidade, 'haver' impessoal). Liste exemplos da própria "
        "redação dele."
    ),
    "C1.006": (
        "Foque nos 5 verbos que mais caem no ENEM: aspirar, "
        "preferir, esquecer-se, obedecer, simpatizar. Pra cada um, "
        "mostre 1 frase certa + 1 errada — aluno aponta a errada."
    ),
    "C1.007": (
        "Mostre lista de 'palavras vermelhas' (tipo, né, pra, vc, "
        "a gente). Aluno relê redação caçando essas palavras e "
        "substitui por equivalente formal."
    ),
    "C1.008": (
        "Faça exercício de sinônimos contextualizados: dê 5 frases "
        "com palavras imprecisas e peça aluno reescrever com termo "
        "técnico adequado. Reforça vocabulário argumentativo."
    ),

    # ── C2 — Compreensão da proposta ──────────────────────────────
    "C2.001": (
        "Trabalhe a leitura ativa da proposta: aluno sublinha "
        "palavras-chave do enunciado e do tema, depois confere se "
        "todas aparecem no texto dele. Fuga vira visível."
    ),
    "C2.002": (
        "Exercite o recorte: dê um tema amplo e peça 3 recortes "
        "diferentes (ex.: 'violência' → estrutural, midiática, "
        "doméstica). Aluno escolhe um e defende — não tudo."
    ),
    "C2.003": (
        "Mostre 4 textos curtos (dissertativo, narrativo, "
        "epistolar, descritivo) sobre o mesmo tema. Aluno "
        "identifica qual é qual e por quê — fixa marcadores do "
        "tipo dissertativo."
    ),
    "C2.004": (
        "Liste verbos-tipo no presente do indicativo, 3ª pessoa "
        "(argumenta-se, mostra-se, evidencia). Aluno reescreve "
        "trecho narrativo dele em modo dissertativo, mantendo a "
        "ideia."
    ),
    "C2.005": (
        "Construa banco de repertório por tema (3-5 referências "
        "sociocultural por tema recorrente do ENEM). Aluno escolhe "
        "1 antes de escrever e integra deliberadamente."
    ),
    "C2.006": (
        "Mostre 2 versões de uma redação: uma com citação 'colada' "
        "e outra com citação integrada. Aluno aponta a diferença e "
        "reescreve a colada dele aplicando integração."
    ),
    "C2.007": (
        "Exercite a 'extração de consequência': dê uma citação e "
        "peça aluno escrever a frase que vem DEPOIS, conectando "
        "a citação à tese. Sempre 2 frases mínimo por repertório."
    ),
    "C2.008": (
        "Mostre lista de fórmulas genéricas que NÃO contam como "
        "repertório ('estudos mostram', 'pesquisas indicam'). "
        "Aluno troca por nome real (autor, lei, dado com fonte). "
        "Use bancos como o Brasil Escola pra encontrar fontes."
    ),

    # ── C3 — Argumentação ─────────────────────────────────────────
    "C3.001": (
        "Trabalhe a fórmula da tese: 'X deve ser feito porque Y'. "
        "Aluno escreve 5 teses sobre temas diferentes seguindo o "
        "padrão antes de redigir a próxima redação inteira."
    ),
    "C3.002": (
        "Faça aluno marcar a tese com cor 1 e cada argumento com "
        "cor 2. Conferir visualmente se todo argumento defende a "
        "tese — desvios ficam evidentes pelo mapa de cores."
    ),
    "C3.003": (
        "Exercite tópico frasal: pra cada parágrafo de "
        "desenvolvimento, aluno escreve 1 frase-resumo ANTES de "
        "começar a desenvolver. Essa frase vira o tópico."
    ),
    "C3.004": (
        "Aluno está descrevendo, não argumentando. Mostre estrutura "
        "'porque + mecanismo + consequência'. Exercite pergunta "
        "'mas por quê?' até chegar na raiz."
    ),
    "C3.005": (
        "Trabalhe os 4 pares clássicos pra D1 vs D2: causa "
        "estrutural × cultural; histórico × atual; econômico × "
        "social; público × privado. Aluno escolhe par antes de "
        "escrever."
    ),
    "C3.006": (
        "Faça aluno conferir: a conclusão retoma A TESE, não o tema "
        "geral? Os argumentos estão alinhados? Use exercício de "
        "'reduzir a redação a 3 frases' — fio condutor aparece."
    ),
    "C3.007": (
        "Mostre 2 textos: um descritivo (lista causas/efeitos) e um "
        "argumentativo (defende leitura). Aluno aponta a diferença "
        "e reescreve trecho descritivo dele em tom argumentativo."
    ),
    "C3.008": (
        "Trabalhe fechamento autoral: aluno relê redação e marca "
        "frases que poderiam estar em qualquer outra redação "
        "(senso comum). Reescreve essas frases com inferência "
        "própria."
    ),

    # ── C4 — Coesão textual ───────────────────────────────────────
    "C4.001": (
        "Liste 5 categorias de conectivos (causa, consequência, "
        "oposição, adição, conclusão) com 3 exemplos de cada. "
        "Aluno usa pelo menos 1 de cada categoria na próxima "
        "redação."
    ),
    "C4.002": (
        "Exercite 'qual relação?': dê 10 pares de orações e aluno "
        "escolhe o conectivo certo entre 4 opções. Reforça que "
        "conectivo = relação lógica, não decoração."
    ),
    "C4.003": (
        "Trabalhe os marcadores de transição entre parágrafos: "
        "'Em primeiro lugar', 'Ademais', 'Por fim', 'Diante "
        "disso'. Aluno usa um diferente em cada parágrafo da "
        "próxima redação."
    ),
    "C4.004": (
        "Faça exercício de retomada: aluno reescreve um parágrafo "
        "dele substituindo TODA repetição de substantivo por "
        "pronome ou sinônimo. Compare antes e depois — fluência "
        "muda."
    ),
    "C4.005": (
        "Mostre exemplos de 'isso' ambíguo (com 3 antecedentes "
        "possíveis) e ensine a reescrever com 'tal questão', "
        "'esse problema'. Treinar na própria redação dele."
    ),
    "C4.006": (
        "Trabalhe progressão temática: aluno marca a IDEIA NOVA "
        "de cada parágrafo. Se 2 parágrafos têm a mesma ideia, "
        "fundir ou cortar um."
    ),
    "C4.007": (
        "Identifique parágrafos com orações justapostas (sem "
        "conectivo). Aluno reescreve adicionando 'porque', "
        "'assim', 'logo' entre orações vizinhas — revela ou "
        "supre conexões."
    ),
    "C4.008": (
        "Marque as 4 transições estruturais (intro→D1, D1→D2, "
        "D2→conclusão). Aluno confere se cada uma tem marcador "
        "explícito; se não, adiciona."
    ),

    # ── C5 — Proposta de intervenção ──────────────────────────────
    "C5.001": (
        "Mostre exemplos de propostas com agentes específicos "
        "(Ministério da Educação, ONGs locais) vs genéricos (a "
        "sociedade). Trabalhe com aluno o exercício de substituir "
        "'todos' por agente nomeado."
    ),
    "C5.002": (
        "Liste verbos de ação concreta (criar, implementar, "
        "fiscalizar, ampliar, reduzir) vs verbos vagos (combater, "
        "lutar contra). Aluno reescreve proposta dele trocando "
        "vagos por concretos."
    ),
    "C5.003": (
        "Treine o conector 'por meio de' / 'através de' como "
        "ponte obrigatória entre ação e finalidade. Sem o meio, "
        "proposta soa como ordem genérica — mostre 2 versões pra "
        "aluno comparar."
    ),
    "C5.004": (
        "Trabalhe a estrutura final da proposta: 'AGENTE faz AÇÃO "
        "por meio de MEIO PARA finalidade'. Aluno escreve 3 "
        "propostas seguindo o template antes de fazer livre."
    ),
    "C5.005": (
        "Mostre exemplo de proposta com 5 elementos crus vs com "
        "1 elemento detalhado (qualifica agente OU especifica "
        "ação). Detalhar 1 transforma a nota — exercite essa "
        "expansão."
    ),
    "C5.006": (
        "Faça aluno listar: o que D1 e D2 discutiram? A proposta "
        "ataca esse problema específico ou virou genérica? "
        "Reescrever proposta amarrando explicitamente aos "
        "afetados nomeados nos desenvolvimentos."
    ),
    "C5.007": (
        "Mostre lista de propostas que VIOLAM direitos humanos "
        "(violência institucional, exclusão, pena de morte). "
        "Aluno aponta o que viola e por quê — fixa o critério "
        "eliminatório."
    ),
    "C5.008": (
        "Use checklist visual dos 5 elementos como rascunho "
        "obrigatório antes do parágrafo final. Aluno preenche os "
        "5 campos antes de escrever a proposta corrida."
    ),
}

_FALLBACK = (
    "Identifique o padrão específico do erro do aluno e exercite "
    "casos similares. Use a evidência citada como ponto de partida."
)


def get_sugestao_pedagogica(descritor_id: str) -> str:
    """Retorna sugestão pedagógica pro descritor.

    Args:
        descritor_id: ID no formato `C{n}.{nnn}` (ex: "C5.001").

    Returns:
        Sugestão acionável (1-2 frases). Fallback genérico se ID
        não estiver mapeado — não levanta. Loga warning pra debug
        se descritor novo entrar no YAML sem entrada aqui.
    """
    if not isinstance(descritor_id, str):
        return _FALLBACK
    sug = _SUGESTOES.get(descritor_id)
    if sug is None:
        logger.warning(
            "sugestao_pedagogica: descritor %r sem entrada no dicionário "
            "— usando fallback. Adicione em sugestoes_pedagogicas.py.",
            descritor_id,
        )
        return _FALLBACK
    return sug


def get_definicao_curta(descritor_id: str, definicao_completa: str) -> str:
    """Extrai 1-2 frases iniciais da definição do YAML pro card.

    Trunca em ponto-final mais próximo de ~150 chars pra caber em UI
    sem rolagem. Se não houver ponto antes do limite, corta por
    palavras + reticências.
    """
    if not isinstance(definicao_completa, str):
        return ""
    txt = definicao_completa.strip().replace("\n", " ")
    while "  " in txt:
        txt = txt.replace("  ", " ")
    if len(txt) <= 150:
        return txt
    # Tenta cortar no primeiro ponto-final >= 100 chars
    for limite in (140, 150, 180):
        ponto = txt.rfind(".", 0, limite)
        if ponto >= 100:
            return txt[: ponto + 1]
    # Fallback: corta por palavras
    return txt[:147].rsplit(" ", 1)[0] + "…"
