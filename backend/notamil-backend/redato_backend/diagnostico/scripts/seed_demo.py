"""Seed de demo: cria turma + aluno + atividade + envio com correção
e diagnóstico cognitivo POPULADOS — sem chamar OpenAI/Anthropic.

Uso (Railway shell do backend):
    python -m redato_backend.diagnostico.scripts.seed_demo

Output: imprime IDs criados + URLs prontas pra abrir no portal e
printar pra apresentação.

Idempotente — re-rodar atualiza dados existentes sem duplicar.

NÃO chama LLM externo. Todos os campos vêm hardcoded (texto de
redação, notas, feedback estruturado, evidências, detectores,
diagnóstico cognitivo dos 40 descritores). Schema M9.4+ completo,
incluindo `feedback_professor` estruturado pra o portal renderizar
a seção "Análise da redação" cheia.

Estado vazio em prod (antes desta seed):
- Sem turma "DEMO", sem aluno "Maria Aparecida"
- Sem envio com diagnóstico cognitivo populado

Estado depois:
- Turma "DEMO" + 1 aluno + 1 atividade ativa + 1 envio com tudo
- Foto: foto_path vazio (sem upload). Frontend mostra
  "foto não persistida" mas as outras seções renderizam cheias.
"""
from __future__ import annotations

import json
import logging
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Constantes do demo
# ──────────────────────────────────────────────────────────────────────

DEMO_ESCOLA_NOME = "Escola Demo Redato"
DEMO_PROFESSOR_NOME = "Prof Demo"
DEMO_PROFESSOR_EMAIL = "demo@redato.app"
DEMO_TURMA_CODIGO = "DEMO-1A"
DEMO_TURMA_CODIGO_JOIN = "DEMO-1A-2026"
DEMO_ALUNO_NOME = "Maria Aparecida Silva"
DEMO_ALUNO_TELEFONE = "+5511999900000"  # placeholder, não é número real
DEMO_MISSAO_CODIGO = "RJ1·OF14·MF"  # OF14 = completo, 5 competências

DEMO_TEXTO_REDACAO = """\
O problema da saúde mental dos jovens brasileiros tornou-se central no século XXI. \
Como aponta Byung-Chul Han, em "Sociedade do Cansaço" (2010), vivemos uma época \
em que a autoexploração substituiu a coerção externa: o jovem se cobra incessantemente \
por produtividade, performance acadêmica e relevância nas redes sociais. Essa pressão \
constante, somada à precariedade dos serviços públicos de saúde mental, configura um \
cenário em que o adoecimento psíquico precoce é regra, não exceção.

Em primeiro lugar, é necessário reconhecer que o estigma associado aos transtornos \
mentais ainda silencia a juventude. Segundo dados do Ministério da Saúde (2023), \
o suicídio é a quarta principal causa de morte entre brasileiros de 15 a 29 anos, \
e a maioria dos casos não recebe acompanhamento profissional prévio. Quando o jovem \
fala "estou cansado", a resposta cultural costuma ser "todos estão" — e a busca por \
ajuda é adiada até o quadro virar emergência.

Ademais, a Rede de Atenção Psicossocial (RAPS), instituída pela Lei 10.216/2001, \
prevê os Centros de Atenção Psicossocial Infantojuvenis (CAPSi) como porta de \
entrada. No entanto, apenas 11% dos municípios brasileiros têm CAPSi funcionando, \
segundo o Conselho Federal de Psicologia. O resultado é que a maioria dos jovens \
sem plano de saúde simplesmente não tem acesso a tratamento — direito previsto \
em lei vira ficção operacional.

A sociedade brasileira precisa enfrentar esse problema com urgência. É fundamental \
que todos se conscientizem sobre a saúde mental dos jovens. Cabe aos governos, à \
sociedade e à mídia trabalhar juntos para garantir que os jovens tenham um futuro \
melhor, mais saudável e com mais oportunidades de bem-estar emocional.\
"""


# ──────────────────────────────────────────────────────────────────────
# Schema M9.4+ do redato_output (cN_audit + feedback_professor)
# ──────────────────────────────────────────────────────────────────────

DEMO_REDATO_OUTPUT: Dict[str, Any] = {
    "modo": "completo",
    "nota_total_enem": 720,
    "c1_audit": {
        "nota": 160,
        "feedback_text": (
            "Norma culta sólida. A construção sintática é variada, "
            "com períodos completos e bom uso de subordinação. "
            "Vocabulário preciso e adequado ao registro formal. "
            "Pequeno deslize em 'apenas 11% dos municípios brasileiros "
            "têm CAPSi' — concordância correta, mas a frase ganharia "
            "fluência com 'apenas 11% dos municípios brasileiros contam "
            "com CAPSi'. Sem desvios graves."
        ),
        "evidencias": [
            {
                "trecho": (
                    "Como aponta Byung-Chul Han, em \"Sociedade do "
                    "Cansaço\" (2010), vivemos uma época em que a "
                    "autoexploração substituiu a coerção externa"
                ),
                "comentario": (
                    "Período complexo bem construído, com inciso "
                    "intercalado e vírgulas adequadas."
                ),
            },
            {
                "trecho": (
                    "a maioria dos jovens sem plano de saúde simplesmente "
                    "não tem acesso a tratamento — direito previsto em lei "
                    "vira ficção operacional"
                ),
                "comentario": (
                    "Vocabulário preciso ('ficção operacional') e uso "
                    "correto do travessão pra ênfase."
                ),
            },
        ],
    },
    "c2_audit": {
        "nota": 160,
        "feedback_text": (
            "Tema bem abordado, com recorte claro: pressão social + "
            "precariedade do SUS. Repertório sociocultural sólido — "
            "Byung-Chul Han é integrado ao argumento (não decorativo), "
            "e os dados do Ministério da Saúde e do CFP são pertinentes "
            "ao recorte. Atenção: a citação de Han poderia ser mais "
            "explorada — você nomeia mas não desdobra a ideia de "
            "'autoexploração' nos parágrafos seguintes."
        ),
        "evidencias": [
            {
                "trecho": (
                    "Segundo dados do Ministério da Saúde (2023), o "
                    "suicídio é a quarta principal causa de morte entre "
                    "brasileiros de 15 a 29 anos"
                ),
                "comentario": (
                    "Dado oficial nomeado, com fonte e ano. Exatamente "
                    "o que a banca espera de repertório legítimo."
                ),
            },
            {
                "trecho": (
                    "a Rede de Atenção Psicossocial (RAPS), instituída "
                    "pela Lei 10.216/2001, prevê os Centros de Atenção "
                    "Psicossocial Infantojuvenis (CAPSi)"
                ),
                "comentario": (
                    "Repertório legal específico com lei e órgão "
                    "nomeados — não cai no genérico 'estudos mostram'."
                ),
            },
        ],
    },
    "c3_audit": {
        "nota": 120,
        "feedback_text": (
            "Argumentação parcial. Os dois desenvolvimentos têm tópico "
            "frasal e usam repertório, mas o texto se aproxima mais da "
            "descrição do problema do que da defesa de uma leitura "
            "específica. Falta um movimento argumentativo claro de "
            "'sustentação' — você apresenta o cenário, mas não constrói "
            "uma cadeia causal forte do tipo 'X acontece PORQUE Y, e "
            "ISSO LEVA A Z'. A profundidade do argumento perde força "
            "quando ele se torna enumerativo."
        ),
        "evidencias": [
            {
                "trecho": (
                    "Quando o jovem fala \"estou cansado\", a resposta "
                    "cultural costuma ser \"todos estão\" — e a busca "
                    "por ajuda é adiada até o quadro virar emergência."
                ),
                "comentario": (
                    "Bom uso de exemplo cotidiano, mas a explicação "
                    "para PORQUE essa cultura de invalidação existe não "
                    "aparece — fica observação descritiva."
                ),
            },
            {
                "trecho": (
                    "O resultado é que a maioria dos jovens sem plano "
                    "de saúde simplesmente não tem acesso a tratamento"
                ),
                "comentario": (
                    "Conclusão lógica do dado anterior, mas você poderia "
                    "ter desdobrado mais — quais são as consequências "
                    "encadeadas dessa exclusão?"
                ),
            },
        ],
    },
    "c4_audit": {
        "nota": 160,
        "feedback_text": (
            "Coesão muito boa. Conectivos variados ('Em primeiro lugar', "
            "'Ademais', 'No entanto', 'Segundo', 'Quando') marcam bem as "
            "transições entre ideias. Referenciação anafórica funciona "
            "(uso de 'essa cultura', 'esse problema'). Único ponto: o "
            "último parágrafo abre com 'A sociedade brasileira precisa "
            "enfrentar' sem conectivo de fechamento ('Portanto', 'Diante "
            "do exposto') — perde a marcação estrutural da conclusão."
        ),
        "evidencias": [
            {
                "trecho": (
                    "Ademais, a Rede de Atenção Psicossocial (RAPS), "
                    "instituída pela Lei 10.216/2001"
                ),
                "comentario": (
                    "Transição entre D1 e D2 com conectivo adequado de "
                    "adição/avanço."
                ),
            },
            {
                "trecho": "No entanto, apenas 11% dos municípios brasileiros",
                "comentario": (
                    "Oposição bem marcada — contraste entre a previsão "
                    "legal e a realidade operacional."
                ),
            },
        ],
    },
    "c5_audit": {
        "nota": 120,
        "feedback_text": (
            "Proposta de intervenção parcial. Você indica que 'governos, "
            "sociedade e mídia' devem agir, mas o agente fica genérico: "
            "'governos' (qual nível? Federal, estadual, municipal? "
            "Ministério da Saúde?) e 'sociedade' (institucional? "
            "Familiar? Movimento social?). A AÇÃO ('trabalhar juntos pra "
            "garantir') é vaga — falta o verbo concreto (ampliar, "
            "implementar, fiscalizar). MEIO e DETALHAMENTO não aparecem. "
            "FINALIDADE está presente ('para um futuro melhor'). "
            "Pra nota 200, a proposta precisa dos 5 elementos com pelo "
            "menos 1 detalhado."
        ),
        "evidencias": [
            {
                "trecho": (
                    "Cabe aos governos, à sociedade e à mídia trabalhar "
                    "juntos para garantir que os jovens tenham um futuro "
                    "melhor"
                ),
                "comentario": (
                    "Agentes genéricos sem qualificação + ação vaga + "
                    "ausência de meio. Falta operacionalizar."
                ),
            },
        ],
    },
    "feedback_professor": {
        "pontos_fortes": [
            "Repertório sociocultural integrado e legítimo: Byung-Chul "
            "Han (2010), dados Ministério da Saúde (2023), Lei "
            "10.216/2001, Conselho Federal de Psicologia. Todos com "
            "fonte verificável — não cai no genérico 'estudos mostram'.",
            "Coesão textual sólida: conectivos variados e adequados "
            "entre parágrafos (Em primeiro lugar / Ademais / No entanto), "
            "e referenciação anafórica clara.",
            "Norma culta sem desvios graves, com vocabulário argumentativo "
            "preciso ('ficção operacional', 'autoexploração').",
        ],
        "pontos_fracos": [
            "Argumentação predominantemente DESCRITIVA — apresenta o "
            "problema mas não constrói cadeia causal forte que "
            "DEFENDA uma leitura específica. Falta o movimento de "
            "sustentação argumentativa.",
            "Proposta de intervenção com 3 dos 5 elementos canônicos: "
            "agente está GENÉRICO ('governos', 'sociedade', 'mídia'), "
            "ação está VAGA ('trabalhar juntos'), e MEIO + DETALHAMENTO "
            "ausentes.",
            "Repertório de Han nomeado mas não desdobrado — o conceito "
            "de 'autoexploração' poderia estruturar a defesa argumentativa "
            "do D1, mas vira citação isolada.",
        ],
        "padrao_falha": (
            "Padrão típico de aluno com boa C1+C2+C4 que perde nota em "
            "C3 e C5 por não dar o salto da DESCRIÇÃO pra DEFESA. "
            "Sabe nomear o problema, mas não constrói raciocínio "
            "sustentado que leve a uma proposta operacional."
        ),
        "transferencia_competencia": (
            "Trabalhar 'extração de consequência do repertório' (C2.007) "
            "tem efeito colateral em C3 — quando o aluno aprende a usar "
            "Han, não só citar, a profundidade argumentativa (C3.004) "
            "também sobe junto. Ganho composto."
        ),
    },
    "_mission": {
        "mode": "completo",
        "model": "claude-opus-4-7",
        "request_id": "demo_seed_2026-05-04",
    },
}


# ──────────────────────────────────────────────────────────────────────
# Diagnóstico cognitivo (40 descritores) — schema da Fase 2
# ──────────────────────────────────────────────────────────────────────

# Lacunas prioritárias coerentes com a redação (nota 720, falha em C5
# e C3): aluno tem proposta incompleta (C5.001, C5.002, C5.005) e
# argumentação descritiva (C3.007, C2.007).
_STATUS_POR_ID: Dict[str, str] = {
    # C1 — Norma culta: tudo domínio (C1 = 160)
    "C1.001": "dominio", "C1.002": "dominio", "C1.003": "dominio",
    "C1.004": "dominio", "C1.005": "dominio", "C1.006": "dominio",
    "C1.007": "dominio", "C1.008": "dominio",
    # C2 — Compreensão da proposta: dominio com 1 lacuna em uso produtivo
    "C2.001": "dominio", "C2.002": "dominio", "C2.003": "dominio",
    "C2.004": "dominio", "C2.005": "dominio", "C2.006": "dominio",
    "C2.007": "lacuna",  # ← repertório não desdobrado
    "C2.008": "dominio",
    # C3 — Argumentação: descrição em vez de defesa
    "C3.001": "dominio", "C3.002": "dominio", "C3.003": "dominio",
    "C3.004": "lacuna",  # ← profundidade
    "C3.005": "dominio", "C3.006": "dominio",
    "C3.007": "lacuna",  # ← defesa de PV
    "C3.008": "incerto",
    # C4 — Coesão: tudo domínio
    "C4.001": "dominio", "C4.002": "dominio", "C4.003": "dominio",
    "C4.004": "dominio", "C4.005": "dominio", "C4.006": "dominio",
    "C4.007": "dominio",
    "C4.008": "incerto",  # ← conclusão sem marcador
    # C5 — Proposta: 3 lacunas grandes
    "C5.001": "lacuna",  # ← agente genérico
    "C5.002": "lacuna",  # ← ação vaga
    "C5.003": "lacuna",  # ← meio ausente
    "C5.004": "dominio",
    "C5.005": "lacuna",  # ← detalhamento ausente
    "C5.006": "dominio",
    "C5.007": "dominio",
    "C5.008": "lacuna",  # ← completude (3 de 5)
}

# Evidências por descritor lacuna (trechos reais do texto)
_EVIDENCIAS_POR_ID: Dict[str, list] = {
    "C2.007": [
        "Como aponta Byung-Chul Han, em \"Sociedade do Cansaço\" (2010), "
        "vivemos uma época em que a autoexploração substituiu a coerção externa",
    ],
    "C3.004": [
        "Quando o jovem fala \"estou cansado\", a resposta cultural costuma "
        "ser \"todos estão\" — e a busca por ajuda é adiada",
    ],
    "C3.007": [
        "Cabe aos governos, à sociedade e à mídia trabalhar juntos para "
        "garantir que os jovens tenham um futuro melhor",
        "É fundamental que todos se conscientizem sobre a saúde mental dos jovens",
    ],
    "C3.008": [
        "É fundamental que todos se conscientizem sobre a saúde mental dos jovens",
    ],
    "C4.008": [
        "A sociedade brasileira precisa enfrentar esse problema com urgência.",
    ],
    "C5.001": [
        "Cabe aos governos, à sociedade e à mídia trabalhar juntos",
    ],
    "C5.002": [
        "trabalhar juntos para garantir que os jovens tenham um futuro melhor",
    ],
    "C5.003": [
        "Cabe aos governos, à sociedade e à mídia trabalhar juntos para "
        "garantir que os jovens tenham um futuro melhor",
    ],
    "C5.005": [
        "Cabe aos governos, à sociedade e à mídia trabalhar juntos para "
        "garantir que os jovens tenham um futuro melhor",
    ],
    "C5.008": [
        "Cabe aos governos, à sociedade e à mídia trabalhar juntos",
    ],
}


def _build_diagnostico_cognitivo() -> Dict[str, Any]:
    """Monta JSON do diagnóstico cognitivo (Fase 2) coerente com a
    redação de demo. Replica schema do `inferir_diagnostico`."""
    from redato_backend.diagnostico import load_descritores

    descritores_yaml = load_descritores()
    entries = []
    for d in descritores_yaml:
        status = _STATUS_POR_ID.get(d.id, "dominio")
        evidencias = _EVIDENCIAS_POR_ID.get(d.id, [])
        # Confiança: alta pra lacunas com evidência, média pra dominio
        # com evidência, baixa pra incerto
        if status == "lacuna":
            confianca = "alta" if evidencias else "media"
        elif status == "incerto":
            confianca = "baixa"
        else:
            confianca = "media"
        entries.append({
            "id": d.id,
            "status": status,
            "evidencias": list(evidencias),
            "confianca": confianca,
        })

    # Lacunas prioritárias com diversidade (max 2 por competência) —
    # mesma estratégia do `diversificar_lacunas_prioritarias` Fase 3
    lacunas_prioritarias = [
        "C5.001",  # Agente genérico — alta C5
        "C5.005",  # Detalhamento ausente — alta C5
        "C3.007",  # Defesa de PV (descrição) — alta C3
        "C3.004",  # Profundidade — alta C3
        "C2.007",  # Repertório não-produtivo — alta C2
    ]

    return {
        "schema_version": "1.0",
        "modelo_usado": "gpt-4.1-2025-04-14",
        "descritores_versao": "1.0",
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "latencia_ms": 12350,
        "custo_estimado_usd": 0.0418,
        "input_tokens": 2945,
        "output_tokens": 5120,
        "descritores": entries,
        "lacunas_prioritarias": lacunas_prioritarias,
        "resumo_qualitativo": (
            "Aluno com boa base em norma culta (C1) e coesão (C4), mas "
            "argumentação predominantemente descritiva (C3) e proposta "
            "de intervenção com agentes/ações genéricos (C5). Tem "
            "repertório legítimo e atual (Han, dados MS, Lei 10.216/2001), "
            "mas não desdobra os conceitos pra sustentar leitura própria. "
            "Nota 720 reflete potencial pra 850+ se trabalhar 'extração "
            "de consequência do repertório' e 'proposta com 5 elementos "
            "detalhados'."
        ),
        "recomendacao_breve": (
            "Reforço prioritário em C5 (5 elementos canônicos da proposta) "
            "e C3.007 (defesa de ponto de vista vs descrição). Ganho "
            "composto: trabalhar repertório produtivo (C2.007) eleva "
            "também a profundidade argumentativa (C3.004)."
        ),
    }


# ──────────────────────────────────────────────────────────────────────
# Helpers de persistência
# ──────────────────────────────────────────────────────────────────────

def _get_or_create_escola(session) -> Any:
    from redato_backend.portal.models import Escola
    from sqlalchemy import select

    escola = session.execute(
        select(Escola).where(Escola.nome == DEMO_ESCOLA_NOME)
    ).scalar_one_or_none()
    if escola:
        return escola
    escola = Escola(
        codigo="DEMO-ESC",
        nome=DEMO_ESCOLA_NOME,
        municipio="São Paulo",
        estado="SP",
        ativa=True,
    )
    session.add(escola)
    session.flush()
    return escola


def _get_or_create_professor(session, escola) -> Any:
    from redato_backend.portal.models import Professor
    from sqlalchemy import select

    prof = session.execute(
        select(Professor).where(Professor.email == DEMO_PROFESSOR_EMAIL)
    ).scalar_one_or_none()
    if prof:
        return prof
    prof = Professor(
        escola_id=escola.id,
        nome=DEMO_PROFESSOR_NOME,
        email=DEMO_PROFESSOR_EMAIL,
        senha_hash=None,  # primeiro acesso pendente, mas demo seed não loga
        ativo=True,
    )
    session.add(prof)
    session.flush()
    return prof


def _get_or_create_turma(session, escola, professor) -> Any:
    from redato_backend.portal.models import Turma
    from sqlalchemy import select

    turma = session.execute(
        select(Turma).where(Turma.codigo_join == DEMO_TURMA_CODIGO_JOIN)
    ).scalar_one_or_none()
    if turma:
        return turma
    turma = Turma(
        escola_id=escola.id,
        professor_id=professor.id,
        codigo=DEMO_TURMA_CODIGO,
        codigo_join=DEMO_TURMA_CODIGO_JOIN,
        serie="1S",
        ano_letivo=2026,
        ativa=True,
    )
    session.add(turma)
    session.flush()
    return turma


def _get_or_create_aluno(session, turma) -> Any:
    from redato_backend.portal.models import AlunoTurma
    from sqlalchemy import select

    aluno = session.execute(
        select(AlunoTurma).where(
            AlunoTurma.turma_id == turma.id,
            AlunoTurma.telefone == DEMO_ALUNO_TELEFONE,
        )
    ).scalar_one_or_none()
    if aluno:
        return aluno
    aluno = AlunoTurma(
        turma_id=turma.id,
        nome=DEMO_ALUNO_NOME,
        telefone=DEMO_ALUNO_TELEFONE,
        ativo=True,
    )
    session.add(aluno)
    session.flush()
    return aluno


def _get_or_create_atividade(session, turma) -> Any:
    from redato_backend.portal.models import Atividade, Missao
    from sqlalchemy import select

    missao = session.execute(
        select(Missao).where(Missao.codigo == DEMO_MISSAO_CODIGO)
    ).scalar_one_or_none()
    if missao is None:
        raise RuntimeError(
            f"Missão {DEMO_MISSAO_CODIGO} não está seedada. Rode "
            "`seed_missoes.py` antes."
        )

    agora = datetime.now(timezone.utc)
    atividade = session.execute(
        select(Atividade).where(
            Atividade.turma_id == turma.id,
            Atividade.missao_id == missao.id,
            Atividade.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if atividade:
        # Renova prazo se já passou
        if atividade.data_fim < agora:
            atividade.data_fim = agora + timedelta(days=30)
        return atividade
    atividade = Atividade(
        turma_id=turma.id,
        missao_id=missao.id,
        data_inicio=agora - timedelta(days=1),
        data_fim=agora + timedelta(days=30),
        criada_por_professor_id=turma.professor_id,
    )
    session.add(atividade)
    session.flush()
    return atividade


def _create_envio_com_correcao(session, atividade, aluno) -> tuple:
    """Cria Interaction + Envio com redato_output + diagnostico
    populados. Idempotente: re-rodar atualiza os JSONs em vez de
    duplicar.
    """
    from redato_backend.portal.models import Envio, Interaction
    from sqlalchemy import select

    # Busca envio existente desse (atividade, aluno)
    envio = session.execute(
        select(Envio).where(
            Envio.atividade_id == atividade.id,
            Envio.aluno_turma_id == aluno.id,
        ).order_by(Envio.tentativa_n.desc()).limit(1)
    ).scalar_one_or_none()

    redato_output_json = json.dumps(
        DEMO_REDATO_OUTPUT, ensure_ascii=False, default=str,
    )
    diagnostico = _build_diagnostico_cognitivo()

    if envio is not None and envio.interaction_id is not None:
        # Atualiza
        interaction = session.get(Interaction, envio.interaction_id)
        if interaction is not None:
            interaction.texto_transcrito = DEMO_TEXTO_REDACAO
            interaction.redato_output = redato_output_json
            interaction.resposta_aluno = (
                "📊 *Sua redação foi avaliada!*\n\n"
                "C1 (Norma culta): 160/200\n"
                "C2 (Tema + repertório): 160/200\n"
                "C3 (Argumentação): 120/200\n"
                "C4 (Coesão): 160/200\n"
                "C5 (Proposta): 120/200\n\n"
                "*Total: 720/1000*\n\n"
                "Pontos fortes: repertório integrado (Han, Lei 10.216) e "
                "coesão sólida. Atenção: sua argumentação descreve o "
                "problema mais do que defende uma leitura, e a proposta "
                "precisa de agente nomeado + meio + detalhamento."
            )
            interaction.elapsed_ms = 28450
        envio.diagnostico = diagnostico
        session.commit()
        return interaction, envio

    # Cria novo
    interaction = Interaction(
        aluno_phone=DEMO_ALUNO_TELEFONE,
        aluno_turma_id=aluno.id,
        source="seed_demo",
        missao_id=DEMO_MISSAO_CODIGO.replace("·", "_"),
        activity_id=DEMO_MISSAO_CODIGO,
        foto_path=None,  # sem foto — frontend mostra "não persistida"
        foto_hash="demo_seed_hash",
        texto_transcrito=DEMO_TEXTO_REDACAO,
        ocr_quality_issues=json.dumps([], ensure_ascii=False),
        ocr_metrics=json.dumps({"brilho": 142, "laplaciano": 280},
                                ensure_ascii=False),
        redato_output=redato_output_json,
        resposta_aluno=(
            "📊 *Sua redação foi avaliada!*\n\n"
            "C1 (Norma culta): 160/200\n"
            "C2 (Tema + repertório): 160/200\n"
            "C3 (Argumentação): 120/200\n"
            "C4 (Coesão): 160/200\n"
            "C5 (Proposta): 120/200\n\n"
            "*Total: 720/1000*"
        ),
        elapsed_ms=28450,
    )
    session.add(interaction)
    session.flush()

    envio = Envio(
        atividade_id=atividade.id,
        aluno_turma_id=aluno.id,
        interaction_id=interaction.id,
        enviado_em=datetime.now(timezone.utc),
        tentativa_n=1,
        diagnostico=diagnostico,
    )
    session.add(envio)
    session.flush()

    interaction.envio_id = envio.id
    session.commit()
    return interaction, envio


# ──────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(
        level="INFO",
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    from sqlalchemy.orm import Session
    from redato_backend.portal.db import get_engine

    print("=" * 60)
    print("Redato — Seed de demo")
    print("=" * 60)
    print()

    with Session(get_engine()) as session:
        print("1. Garantindo Escola, Professor, Turma…")
        escola = _get_or_create_escola(session)
        professor = _get_or_create_professor(session, escola)
        turma = _get_or_create_turma(session, escola, professor)
        session.commit()
        print(f"   ✓ Escola: {escola.id}")
        print(f"   ✓ Professor: {professor.id} ({professor.email})")
        print(f"   ✓ Turma: {turma.id} ({turma.codigo_join})")
        print()

        print("2. Garantindo aluno + atividade ativa…")
        aluno = _get_or_create_aluno(session, turma)
        atividade = _get_or_create_atividade(session, turma)
        session.commit()
        print(f"   ✓ Aluno: {aluno.id} ({aluno.nome})")
        print(f"   ✓ Atividade: {atividade.id} ({DEMO_MISSAO_CODIGO})")
        print(f"   ✓ Prazo: até {atividade.data_fim.strftime('%d/%m/%Y')}")
        print()

        print("3. Criando envio com correção + diagnóstico…")
        interaction, envio = _create_envio_com_correcao(
            session, atividade, aluno,
        )
        print(f"   ✓ Interaction id: {interaction.id}")
        print(f"   ✓ Envio: {envio.id}")
        print(f"   ✓ Nota total: 720/1000")
        print(f"   ✓ Lacunas prioritárias: 5 (C5.001, C5.005, C3.007, "
              f"C3.004, C2.007)")
        print()

    print("=" * 60)
    print("Demo pronto. URLs pra printar:")
    print("=" * 60)
    frontend = "https://frontend-production-74ab7.up.railway.app"
    print()
    print("Dashboard da turma (storytelling):")
    print(f"  {frontend}/turma/{turma.id}")
    print()
    print("Perfil do aluno (Mapa Cognitivo + heatmap + BNCC):")
    print(f"  {frontend}/turma/{turma.id}/aluno/{aluno.id}")
    print()
    print("Atividade — detalhe da redação do aluno (correção + análise):")
    print(f"  {frontend}/atividade/{atividade.id}/aluno/{aluno.id}")
    print()
    print("Credenciais pra logar (caso ainda não tenha):")
    print(f"  email: {professor.email}")
    print(f"  Setar senha via shell:")
    print(f"  python -c 'from redato_backend.portal.auth.password import "
          f"hash_senha; print(hash_senha(\"demo123\"))'")
    print(f"  psql \"$DATABASE_URL\" -c \"UPDATE professores SET senha_hash "
          f"= '<HASH>' WHERE email = '{professor.email}';\"")
    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
