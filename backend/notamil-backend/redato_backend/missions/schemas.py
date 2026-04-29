"""Schemas tool_use para os modos REJ 1S + 2S.

Spec: docs/redato/v3/redato_1S_criterios.md (1S),
docs/redato/v3/proposta_flags_foco_c1_c2.md (foco_c2 — 2026-04-28).

- foco_c2 (RJ2·OF04·MF, RJ2·OF06·MF): rubrica REJ 3 critérios → C2 ENEM
  0-200. C2 PURO (compreensão da proposta + tipo textual + repertório).
- foco_c3 (OF10): rubrica REJ 4 critérios → C3 ENEM 0-200.
- foco_c4 (OF11): rubrica REJ 4 critérios → C4 ENEM 0-200.
- foco_c5 (OF12): rubrica REJ 6 critérios → C5 ENEM 0-200.
- completo_parcial (OF13): C1+C2+C3+C4 (0-800), C5 = "não_aplicável".

Modo completo_integral (OF14) reutiliza o tool _SUBMIT_CORRECTION_FLAT_TOOL
existente — não está aqui. Modo foco_c1 ADIADO (decisão Daniel
2026-04-28) — sem missão atribuída atualmente.
"""
from __future__ import annotations
from typing import Any, Dict, List


# Escala granular 0-100 por critério (FIX 2 — reduz oscilação em casos
# fronteiriços). Bandas semânticas:
#   0-30  / 31-50  → insuficiente
#   51-70 / 71-85  → adequado
#   86-100         → excelente
def _score_0_100() -> Dict[str, Any]:
    return {
        "type": "integer",
        "minimum": 0,
        "maximum": 100,
        "description": (
            "Score 0-100. Bandas: 0-50 insuficiente, 51-79 adequado, "
            "80-100 excelente. Use o continuum dentro da banda."
        ),
    }


def _confidence_0_100() -> Dict[str, Any]:
    return {
        "type": "integer",
        "minimum": 0,
        "maximum": 100,
        "description": (
            "Quão confiante você está deste score (0-100). Valores baixos "
            "(<60) sinalizam zona de fronteira — caso ambíguo entre bandas."
        ),
    }


_NIVEL_REJ_4 = [0, 1, 2, 3]  # rubrica REJ 0-3 por critério (OF13)
_NOTA_ENEM = [0, 40, 80, 120, 160, 200]


def _feedback_aluno_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "acertos": {
                "type": "array",
                "items": {"type": "string"},
                "description": "1-3 frases curtas em vocabulário REJ ('tópico frasal', "
                               "'argumento', 'repertório', 'coesão') reconhecendo o que "
                               "o aluno fez bem.",
            },
            "ajustes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "1-3 ações concretas e acionáveis para o próximo "
                               "exercício, em vocabulário REJ.",
            },
        },
        "required": ["acertos", "ajustes"],
    }


def _feedback_professor_schema(audit_target: str = "100-200 palavras") -> Dict[str, Any]:
    """Estrutura do `feedback_professor` (M9.4, 2026-04-29).

    Decisão Daniel: substitui o monólito `audit_completo` por 4 campos
    discretos, pra UI renderizar com seções visuais (pontos fortes,
    pontos fracos, padrão de falha, transferência). Reduz parede de
    texto na tela do aluno.

    `audit_target` (parâmetro mantido pra retrocompat de chamadas
    existentes em `FOCO_C{3,4,5}_TOOL` e `COMPLETO_PARCIAL_TOOL`)
    agora se aplica ao **somatório** dos 4 campos — não mais a um
    único campo. Helper `_audit_pedagogico_de` no portal lê tanto o
    formato novo quanto o legado `audit_completo`.
    """
    return {
        "type": "object",
        "properties": {
            "pontos_fortes": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 3,
                "description": (
                    "1-3 itens curtos (1-2 frases cada) sobre o que o "
                    "aluno fez bem. Em terminologia INEP/oficina pro "
                    "professor (não o vocabulário simplificado do "
                    "feedback_aluno). Ex.: 'Tópico frasal assertivo "
                    "com recorte temático preservado.'"
                ),
            },
            "pontos_fracos": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 3,
                "description": (
                    "1-3 itens curtos (1-2 frases cada) sobre o que "
                    "compromete a nota. Específico, não genérico. "
                    "Ex.: 'Repertório legitimado mas desarticulado do "
                    "argumento — Bauman colado sem aprofundamento.'"
                ),
            },
            "padrao_falha": {
                "type": "string",
                "description": (
                    "1 frase nomeando o padrão pedagógico dominante. "
                    "Em terminologia INEP/oficina. Ex.: 'tese "
                    "genérica', 'salto lógico', 'proposta "
                    "desarticulada', 'repertório de bolso'."
                ),
            },
            "transferencia_competencia": {
                "type": "string",
                "description": (
                    "1-2 frases apontando como esse padrão se "
                    "manifesta em outras competências do ENEM e o "
                    "que o aluno deve treinar pra evitar reincidência."
                ),
            },
        },
        "required": [
            "pontos_fortes",
            "pontos_fracos",
            "padrao_falha",
            "transferencia_competencia",
        ],
    }


# ──────────────────────────────────────────────────────────────────────
# Modo Foco C2 (RJ2·OF04·MF, RJ2·OF06·MF) — 2S, M9.1
# ──────────────────────────────────────────────────────────────────────
# Decisão pedagógica (Daniel, 2026-04-28): C2 PURO. Cobre apenas
# (a) compreensão da proposta — não fugiu/tangenciou; (b) tipo textual
# dissertativo-argumentativo; (c) repertório articulado. NÃO inclui
# aspectos de C3 (autoria, projeto de texto, profundidade argumentativa).
# Spec completo: docs/redato/v3/proposta_flags_foco_c1_c2.md.

FOCO_C2_TOOL: Dict[str, Any] = {
    "name": "submit_foco_c2",
    "description": (
        "Avaliação Modo Foco C2 (compreensão da proposta + tipo textual "
        "+ repertório). Aluno escreveu introdução dissertativa OU "
        "parágrafo com citação articulada (~80-150 palavras). Avalie "
        "APENAS C2 — não rebaixe por problemas de C3 (autoria, projeto "
        "de texto, profundidade argumentativa). Caps semânticos: "
        "fuga ao tema → 0 (anula); tipo textual inadequado → 0 (anula); "
        "tangenciamento → ≤ 80; repertório de bolso → ≤ 120."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "modo": {"type": "string", "enum": ["foco_c2"]},
            # 2 missões 2S usam foco_c2 (Fontes e Citações; Da Notícia
            # ao Artigo). Nomes canonizados pelo router via
            # _canonicalize (middle dots → underscore).
            "missao_id": {
                "type": "string",
                "enum": ["RJ2_OF04_MF", "RJ2_OF06_MF"],
            },
            "rubrica_rej": {
                "type": "object",
                "properties": {
                    "compreensao_tema": _score_0_100(),
                    "tipo_textual": _score_0_100(),
                    "repertorio": _score_0_100(),
                },
                "required": [
                    "compreensao_tema", "tipo_textual", "repertorio",
                ],
            },
            "confidences": {
                "type": "object",
                "description": "Opcional. Confiança 0-100 por critério.",
                "properties": {
                    "compreensao_tema": _confidence_0_100(),
                    "tipo_textual": _confidence_0_100(),
                    "repertorio": _confidence_0_100(),
                },
            },
            "nota_rej_total": {
                "type": "integer",
                "minimum": 0,
                "maximum": 300,
                "description": (
                    "Soma dos 3 critérios (cada 0-100). Range 0-300."
                ),
            },
            "nota_c2_enem": {
                "type": "integer",
                "enum": _NOTA_ENEM,
                "description": (
                    "C2 ENEM 0-200. Caps obrigatórios (Python aplica em "
                    "scoring.py via defesa em profundidade — você pode "
                    "emitir ou não, mas Python faz min): "
                    "fuga_tema=true → 0; "
                    "tipo_textual_inadequado=true → 0; "
                    "tangenciamento_tema=true → ≤ 80; "
                    "repertorio_de_bolso=true → ≤ 120."
                ),
            },
            "flags": {
                "type": "object",
                "properties": {
                    "tangenciamento_tema": {
                        "type": "boolean",
                        "description": (
                            "true se aborda assunto amplo do tema mas "
                            "não o recorte específico definido na "
                            "proposta. Cap C2 ≤ 80 quando true."
                        ),
                    },
                    "fuga_tema": {
                        "type": "boolean",
                        "description": (
                            "true se não aborda nem o assunto amplo nem "
                            "o recorte específico — anula a redação "
                            "(C2 = 0; rubrica oficial). Mutuamente "
                            "exclusiva com tangenciamento_tema."
                        ),
                    },
                    "tipo_textual_inadequado": {
                        "type": "boolean",
                        "description": (
                            "true se predominam marcas de narrativo, "
                            "descritivo ou expositivo puro em vez de "
                            "dissertativo-argumentativo. Anula a redação "
                            "(C2 = 0). Mutuamente exclusiva com "
                            "tangenciamento e fuga."
                        ),
                    },
                    "repertorio_de_bolso": {
                        "type": "boolean",
                        "description": (
                            "true se referência citada é genérica/"
                            "decorada, aplicável a qualquer tema, sem "
                            "articulação específica ao recorte (ex.: "
                            "Utopia de More, alegoria da caverna, "
                            "instituições zumbis de Bauman sem "
                            "aprofundamento). Cap C2 ≤ 120 quando true. "
                            "Compartilhada com modo completo_parcial."
                        ),
                    },
                    "copia_motivadores_recorrente": {
                        "type": "boolean",
                        "description": (
                            "true se ≥ 2 sentenças completas são "
                            "reproduzidas literalmente dos textos "
                            "motivadores sem marcação de citação, "
                            "indicando ausência de produção autoral. "
                            "NOTA: detecção efetiva depende de pipeline "
                            "de motivadores no contexto, ainda não "
                            "implementado — emita apenas em casos "
                            "óbvios (aluno menciona 'conforme o texto "
                            "motivador' sem produção autoral)."
                        ),
                    },
                },
                "required": [
                    "tangenciamento_tema",
                    "fuga_tema",
                    "tipo_textual_inadequado",
                    "repertorio_de_bolso",
                    "copia_motivadores_recorrente",
                ],
            },
            "feedback_aluno": _feedback_aluno_schema(),
            "feedback_professor": _feedback_professor_schema(
                "100-180 palavras"
            ),
        },
        "required": [
            "modo",
            "missao_id",
            "rubrica_rej",
            "nota_rej_total",
            "nota_c2_enem",
            "flags",
            "feedback_aluno",
            "feedback_professor",
        ],
    },
}


# ──────────────────────────────────────────────────────────────────────
# Modo Foco C3 (OF10)
# ──────────────────────────────────────────────────────────────────────

FOCO_C3_TOOL: Dict[str, Any] = {
    "name": "submit_foco_c3",
    "description": (
        "Avaliação Modo Foco C3 (OF10). Aluno escreveu UM parágrafo com "
        "Conclusão + Premissa + Exemplo. Avalie cada critério da rubrica "
        "REJ em score 0-100 (continuum granular dentro das bandas "
        "insuficiente/adequado/excelente), traduza para C3 ENEM 0-200, e "
        "produza feedback aluno + professor."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "modo": {"type": "string", "enum": ["foco_c3"]},
            "missao_id": {"type": "string", "enum": ["RJ1_OF10_MF"]},
            "rubrica_rej": {
                "type": "object",
                "properties": {
                    "conclusao": _score_0_100(),
                    "premissa": _score_0_100(),
                    "exemplo": _score_0_100(),
                    "fluencia": _score_0_100(),
                },
                "required": ["conclusao", "premissa", "exemplo", "fluencia"],
            },
            "confidences": {
                "type": "object",
                "description": "Opcional. Confiança 0-100 por critério; "
                               "valores baixos sinalizam zona de fronteira.",
                "properties": {
                    "conclusao": _confidence_0_100(),
                    "premissa": _confidence_0_100(),
                    "exemplo": _confidence_0_100(),
                    "fluencia": _confidence_0_100(),
                },
            },
            "nota_rej_total": {
                "type": "integer",
                "minimum": 0,
                "maximum": 400,
                "description": "Soma dos 4 critérios (cada 0-100). Range 0-400.",
            },
            "nota_c3_enem": {
                "type": "integer",
                "enum": _NOTA_ENEM,
                "description": "C3 ENEM 0-200 derivada qualitativamente da rubrica REJ "
                               "+ Cartilha INEP, usando a tabela de tradução da spec.",
            },
            "flags": {
                "type": "object",
                "properties": {
                    "andaime_copiado": {
                        "type": "boolean",
                        "description": "true se as palavras 'Conclusão:', 'Premissa:' "
                                       "ou 'Exemplo:' aparecem no texto reescrito, "
                                       "sinalizando falta de fluência argumentativa.",
                    },
                    "tese_generica": {
                        "type": "boolean",
                        "description": "true se a conclusão é frase clichê genérica "
                                       "aplicável a qualquer tema.",
                    },
                    "exemplo_redundante": {
                        "type": "boolean",
                        "description": "true se o exemplo apenas paráfraseia a premissa "
                                       "sem adicionar caso concreto.",
                    },
                },
                "required": ["andaime_copiado", "tese_generica", "exemplo_redundante"],
            },
            "feedback_aluno": _feedback_aluno_schema(),
            "feedback_professor": _feedback_professor_schema("100-200 palavras"),
        },
        "required": [
            "modo",
            "missao_id",
            "rubrica_rej",
            "nota_rej_total",
            "nota_c3_enem",
            "flags",
            "feedback_aluno",
            "feedback_professor",
        ],
    },
}


# ──────────────────────────────────────────────────────────────────────
# Modo Foco C4 (OF11)
# ──────────────────────────────────────────────────────────────────────

FOCO_C4_TOOL: Dict[str, Any] = {
    "name": "submit_foco_c4",
    "description": (
        "Avaliação Modo Foco C4 (OF11). Aluno escreveu UM parágrafo "
        "argumentativo (entrevista de emprego) com 4 peças e conectivos. "
        "Avalie cada critério da rubrica REJ em score 0-100 (continuum), "
        "traduza para C4 ENEM 0-200. NÃO conte conectivos — avalie "
        "adequação semântica."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "modo": {"type": "string", "enum": ["foco_c4"]},
            "missao_id": {"type": "string", "enum": ["RJ1_OF11_MF"]},
            "rubrica_rej": {
                "type": "object",
                "properties": {
                    "estrutura": _score_0_100(),
                    "conectivos": _score_0_100(),
                    "cadeia_logica": _score_0_100(),
                    "palavra_dia": _score_0_100(),
                },
                "required": ["estrutura", "conectivos", "cadeia_logica", "palavra_dia"],
            },
            "confidences": {
                "type": "object",
                "description": "Opcional. Confiança 0-100 por critério.",
                "properties": {
                    "estrutura": _confidence_0_100(),
                    "conectivos": _confidence_0_100(),
                    "cadeia_logica": _confidence_0_100(),
                    "palavra_dia": _confidence_0_100(),
                },
            },
            "nota_rej_total": {"type": "integer", "minimum": 0, "maximum": 400},
            "nota_c4_enem": {"type": "integer", "enum": _NOTA_ENEM},
            "flags": {
                "type": "object",
                "properties": {
                    "conectivo_relacao_errada": {
                        "type": "boolean",
                        "description": "true se algum conectivo tem função lógica "
                                       "errada (ex.: 'portanto' introduzindo causa).",
                    },
                    "conectivo_repetido": {
                        "type": "boolean",
                        "description": "true se o mesmo conectivo aparece 3+ vezes.",
                    },
                    "salto_logico": {
                        "type": "boolean",
                        "description": "true se a cadeia tem elos faltantes entre "
                                       "premissa e conclusão.",
                    },
                    "palavra_dia_uso_errado": {
                        "type": "boolean",
                        "description": "true se 'premissa', 'mitigar' ou 'exacerbar' "
                                       "está usada com sentido inadequado.",
                    },
                },
                "required": [
                    "conectivo_relacao_errada",
                    "conectivo_repetido",
                    "salto_logico",
                    "palavra_dia_uso_errado",
                ],
            },
            "feedback_aluno": _feedback_aluno_schema(),
            "feedback_professor": _feedback_professor_schema("100-200 palavras"),
        },
        "required": [
            "modo",
            "missao_id",
            "rubrica_rej",
            "nota_rej_total",
            "nota_c4_enem",
            "flags",
            "feedback_aluno",
            "feedback_professor",
        ],
    },
}


# ──────────────────────────────────────────────────────────────────────
# Modo Foco C5 (OF12)
# ──────────────────────────────────────────────────────────────────────

FOCO_C5_TOOL: Dict[str, Any] = {
    "name": "submit_foco_c5",
    "description": (
        "Avaliação Modo Foco C5 (OF12). Aluno escreveu UMA proposta de "
        "intervenção. Avalie a rubrica REJ (6 critérios), aplique a regra "
        "PRIMÁRIA de articulação à discussão (não conte 5 elementos), "
        "traduza para C5 ENEM 0-200. Caps: desarticulada=80, "
        "vaga/constatatória=40, viola DH=0."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "modo": {"type": "string", "enum": ["foco_c5"]},
            "missao_id": {"type": "string", "enum": ["RJ1_OF12_MF"]},
            "rubrica_rej": {
                "type": "object",
                "properties": {
                    "agente": _score_0_100(),
                    "acao_verbo": _score_0_100(),
                    "meio": _score_0_100(),
                    "finalidade": _score_0_100(),
                    "detalhamento": _score_0_100(),
                    "direitos_humanos": _score_0_100(),
                },
                "required": [
                    "agente", "acao_verbo", "meio", "finalidade",
                    "detalhamento", "direitos_humanos",
                ],
            },
            "confidences": {
                "type": "object",
                "description": "Opcional. Confiança 0-100 por critério.",
                "properties": {
                    "agente": _confidence_0_100(),
                    "acao_verbo": _confidence_0_100(),
                    "meio": _confidence_0_100(),
                    "finalidade": _confidence_0_100(),
                    "detalhamento": _confidence_0_100(),
                    "direitos_humanos": _confidence_0_100(),
                },
            },
            "articulacao_a_discussao": {
                "type": "string",
                "enum": ["ausente", "fragil", "clara", "tematizada"],
                "description": "Critério PRIMÁRIO. 'ausente' ou 'fragil' aplicam "
                               "caps independentemente da rubrica REJ.",
            },
            "nota_rej_total": {"type": "integer", "minimum": 0, "maximum": 600},
            "nota_c5_enem": {"type": "integer", "enum": _NOTA_ENEM},
            "flags": {
                "type": "object",
                "properties": {
                    "proposta_vaga_constatatoria": {
                        "type": "boolean",
                        "description": "true se proposta limita-se a constatar "
                                       "problema sem indicar solução concreta. "
                                       "Aplica cap 40.",
                    },
                    "proposta_desarticulada": {
                        "type": "boolean",
                        "description": "true se a solução não responde aos problemas "
                                       "específicos discutidos. Aplica cap 80.",
                    },
                    "agente_generico": {
                        "type": "boolean",
                        "description": "true se 'o governo', 'a sociedade', 'as pessoas' "
                                       "sem especificação institucional.",
                    },
                    "verbo_fraco": {
                        "type": "boolean",
                        "description": "true se 'fazer', 'ter' ou 'ser' como verbo "
                                       "principal da ação.",
                    },
                    "desrespeito_direitos_humanos": {
                        "type": "boolean",
                        "description": "true se proposta viola direitos humanos. "
                                       "C5 vai a 0.",
                    },
                },
                "required": [
                    "proposta_vaga_constatatoria",
                    "proposta_desarticulada",
                    "agente_generico",
                    "verbo_fraco",
                    "desrespeito_direitos_humanos",
                ],
            },
            "feedback_aluno": _feedback_aluno_schema(),
            "feedback_professor": _feedback_professor_schema("100-200 palavras"),
        },
        "required": [
            "modo",
            "missao_id",
            "rubrica_rej",
            "articulacao_a_discussao",
            "nota_rej_total",
            "nota_c5_enem",
            "flags",
            "feedback_aluno",
            "feedback_professor",
        ],
    },
}


# ──────────────────────────────────────────────────────────────────────
# Modo Completo Parcial (OF13) — parágrafo único, C5 = não_aplicável
# ──────────────────────────────────────────────────────────────────────

COMPLETO_PARCIAL_TOOL: Dict[str, Any] = {
    "name": "submit_completo_parcial",
    "description": (
        "Avaliação Modo Completo Parcial (OF13). Aluno escreveu UM "
        "parágrafo argumentativo (6-9 linhas). Avalie a rubrica REJ "
        "(Tópico Frasal, Argumento, Repertório, Coesão — 0-3 cada) e "
        "produza notas C1+C2+C3+C4 ENEM (0-200 cada). C5 é 'não_aplicável' "
        "porque parágrafo único não tem proposta de intervenção. "
        "nota_total_parcial = soma de C1+C2+C3+C4 (0-800)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "modo": {"type": "string", "enum": ["completo_parcial"]},
            "missao_id": {"type": "string", "enum": ["RJ1_OF13_MF"]},
            "rubrica_rej": {
                "type": "object",
                "properties": {
                    "topico_frasal": _score_0_100(),
                    "argumento": _score_0_100(),
                    "repertorio": _score_0_100(),
                    "coesao": _score_0_100(),
                },
                "required": ["topico_frasal", "argumento", "repertorio", "coesao"],
            },
            "confidences": {
                "type": "object",
                "description": "Opcional. Confiança 0-100 por critério.",
                "properties": {
                    "topico_frasal": _confidence_0_100(),
                    "argumento": _confidence_0_100(),
                    "repertorio": _confidence_0_100(),
                    "coesao": _confidence_0_100(),
                },
            },
            "nota_rej_total": {"type": "integer", "minimum": 0, "maximum": 400},
            "notas_enem": {
                "type": "object",
                "properties": {
                    "c1": {"type": "integer", "enum": _NOTA_ENEM},
                    "c2": {"type": "integer", "enum": _NOTA_ENEM},
                    "c3": {"type": "integer", "enum": _NOTA_ENEM},
                    "c4": {"type": "integer", "enum": _NOTA_ENEM},
                    "c5": {"type": "string", "enum": ["não_aplicável"]},
                },
                "required": ["c1", "c2", "c3", "c4", "c5"],
            },
            "nota_total_parcial": {
                "type": "integer",
                "minimum": 0,
                "maximum": 800,
                "description": "Soma C1+C2+C3+C4. C5 não entra na soma.",
            },
            "flags": {
                "type": "object",
                "properties": {
                    "topico_e_pergunta": {
                        "type": "boolean",
                        "description": "true se o tópico frasal é interrogativo "
                                       "em vez de assertivo.",
                    },
                    "repertorio_de_bolso": {
                        "type": "boolean",
                        "description": "true se há repertório citado mas desarticulado "
                                       "do argumento (Aristóteles colado).",
                    },
                    "argumento_superficial": {
                        "type": "boolean",
                        "description": "true se argumento é frase solta sem mecanismo "
                                       "causal.",
                    },
                    "coesao_perfeita_sem_progressao": {
                        "type": "boolean",
                        "description": "true se conectivos OK mas parágrafo gira em "
                                       "torno da mesma ideia.",
                    },
                },
                "required": [
                    "topico_e_pergunta",
                    "repertorio_de_bolso",
                    "argumento_superficial",
                    "coesao_perfeita_sem_progressao",
                ],
            },
            "feedback_aluno": _feedback_aluno_schema(),
            "feedback_professor": _feedback_professor_schema("200-400 palavras"),
        },
        "required": [
            "modo",
            "missao_id",
            "rubrica_rej",
            "nota_rej_total",
            "notas_enem",
            "nota_total_parcial",
            "flags",
            "feedback_aluno",
            "feedback_professor",
        ],
    },
}


# ──────────────────────────────────────────────────────────────────────
# Modo Jogo Redação (RJ2·OF13·MF) — Fase 2 passo 5, 2026-04-29
# ──────────────────────────────────────────────────────────────────────
# Spec: docs/redato/v3/proposta_integracao_jogo_redato.md (seção C.5) +
# adendo G (decisões G.1.6, G.1.7).
#
# Aluno do 2S faz REESCRITA INDIVIDUAL a partir de uma redação
# cooperativa montada com cartas. O tool avalia a versão autoral (não a
# montada) com 5 competências ENEM completas (escala 0/40/80/120/160/200,
# total 0-1000) MAIS 2 saídas específicas do jogo:
#
# - `transformacao_cartas` (0-100, decisão G.1.6): score independente.
#   Mede quanto a reescrita superou o esqueleto cooperativo. NÃO compõe
#   a nota total ENEM. Aparece no dashboard como métrica complementar.
#
# - `sugestoes_cartas_alternativas` (0-2 itens, decisão G.1.7): pra
#   cartas escolhidas que ficaram fracas no contexto do tema, sugerir
#   UMA outra carta do mesmo minideck + motivo pedagógico curto.
#
# Flags barram regressões clássicas do jogo: cópia literal das cartas,
# cartas mal articuladas, fuga do tema, tipo textual inadequado, e
# desrespeito a DH (cap C1=0 padrão ENEM).

JOGO_REDACAO_TOOL: Dict[str, Any] = {
    "name": "submit_jogo_redacao",
    "description": (
        "Avaliação Modo Jogo Redação (RJ2·OF13·MF, 2S). Aluno fez "
        "reescrita individual de uma redação cooperativa montada com "
        "cartas (estruturais E## + temáticas P/R/K/A/AC/ME/F do "
        "minideck). Avalie A REESCRITA AUTORAL (não a montada) com 5 "
        "competências ENEM completas. Adicionalmente, produza score "
        "independente `transformacao_cartas` (0-100) medindo quanto "
        "a reescrita superou o esqueleto, e até 2 sugestões de cartas "
        "alternativas pra cartas que ficaram fracas no contexto."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "modo": {"type": "string", "enum": ["jogo_redacao"]},
            "tema_minideck": {
                "type": "string",
                "description": (
                    "Slug do minideck temático (ex.: 'saude_mental'). "
                    "Vem repetido aqui pra reforçar a coerência do "
                    "feedback com o tema escolhido pelo grupo."
                ),
            },
            "notas_enem": {
                "type": "object",
                "properties": {
                    "c1": {"type": "integer", "enum": _NOTA_ENEM,
                           "description": "Domínio da norma culta."},
                    "c2": {"type": "integer", "enum": _NOTA_ENEM,
                           "description": "Compreensão da proposta + tipo textual + repertório."},
                    "c3": {"type": "integer", "enum": _NOTA_ENEM,
                           "description": "Seleção/relação/organização/interpretação de informações."},
                    "c4": {"type": "integer", "enum": _NOTA_ENEM,
                           "description": "Conhecimento dos mecanismos linguísticos."},
                    "c5": {"type": "integer", "enum": _NOTA_ENEM,
                           "description": "Proposta de intervenção com agente, ação, meio, finalidade, detalhamento."},
                },
                "required": ["c1", "c2", "c3", "c4", "c5"],
            },
            "nota_total_enem": {
                "type": "integer",
                "minimum": 0,
                "maximum": 1000,
                "description": (
                    "Soma das 5 competências (0-1000). Override "
                    "determinístico em Python depois — emita o melhor "
                    "valor possível."
                ),
            },
            "transformacao_cartas": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": (
                    "Score independente (0-100, decisão G.1.6). "
                    "Quanto a reescrita superou o esqueleto cooperativo. "
                    "Bandas: "
                    "0-15 = cópia literal das cartas; "
                    "16-40 = só conectivos trocados, dependência alta "
                    "do esqueleto; "
                    "41-70 = paráfrases com algum recorte autoral, mas "
                    "ainda reconhecível como expansão das cartas; "
                    "71-90 = autoria substancial, cartas reaproveitadas "
                    "como ponto de partida; "
                    "91-100 = autoria plena, cartas claramente subordinadas "
                    "à voz do aluno. NÃO compõe a nota_total_enem."
                ),
            },
            "sugestoes_cartas_alternativas": {
                "type": "array",
                "minItems": 0,
                "maxItems": 2,
                "description": (
                    "0-2 sugestões (decisão G.1.7). Lista vazia é "
                    "feedback positivo legítimo (todas as cartas do "
                    "grupo funcionaram bem). Cada item: carta original "
                    "que ficou fraca + carta alternativa do mesmo "
                    "minideck + motivo pedagógico curto."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "codigo_original": {
                            "type": "string",
                            "description": (
                                "Código da carta escolhida pelo grupo "
                                "que ficou fraca (ex.: 'P03', 'K22'). "
                                "DEVE estar entre as cartas que o "
                                "grupo escolheu."
                            ),
                        },
                        "codigo_sugerido": {
                            "type": "string",
                            "description": (
                                "Código de carta alternativa (ex.: "
                                "'P05'). DEVE estar no minideck e "
                                "ser do mesmo TIPO da original "
                                "(P→P, R→R, etc.). DEVE ser diferente "
                                "da original."
                            ),
                        },
                        "motivo": {
                            "type": "string",
                            "description": (
                                "1-2 frases curtas em vocabulário REJ. "
                                "Por que a alternativa funciona "
                                "melhor no contexto. Ex.: 'P05 dá "
                                "mais especificidade ao recorte que "
                                "P03 deixou genérico'."
                            ),
                        },
                    },
                    "required": [
                        "codigo_original", "codigo_sugerido", "motivo",
                    ],
                },
            },
            "flags": {
                "type": "object",
                "properties": {
                    "copia_literal_das_cartas": {
                        "type": "boolean",
                        "description": (
                            "true se a reescrita reproduz literalmente "
                            "frases da redação cooperativa montada — "
                            "sem reformulação. Trigger pra "
                            "transformacao_cartas <= 15."
                        ),
                    },
                    "cartas_mal_articuladas": {
                        "type": "boolean",
                        "description": (
                            "true se cartas escolhidas aparecem coladas "
                            "à força, sem ligação argumentativa "
                            "(repertório de bolso, agente solto). "
                            "Compromete C3."
                        ),
                    },
                    "fuga_do_tema_do_minideck": {
                        "type": "boolean",
                        "description": (
                            "true se reescrita perde o tema do "
                            "minideck escolhido pelo grupo (ex.: "
                            "minideck 'Saúde Mental' mas reescrita "
                            "discute educação digital). Cap C2 em 80."
                        ),
                    },
                    "tipo_textual_inadequado": {
                        "type": "boolean",
                        "description": (
                            "true se reescrita não é dissertativo-"
                            "argumentativa (vira narração, descrição, "
                            "carta). Cap C2 em 80 (padrão ENEM)."
                        ),
                    },
                    "desrespeito_direitos_humanos": {
                        "type": "boolean",
                        "description": (
                            "true se a reescrita propõe ou defende "
                            "violação de direitos humanos. Cap "
                            "C1=0 + C5=0 (padrão ENEM, cartilha INEP)."
                        ),
                    },
                },
                "required": [
                    "copia_literal_das_cartas",
                    "cartas_mal_articuladas",
                    "fuga_do_tema_do_minideck",
                    "tipo_textual_inadequado",
                    "desrespeito_direitos_humanos",
                ],
            },
            "feedback_aluno": _feedback_aluno_schema(),
            "feedback_professor": _feedback_professor_schema("200-400 palavras"),
        },
        "required": [
            "modo",
            "tema_minideck",
            "notas_enem",
            "nota_total_enem",
            "transformacao_cartas",
            "sugestoes_cartas_alternativas",
            "flags",
            "feedback_aluno",
            "feedback_professor",
        ],
    },
}


TOOLS_BY_MODE: Dict[str, Dict[str, Any]] = {
    # foco_c1 ADIADO (decisão Daniel 2026-04-28) — sem missão atual.
    # Quando ativar: implementar FOCO_C1_TOOL conforme proposta em
    # docs/redato/v3/proposta_flags_foco_c1_c2.md F.1, descomentar
    # linha abaixo, atualizar router/detectors paralelo.
    # "foco_c1": FOCO_C1_TOOL,
    "foco_c2": FOCO_C2_TOOL,            # NOVO (M9.1, 2S)
    "foco_c3": FOCO_C3_TOOL,
    "foco_c4": FOCO_C4_TOOL,
    "foco_c5": FOCO_C5_TOOL,
    "completo_parcial": COMPLETO_PARCIAL_TOOL,
    "jogo_redacao": JOGO_REDACAO_TOOL,  # Fase 2 passo 5 (2S, OF13 jogo)
}
