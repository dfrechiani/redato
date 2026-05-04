"""Gerador de narrativa + ações pro Dashboard de turma (proposta D, 2026-05-04).

Recebe agregado de diagnóstico cognitivo da turma (output de
`agregacao.agregar_diagnosticos_turma`) e produz:

- 1 frase narrativa principal ("dos N alunos, M têm dificuldade em X…")
- Cards de ação organizados em 3 categorias:
  * Trabalhar agora (urgência alta) — top 1-2 lacunas críticas (≥50%)
  * Esta semana (urgência média) — lacunas 30-49%
  * Este mês (urgência baixa) — competências inteiras em alerta

Decisões de design (Daniel, fix UX Fase 4):
- TEMPLATE ESTÁTICO (sem LLM, custo zero, instantâneo). LLM dinâmico
  fica pra Fase 6 — ROI duvidoso enquanto não validamos com cursinhos.
- 3 categorias temporais ajudam o professor a planejar — "agora"
  vai pra próxima aula, "semana" pra próxima atividade, "mês" pra
  ciclo longo.
- Cards de "agora" trazem oficina sugerida com botão acionável; os
  outros são mais consultivos (sem CTA forte).

Estado degenerado:
- Cobertura < 30% (poucos alunos diagnosticados): só narrativa
  pedindo mais envios, sem ações.
- 0 alunos diagnosticados: mensagem de espera.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Constantes
# ──────────────────────────────────────────────────────────────────────

# Thresholds (em %, sobre alunos diagnosticados)
THRESHOLD_AGORA = 50.0
"""Lacuna ≥50% alunos com lacuna → vira card 'Trabalhar agora'."""

THRESHOLD_SEMANA_MIN = 30.0
THRESHOLD_SEMANA_MAX = 49.99
"""Lacuna 30-50% alunos → vira card 'Esta semana'."""

THRESHOLD_MES_DESCRITORES_ALERTA = 2
"""Competência com >= N descritores em alerta (≥50% lacuna) →
vira card 'Este mês' (acompanhar evolução da competência inteira)."""

THRESHOLD_COBERTURA_AVISO = 30.0
"""% alunos diagnosticados abaixo do qual NÃO geramos ações
(diagnóstico em formação)."""

MAX_ACOES_AGORA = 2
"""Briefing pediu 1-2 itens em 'agora'."""

MAX_ACOES_SEMANA = 3
"""Briefing pediu 2-3 itens em 'semana'."""

MAX_ACOES_MES = 2
"""Briefing pediu 1-2 itens em 'mês'."""


_NOMES_COMPETENCIA: Dict[str, str] = {
    "C1": "norma culta",
    "C2": "compreensão do tema e repertório",
    "C3": "argumentação",
    "C4": "coesão textual",
    "C5": "proposta de intervenção",
}


# ──────────────────────────────────────────────────────────────────────
# Tipos
# ──────────────────────────────────────────────────────────────────────

@dataclass
class CardAcao:
    """Card de ação com 3 níveis de urgência (alta/media/baixa).

    `oficina_sugerida` populado SÓ pra urgência=alta (cards mais
    acionáveis). Frontend renderiza botão "Criar atividade" lá.
    """
    titulo: str
    descricao: str
    urgencia: str                # "alta" | "media" | "baixa"
    lacunas_atendidas: List[str]
    oficina_sugerida: Optional[Dict[str, str]] = None
    """Sugestão de oficina (codigo, titulo, modo_correcao). None
    quando urgencia != 'alta'."""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "titulo": self.titulo,
            "descricao": self.descricao,
            "urgencia": self.urgencia,
            "lacunas_atendidas": list(self.lacunas_atendidas),
            "oficina_sugerida": (
                dict(self.oficina_sugerida) if self.oficina_sugerida else None
            ),
        }


@dataclass
class NarrativaTurma:
    """Pacote completo: 1 frase principal + 3 listas de cards."""
    narrativa_principal: str
    acoes_agora: List[CardAcao] = field(default_factory=list)
    acoes_semana: List[CardAcao] = field(default_factory=list)
    acoes_mes: List[CardAcao] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "narrativa_principal": self.narrativa_principal,
            "acoes_agora": [c.to_dict() for c in self.acoes_agora],
            "acoes_semana": [c.to_dict() for c in self.acoes_semana],
            "acoes_mes": [c.to_dict() for c in self.acoes_mes],
        }


# ──────────────────────────────────────────────────────────────────────
# Helpers internos
# ──────────────────────────────────────────────────────────────────────

def _percent(num: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((num / total) * 100, 1)


def _qtd_alunos_em_competencia(
    agregado_por_descritor: List[Dict[str, Any]],
    competencia: str,
    n_total: int,
) -> int:
    """Estima quantos alunos têm dificuldade na competência inteira.

    Heurística: pega o MAIOR `alunos_com_lacuna` entre os 8 descritores
    da competência (não soma — mesmo aluno aparece em vários
    descritores, somar inflaria).
    """
    qtds = [
        d.get("alunos_com_lacuna", 0)
        for d in agregado_por_descritor
        if d.get("competencia") == competencia
    ]
    return max(qtds, default=0)


def _primeira_oficina(
    oficinas_sugeridas: List[Dict[str, Any]],
) -> Optional[Dict[str, str]]:
    """Pega a primeira oficina sugerida (já vem ranqueada do
    `agregacao.calcular_top_lacunas` — foco específico antes de
    completo). Devolve dict slim pro card."""
    if not oficinas_sugeridas:
        return None
    o = oficinas_sugeridas[0]
    if not isinstance(o, dict):
        return None
    return {
        "codigo": str(o.get("codigo", "")),
        "titulo": str(o.get("titulo", "")),
        "modo_correcao": str(o.get("modo_correcao", "")),
    }


# ──────────────────────────────────────────────────────────────────────
# Narrativa principal
# ──────────────────────────────────────────────────────────────────────

def _narrativa_cobertura_zero(turma_codigo: str) -> str:
    return (
        f"Aguardando primeira redação corrigida da turma "
        f"{turma_codigo}. Quando alunos enviarem suas redações, "
        f"o diagnóstico coletivo aparece aqui."
    )


def _narrativa_cobertura_baixa(
    turma_codigo: str, n_diag: int, n_total: int,
) -> str:
    return (
        f"Diagnóstico em formação. Apenas {n_diag} de {n_total} "
        f"alunos da turma {turma_codigo} enviaram redação. "
        f"Recomendamos estimular mais alunos a enviar antes de "
        f"tomar decisões pedagógicas."
    )


def _formatar_pct(pct: float) -> str:
    """Formata 78.0 como '78%' e 78.5 como '78.5%' — evita decimais
    desnecessários quando o valor é inteiro."""
    if abs(pct - round(pct)) < 0.05:
        return f"{int(round(pct))}%"
    return f"{pct}%"


def _narrativa_cobertura_normal(
    turma_codigo: str,
    n_diag: int,
    top_lacuna: Dict[str, Any],
    qtd_competencia: int,
    definicao_curta: str,
) -> str:
    """Template principal: 2 frases curtas, sem tentar costurar o
    indicador_lacuna do YAML (que tem shapes irregulares).

    A definicao_curta entra como esclarecimento entre travessões —
    contrato pedagógico claro pro professor entender o que é a
    lacuna sem precisar abrir o accordion do heatmap.

    Exemplo:
        "Dos 18 alunos da turma 1A, 14 têm dificuldade em proposta
         de intervenção. A lacuna mais comum é em 'Agente' (78% dos
         diagnosticados) — a proposta precisa nomear QUEM vai executar
         (instituição, ministério, ONG)."
    """
    comp = top_lacuna.get("competencia", "")
    nome_comp = _NOMES_COMPETENCIA.get(comp, comp)
    nome_lacuna = (top_lacuna.get("nome") or "").strip()
    pct_str = _formatar_pct(top_lacuna.get("percent_lacuna", 0))

    frase1 = (
        f"Dos {n_diag} alunos da turma {turma_codigo}, "
        f"{qtd_competencia} têm dificuldade em {nome_comp}."
    )

    if definicao_curta:
        # Limpa pontuação final pra encaixar com travessão
        defc = definicao_curta.rstrip(" .;,")
        frase2 = (
            f"A lacuna mais comum é em '{nome_lacuna}' "
            f"({pct_str} dos diagnosticados) — {defc.lower() if defc and defc[0].isupper() else defc}."
        )
    else:
        frase2 = (
            f"A lacuna mais comum é em '{nome_lacuna}' "
            f"({pct_str} dos diagnosticados)."
        )

    return frase1 + " " + frase2


# ──────────────────────────────────────────────────────────────────────
# Cards de ação
# ──────────────────────────────────────────────────────────────────────

def _card_agora(top_lacuna: Dict[str, Any]) -> CardAcao:
    """Card com urgência alta — descritor com ≥50% alunos em lacuna.
    Inclui oficina sugerida pra ativar imediatamente.
    """
    nome = (top_lacuna.get("nome") or "").strip()
    qtd = top_lacuna.get("qtd_alunos", 0)
    sug = top_lacuna.get("sugestao_pedagogica", "").strip()
    oficina = _primeira_oficina(top_lacuna.get("oficinas_sugeridas") or [])

    titulo = f"Mini-aula sobre {nome.lower()}"
    if oficina and oficina.get("codigo"):
        descricao = (
            f"{qtd} alunos precisam dominar esse ponto. "
            f"Use {oficina['codigo']} ({oficina['titulo']}) como base. "
            f"{sug}".strip()
        )
    else:
        # Sem oficina catalogada (caso 3S OF02/08 ausentes ou
        # competência sem missão na série) — só sugestão pedagógica
        descricao = f"{qtd} alunos precisam dominar esse ponto. {sug}"

    return CardAcao(
        titulo=titulo,
        descricao=descricao,
        urgencia="alta",
        lacunas_atendidas=[top_lacuna.get("id", "")],
        oficina_sugerida=oficina,
    )


def _card_semana(lacuna_descritor: Dict[str, Any]) -> CardAcao:
    """Card com urgência média — descritor com 30-50% alunos em lacuna.
    SEM botão de oficina (mais consultivo). Foco na descrição
    pedagógica do que revisar.
    """
    nome = (lacuna_descritor.get("nome") or "").strip()
    pct = lacuna_descritor.get("percent_lacuna", 0)
    qtd = lacuna_descritor.get("alunos_com_lacuna", 0)
    sug = lacuna_descritor.get("sugestao_pedagogica", "").strip()

    titulo = f"Revisar {nome.lower()}"
    descricao = f"{qtd} alunos ({pct}%) com lacuna. {sug}"

    return CardAcao(
        titulo=titulo,
        descricao=descricao,
        urgencia="media",
        lacunas_atendidas=[lacuna_descritor.get("id", "")],
        oficina_sugerida=None,
    )


def _card_mes(
    competencia: str,
    n_descritores_em_alerta: int,
    n_total_competencia: int,
) -> CardAcao:
    """Card com urgência baixa — competência inteira em alerta
    (>= N descritores em vermelho).

    Não traz CTA de oficina — competência inteira é menos acionável
    que descritor único, melhor monitorar.
    """
    nome_comp = _NOMES_COMPETENCIA.get(competencia, competencia)
    titulo = f"Acompanhar evolução em {nome_comp} ({competencia})"
    descricao = (
        f"{n_descritores_em_alerta} dos {n_total_competencia} "
        f"descritores em alerta. Reavaliar após 2-3 redações."
    )
    return CardAcao(
        titulo=titulo,
        descricao=descricao,
        urgencia="baixa",
        lacunas_atendidas=[],
        oficina_sugerida=None,
    )


# ──────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────

def gerar_narrativa_turma(
    agregado: Dict[str, Any],
    *,
    descritores_por_id_lookup: Optional[Dict[str, Any]] = None,
) -> NarrativaTurma:
    """Recebe agregado de diagnóstico (output de
    `agregar_diagnosticos_turma`) e devolve narrativa + ações
    organizadas em 3 categorias temporais.

    Args:
        agregado: dict com chaves `turma`, `agregado_por_descritor`,
            `agregado_por_competencia`, `top_lacunas`.
        descritores_por_id_lookup: lookup id→Descritor pra puxar
            `indicador_lacuna` do YAML. Se None, carrega via Fase 1.

    Returns:
        NarrativaTurma. SEMPRE retorna estrutura válida — campos
        vazios em estados degenerados.
    """
    # Lazy import pra evitar ciclo
    if descritores_por_id_lookup is None:
        from redato_backend.diagnostico.descritores import descritores_por_id
        descritores_por_id_lookup = descritores_por_id()

    turma = agregado.get("turma", {}) or {}
    n_total = int(turma.get("total_alunos", 0))
    n_diag = int(turma.get("alunos_com_diagnostico", 0))
    codigo = str(turma.get("codigo", "?"))

    # Estado vazio: 0 alunos diagnosticados
    if n_diag == 0:
        return NarrativaTurma(
            narrativa_principal=_narrativa_cobertura_zero(codigo),
        )

    # Estado degenerado: cobertura < 30% (poucos alunos)
    cobertura_pct = _percent(n_diag, n_total)
    if cobertura_pct < THRESHOLD_COBERTURA_AVISO:
        return NarrativaTurma(
            narrativa_principal=_narrativa_cobertura_baixa(
                codigo, n_diag, n_total,
            ),
        )

    top_lacunas = agregado.get("top_lacunas", []) or []
    agregado_descritor = agregado.get("agregado_por_descritor", []) or []
    agregado_comp = agregado.get("agregado_por_competencia", []) or []

    # ── Narrativa principal ──────────────────────────────────────
    if not top_lacunas:
        # Tem alunos diagnosticados mas nenhum descritor crítico
        # (turma boa! ou ruído distribuído sem concentração)
        narrativa = (
            f"Dos {n_diag} alunos da turma {codigo} diagnosticados, "
            f"nenhum descritor isolado tem ≥30% de lacuna — turma "
            f"está distribuída sem concentração crítica. Continue "
            f"acompanhando perfis individuais."
        )
        # Sem cards de "agora" / "semana" mas pode ter "mês"
        # se houver competência em alerta
        return _construir_pacote_acoes(
            narrativa_principal=narrativa,
            top_lacunas=top_lacunas,
            agregado_por_descritor=agregado_descritor,
            agregado_por_competencia=agregado_comp,
        )

    # Top lacuna existe — usa pra narrativa principal.
    # Usa `definicao_curta` (já pré-resolvida no agregado) como
    # complemento — tem shape consistente (1-2 frases) ao contrário
    # do `indicador_lacuna` que é fragmento.
    top1 = top_lacunas[0]
    comp_top = top1.get("competencia", "")
    definicao_curta = top1.get("definicao_curta", "") or ""
    qtd_competencia = _qtd_alunos_em_competencia(
        agregado_descritor, comp_top, n_diag,
    )

    narrativa = _narrativa_cobertura_normal(
        turma_codigo=codigo,
        n_diag=n_diag,
        top_lacuna=top1,
        qtd_competencia=qtd_competencia,
        definicao_curta=definicao_curta,
    )

    return _construir_pacote_acoes(
        narrativa_principal=narrativa,
        top_lacunas=top_lacunas,
        agregado_por_descritor=agregado_descritor,
        agregado_por_competencia=agregado_comp,
    )


def _construir_pacote_acoes(
    *,
    narrativa_principal: str,
    top_lacunas: List[Dict[str, Any]],
    agregado_por_descritor: List[Dict[str, Any]],
    agregado_por_competencia: List[Dict[str, Any]],
) -> NarrativaTurma:
    """Monta as 3 listas de cards a partir dos thresholds."""

    # ── Trabalhar agora: top 1-2 lacunas ≥50% ────────────────────
    acoes_agora: List[CardAcao] = []
    lacunas_em_agora: set = set()
    for lac in top_lacunas:
        pct = lac.get("percent_lacuna", 0)
        if pct >= THRESHOLD_AGORA:
            acoes_agora.append(_card_agora(lac))
            lacunas_em_agora.add(lac.get("id"))
            if len(acoes_agora) >= MAX_ACOES_AGORA:
                break

    # ── Esta semana: descritores com 30-49% lacuna ───────────────
    # Iteramos `agregado_por_descritor` (40 entries) — mais
    # abrangente que `top_lacunas` (max 10). Filtra zona 30-49%.
    acoes_semana: List[CardAcao] = []
    candidatos_semana = sorted(
        [
            d for d in agregado_por_descritor
            if THRESHOLD_SEMANA_MIN <= d.get("percent_lacuna", 0)
            <= THRESHOLD_SEMANA_MAX
            and d.get("id") not in lacunas_em_agora
        ],
        key=lambda d: -d.get("percent_lacuna", 0),
    )
    for d in candidatos_semana[:MAX_ACOES_SEMANA]:
        acoes_semana.append(_card_semana(d))

    # ── Este mês: competências em alerta ─────────────────────────
    # Competência com ≥2 descritores em "vermelho" (≥50% lacuna)
    acoes_mes: List[CardAcao] = []
    for c in agregado_por_competencia:
        em_alerta = c.get("descritores_em_alerta", []) or []
        if len(em_alerta) >= THRESHOLD_MES_DESCRITORES_ALERTA:
            acoes_mes.append(_card_mes(
                competencia=c.get("competencia", ""),
                n_descritores_em_alerta=len(em_alerta),
                n_total_competencia=8,  # YAML tem 8 por competência
            ))
            if len(acoes_mes) >= MAX_ACOES_MES:
                break

    return NarrativaTurma(
        narrativa_principal=narrativa_principal,
        acoes_agora=acoes_agora,
        acoes_semana=acoes_semana,
        acoes_mes=acoes_mes,
    )
