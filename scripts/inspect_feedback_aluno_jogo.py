#!/usr/bin/env python3
"""Inspeção qualitativa do feedback_aluno do modo jogo_redacao com Claude real.

Roda 6 cenários cobrindo a faixa esperada de notas em uma única
execução, pra Daniel ler o output e calibrar o registro do
feedback_aluno (commits 3812079 e 614af41).

Cenários (todos com mesmas cartas escolhidas):
  1. Cópia literal              (transformacao 0-15)
  2. Conectivos trocados        (transformacao 30-50)
  3. Autoral substancial        (transformacao 70-90)
  4. Excelente, mira 900+       (transformacao 85-100)
  5. Fuga do tema               (flag + C2 cap 80)
  6. Desrespeito DH             (flags + C1=0 + C5=0)

Cada cenário imprime: nome + reescrita preview (200 chars) + notas
+ transformação + flags + feedback_aluno completo. Ao final, sumário
com custo total estimado e tempo.

NÃO toca DB. NÃO roda em CI (depende de ANTHROPIC_API_KEY). NÃO
trata de calibração — só roda os 6 e mostra. Daniel analisa.

Uso:
    cd backend/notamil-backend
    ANTHROPIC_API_KEY=... python ../../scripts/inspect_feedback_aluno_jogo.py

Variáveis opcionais:
    REDATO_MISSION_MODEL   override do modelo (default sonnet-4-6)
"""
from __future__ import annotations

import os
import sys
import time
from collections import namedtuple
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend" / "notamil-backend"
sys.path.insert(0, str(BACKEND))

try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]
    load_dotenv(BACKEND / ".env")
except ImportError:
    pass


# ──────────────────────────────────────────────────────────────────────
# Catálogo do minideck Saúde Mental — reaproveitado do test
# ──────────────────────────────────────────────────────────────────────
#
# Daniel pediu reuso do `_lacunas_minideck_saude_mental()` em
# test_jogo_redacao_canarios.py. Importamos direto — esses tests
# importam `pytest` no topo, então essa import só funciona em
# ambiente de dev (Daniel local) que tem pytest instalado. Não
# rodamos esse script em prod, então OK.

from redato_backend.tests.missions.test_jogo_redacao_canarios import (
    _lacunas_minideck_saude_mental,
)


Est = namedtuple("Est", ["codigo", "secao", "cor", "texto", "lacunas"])


def _build_estruturais() -> Dict[str, Est]:
    """10 estruturais (1 por seção do tabuleiro). Catálogo reduzido
    pra prompt — redato real teria 63 estruturais mas pra inspect
    bastam as 10 escolhidas pelo grupo."""
    return {
        "E01": Est(
            "E01", "ABERTURA", "AZUL",
            "No Brasil, [PROBLEMA] persiste como questão central. "
            "Conforme [REPERTORIO], demanda atenção urgente.",
            ["PROBLEMA", "REPERTORIO"],
        ),
        "E10": Est(
            "E10", "TESE", "AZUL",
            "Cenário impulsionado por [PALAVRA_CHAVE].",
            ["PALAVRA_CHAVE"],
        ),
        "E17": Est(
            "E17", "TOPICO_DEV1", "AMARELO",
            "Em primeira análise, [PROBLEMA] liga-se a "
            "[PALAVRA_CHAVE].",
            ["PROBLEMA", "PALAVRA_CHAVE"],
        ),
        "E19": Est(
            "E19", "ARGUMENTO_DEV1", "AMARELO",
            "Tal realidade é agravada por [PALAVRA_CHAVE].",
            ["PALAVRA_CHAVE"],
        ),
        "E21": Est(
            "E21", "REPERTORIO_DEV1", "AMARELO",
            "Comprovado por [REPERTORIO].",
            ["REPERTORIO"],
        ),
        "E33": Est(
            "E33", "TOPICO_DEV2", "VERDE",
            "Outro fator: [PALAVRA_CHAVE] amplia [PROBLEMA].",
            ["PALAVRA_CHAVE", "PROBLEMA"],
        ),
        "E35": Est(
            "E35", "ARGUMENTO_DEV2", "VERDE",
            "Há prejuízos para [PALAVRA_CHAVE].",
            ["PALAVRA_CHAVE"],
        ),
        "E37": Est(
            "E37", "REPERTORIO_DEV2", "VERDE",
            "Análise encontra respaldo em [REPERTORIO].",
            ["REPERTORIO"],
        ),
        "E49": Est(
            "E49", "RETOMADA", "LARANJA",
            "Evidencia-se que [PROBLEMA] exige [ACAO_MEIO].",
            ["PROBLEMA", "ACAO_MEIO"],
        ),
        "E51": Est(
            "E51", "PROPOSTA", "LARANJA",
            "[AGENTE] tem como prioridade [ACAO_MEIO].",
            ["AGENTE", "ACAO_MEIO"],
        ),
    }


# ──────────────────────────────────────────────────────────────────────
# Texto montado e cartas escolhidas — compartilhados pelos 6 cenários
# ──────────────────────────────────────────────────────────────────────
#
# Daniel especificou texto_montado curto pro cenário 1. Reutilizamos
# nos 6 cenários — varia só `reescrita_texto`. Isso isola a variável
# (texto_montado fixo, registro/qualidade da reescrita varia).

_TEXTO_MONTADO = (
    "No Brasil, estigma social associado aos transtornos mentais "
    "persiste. Conforme OMS, demanda atenção. Cenário impulsionado "
    "por falta de investimento público. Em primeira análise, "
    "estigma social impacta vida cotidiana. Cabe ao Ministério da "
    "Saúde, por meio do Fundo Nacional de Saúde, garantir acesso "
    "universal a tratamento psicológico."
)

# 10 estruturais + 7 lacunas escolhidas pelo grupo
_CODIGOS_ESCOLHIDOS = [
    "E01", "E10", "E17", "E19", "E21", "E33", "E35", "E37",
    "E49", "E51",
    "P01", "R01", "K01", "A01", "AC07", "ME04", "F02",
]


# ──────────────────────────────────────────────────────────────────────
# Reescritas dos 6 cenários
# ──────────────────────────────────────────────────────────────────────

# CENÁRIO 1 — cópia literal (igual texto_montado)
_REESCRITA_1_COPIA = _TEXTO_MONTADO

# CENÁRIO 2 — conectivos trocados / paráfrase superficial
_REESCRITA_2_CONECTIVOS = (
    "No Brasil, o estigma social ligado aos transtornos mentais "
    "ainda existe. De acordo com a OMS, isso pede atenção. A "
    "situação é causada pela falta de investimento público. "
    "Inicialmente, o estigma social atinge o dia a dia. Por isso, "
    "o Ministério da Saúde, através do Fundo Nacional de Saúde, "
    "deve garantir acesso universal ao tratamento psicológico."
)

# CENÁRIO 3 — autoral substancial (mesmo do canário caso_feliz)
_REESCRITA_3_SUBSTANCIAL = (
    "O estigma cultural em torno dos transtornos mentais "
    "configura-se como um dos principais obstáculos ao acesso "
    "à saúde no Brasil contemporâneo. Segundo dados da "
    "Organização Mundial da Saúde, mais de 86% das pessoas com "
    "transtornos mentais no país não recebem tratamento "
    "adequado, evidência que escancara a urgência do tema.\n\n"
    "Essa exclusão tem raízes culturais — o silêncio sobre "
    "sofrimento psíquico ainda é regra em muitas famílias — mas "
    "é potencializada pelo desinvestimento estrutural na rede "
    "pública. Conforme aponta a OMS, a articulação entre estigma "
    "e subfinanciamento perpetua um ciclo no qual quem mais "
    "precisa de atendimento é também quem menos consegue acessar.\n\n"
    "Diante desse cenário, cabe ao Ministério da Saúde, por meio "
    "da ampliação efetiva da rede de Centros de Atenção "
    "Psicossocial e do redirecionamento de emendas parlamentares, "
    "garantir que o tratamento psicológico deixe de ser "
    "privilégio e se torne direito exercido cotidianamente. "
    "Somente assim será possível romper o silêncio histórico "
    "que cerca a saúde mental no país."
)

# CENÁRIO 4 — excelente, mira 900+
_REESCRITA_4_EXCELENTE = (
    "O estigma cultural em torno dos transtornos mentais "
    "configura-se como o principal obstáculo ao acesso à saúde "
    "mental no Brasil. Dados da Organização Mundial da Saúde "
    "apontam que mais de 86% das pessoas com transtornos mentais "
    "no país não recebem tratamento adequado, indicador que "
    "escancara a magnitude do problema. Esse desamparo, longe "
    "de ser acidente estatístico, articula duas dimensões "
    "interdependentes. De um lado, raízes culturais profundas — "
    "o silêncio sobre o sofrimento psíquico, ainda regra em "
    "muitas famílias brasileiras, transforma o adoecimento em "
    "assunto privado e inominável. De outro, esse silêncio é "
    "potencializado pelo desinvestimento estrutural na rede "
    "pública, uma vez que a ausência de serviços especializados "
    "acessíveis perpetua a ideia de que sofrimento mental não é "
    "questão de saúde pública. Para romper esse ciclo, cabe ao "
    "Ministério da Saúde, por meio da ampliação efetiva da rede "
    "de Centros de Atenção Psicossocial (CAPS) e do uso de "
    "emendas parlamentares vinculadas ao SUS, garantir que o "
    "tratamento psicológico deixe de ser privilégio de quem pode "
    "pagar e se torne direito exercido cotidianamente. A medida "
    "deve incluir contratação de profissionais, campanhas "
    "educativas em escolas e mídia, e integração com a atenção "
    "básica, viabilizando enfim o que a Constituição já prometia: "
    "saúde como direito de todos."
)

# CENÁRIO 5 — fuga do tema (escreve sobre saúde física, não mental)
_REESCRITA_5_FUGA = (
    "A saúde pública no Brasil enfrenta diversos desafios, "
    "especialmente quanto ao acesso de toda a população. As "
    "filas em hospitais e a escassez de medicamentos são "
    "problemas frequentes que afetam milhares de brasileiros. "
    "É necessário que o governo federal invista em mais "
    "hospitais e contrate mais médicos para atender essa "
    "demanda crescente, garantindo o direito constitucional "
    "à saúde."
)

# CENÁRIO 6 — desrespeito a Direitos Humanos (zera C1+C5)
_REESCRITA_6_DH = (
    "As pessoas com transtornos mentais são um peso para a "
    "sociedade e deveriam ser isoladas em instituições afastadas "
    "dos centros urbanos. O governo gasta dinheiro público demais "
    "com esse tipo de gente, quando poderia investir em quem "
    "realmente trabalha. A solução é parar de fingir que doença "
    "mental é igual doença física e tratar essas pessoas como "
    "casos perdidos."
)


# ──────────────────────────────────────────────────────────────────────
# Definição dos 6 cenários (ordem importa — Daniel lê em sequência)
# ──────────────────────────────────────────────────────────────────────

CENARIOS: List[Dict[str, Any]] = [
    {
        "n": 1,
        "nome": "Cópia literal",
        "esperado": "transformacao 0-15, copia_literal=true, total ~480-560",
        "reescrita": _REESCRITA_1_COPIA,
    },
    {
        "n": 2,
        "nome": "Conectivos trocados (paráfrase superficial)",
        "esperado": "transformacao 30-50, total ~600-700",
        "reescrita": _REESCRITA_2_CONECTIVOS,
    },
    {
        "n": 3,
        "nome": "Reescrita autoral substancial",
        "esperado": "transformacao 70-90, total ~750-850",
        "reescrita": _REESCRITA_3_SUBSTANCIAL,
    },
    {
        "n": 4,
        "nome": "Reescrita excelente, mira 900+",
        "esperado": "transformacao 85-100, total ~880-950",
        "reescrita": _REESCRITA_4_EXCELENTE,
    },
    {
        "n": 5,
        "nome": "Fuga do tema (saúde física, não mental)",
        "esperado": "fuga_do_tema=true, C2 cap 80, total ~400-560",
        "reescrita": _REESCRITA_5_FUGA,
    },
    {
        "n": 6,
        "nome": "Desrespeito a Direitos Humanos",
        "esperado": "desrespeito_dh=true, C1=0, C5=0, total ~80-200",
        "reescrita": _REESCRITA_6_DH,
    },
]


# ──────────────────────────────────────────────────────────────────────
# Render
# ──────────────────────────────────────────────────────────────────────

_BAR = "=" * 64
_BAR_THIN = "-" * 64


def _print_header(cen: Dict[str, Any]) -> None:
    print()
    print(_BAR)
    print(f"CENÁRIO {cen['n']} — {cen['nome']}")
    print(_BAR)
    print(f"_Esperado: {cen['esperado']}_\n")


def _print_reescrita_preview(reescrita: str) -> None:
    preview = reescrita[:200].replace("\n", " ").strip()
    if len(reescrita) > 200:
        preview += "..."
    print(f"Reescrita (primeiros 200 chars):\n  \"{preview}\"\n")


def _print_notas_e_flags(out: Dict[str, Any]) -> None:
    notas = out.get("notas_enem") or {}
    total = out.get("nota_total_enem", "?")
    transformacao = out.get("transformacao_cartas", "?")

    print("NOTAS ENEM")
    print(f"  C1: {notas.get('c1', '?'):<4}"
          f" C2: {notas.get('c2', '?'):<4}"
          f" C3: {notas.get('c3', '?'):<4}"
          f" C4: {notas.get('c4', '?'):<4}"
          f" C5: {notas.get('c5', '?')}")
    print(f"  Total: {total}/1000")
    print(f"  Transformação: {transformacao}/100\n")

    flags = out.get("flags") or {}
    flags_on = [k for k, v in flags.items() if v]
    print("FLAGS")
    if flags_on:
        for f in flags_on:
            print(f"  - {f}")
    else:
        print("  (nenhuma ativada)")
    print()

    sugestoes = out.get("sugestoes_cartas_alternativas") or []
    if sugestoes:
        print(f"SUGESTÕES DE CARTAS ALTERNATIVAS ({len(sugestoes)}):")
        for s in sugestoes:
            print(f"  - {s.get('codigo_original')} → "
                  f"{s.get('codigo_sugerido')}: {s.get('motivo')}")
        print()


def _print_feedback_aluno(out: Dict[str, Any]) -> None:
    fa = out.get("feedback_aluno") or {}
    acertos = fa.get("acertos") or []
    ajustes = fa.get("ajustes") or []

    print("FEEDBACK_ALUNO — Acertos:")
    if acertos:
        for a in acertos:
            print(f"  - {a}")
    else:
        print("  (vazio)")
    print()

    print("FEEDBACK_ALUNO — Ajustes:")
    if ajustes:
        for a in ajustes:
            print(f"  - {a}")
    else:
        print("  (vazio)")
    print()


def _print_feedback_professor_padrao(out: Dict[str, Any]) -> None:
    """Imprime apenas `padrao_falha` do feedback_professor — útil pra
    Daniel ver o diagnóstico técnico em 1 frase. O feedback_professor
    completo (pontos_fortes/pontos_fracos/transferencia) fica
    acessível no JSON retornado se Daniel quiser inspecionar."""
    fp = out.get("feedback_professor") or {}
    padrao = (fp.get("padrao_falha") or "").strip()
    print("FEEDBACK_PROFESSOR — Padrão de falha:")
    if padrao:
        print(f"  {padrao}")
    else:
        print("  (vazio)")
    print()


# ──────────────────────────────────────────────────────────────────────
# Pipeline — chama Claude e formata
# ──────────────────────────────────────────────────────────────────────

def _build_payload(reescrita: str, lacunas, estruturais):
    return {
        "tema_minideck": "saude_mental",
        "nome_humano_tema": "Saúde Mental",
        "cartas_lacuna_full": list(lacunas.values()),
        "codigos_escolhidos": _CODIGOS_ESCOLHIDOS,
        "estruturais_por_codigo": estruturais,
        "lacunas_por_codigo": lacunas,
        "texto_montado": _TEXTO_MONTADO,
        "reescrita_texto": reescrita,
    }


def _executa_cenario(
    cen: Dict[str, Any], lacunas, estruturais,
) -> Dict[str, Any]:
    """Roda 1 cenário. Retorna dict com:
        - cenario (n + nome)
        - elapsed_s: tempo da chamada
        - resultado: tool_args do Claude (ou None se erro)
        - erro: mensagem (ou None)
    """
    from redato_backend.missions.router import grade_jogo_redacao

    payload = _build_payload(cen["reescrita"], lacunas, estruturais)
    t0 = time.monotonic()
    try:
        resultado = grade_jogo_redacao(payload)
        erro = None
    except Exception as exc:  # noqa: BLE001
        resultado = None
        erro = f"{type(exc).__name__}: {exc}"
    elapsed_s = time.monotonic() - t0
    return {
        "cenario": cen, "elapsed_s": elapsed_s,
        "resultado": resultado, "erro": erro,
    }


def _print_resultado(res: Dict[str, Any]) -> None:
    cen = res["cenario"]
    _print_header(cen)
    _print_reescrita_preview(cen["reescrita"])
    if res["erro"]:
        print(f"FALHA — {res['erro']}\n")
        return
    out = res["resultado"]
    _print_notas_e_flags(out)
    _print_feedback_aluno(out)
    _print_feedback_professor_padrao(out)
    print(_BAR_THIN)
    print(f"  Latência da chamada: {res['elapsed_s']:.1f}s")


def _print_tabela_resumo(resultados: List[Dict[str, Any]]) -> None:
    """Tabela compacta no fim — nome | nota | transformação | flags.
    Daniel consegue avaliar em 1 olhada se cada cenário caiu na faixa
    esperada."""
    print()
    print(_BAR)
    print("RESUMO COMPARATIVO")
    print(_BAR)
    # Calcula larguras
    nome_w = max(len(r["cenario"]["nome"]) for r in resultados)
    nome_w = min(max(nome_w, 20), 40)
    print(
        f"  {'Cenário':<{nome_w}}  {'Nota':>4}  {'Transf.':>7}  Flags"
    )
    print(f"  {'-' * nome_w}  ----  -------  -----")
    for r in resultados:
        nome = r["cenario"]["nome"]
        if len(nome) > nome_w:
            nome = nome[: nome_w - 1] + "…"
        if r["erro"]:
            nota_str = "ERR"
            transf_str = "—"
            flags_str = r["erro"][:30]
        else:
            out = r["resultado"]
            nota_str = str(out.get("nota_total_enem", "?"))
            transf_str = str(out.get("transformacao_cartas", "?"))
            flags = out.get("flags") or {}
            flags_on = [
                k.replace("_das_cartas", "")
                .replace("_do_minideck", "")
                .replace("desrespeito_", "DH_")
                for k, v in flags.items() if v
            ]
            flags_str = ", ".join(flags_on) if flags_on else "(nenhuma)"
        print(
            f"  {nome:<{nome_w}}  {nota_str:>4}  {transf_str:>7}  {flags_str}"
        )
    print()


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

def main() -> int:
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERRO: ANTHROPIC_API_KEY não definido. Defina via env "
              "(ou .env do backend) antes de rodar.")
        return 2

    lacunas = _lacunas_minideck_saude_mental()
    estruturais = _build_estruturais()
    model = os.getenv("REDATO_MISSION_MODEL", "claude-sonnet-4-6")

    print(f"\n{_BAR}")
    print(f"INSPEÇÃO QUALITATIVA — feedback_aluno em jogo_redacao")
    print(f"{_BAR}")
    print(f"  Modelo:         {model}")
    print(f"  Cenários:       {len(CENARIOS)}")
    print(f"  Cartas comuns:  P01, R01, K01, A01, AC07, ME04, F02 "
          f"(+ 10 estruturais)")
    print(f"  Tema:           Saúde Mental")
    print(f"  Texto montado:  {len(_TEXTO_MONTADO)} chars (compartilhado)")
    print()

    t_start = time.monotonic()
    resultados: List[Dict[str, Any]] = []
    for cen in CENARIOS:
        res = _executa_cenario(cen, lacunas, estruturais)
        _print_resultado(res)
        resultados.append(res)

    t_total = time.monotonic() - t_start

    # Tabela-resumo dos 6 cenários — Daniel vê em 1 olhada se cada
    # caiu na faixa esperada (nota + transformação + flags).
    _print_tabela_resumo(resultados)

    # Sumário (totais)
    n_ok = sum(1 for r in resultados if r["erro"] is None)
    n_err = sum(1 for r in resultados if r["erro"] is not None)
    print(_BAR)
    print("TOTAIS")
    print(_BAR)
    print(f"  {n_ok}/{len(CENARIOS)} cenários executados com sucesso")
    if n_err:
        print(f"  {n_err} falharam — investigar")
    print(f"  Tempo total: {t_total:.1f}s")
    # Custo: Sonnet 4.6 ~$0.04 sem cache, ~$0.02 com cache.
    # Cache TTL=1h cobre system+catálogo a partir do 2º cenário.
    # 1ª chamada paga full + 5 com cache hit do system/catálogo.
    estimativa_full = 0.04
    estimativa_cached = 0.02
    custo_total = estimativa_full + 5 * estimativa_cached  # ~$0.14
    print(f"  Custo estimado: ~${custo_total:.2f} "
          f"(1ª chamada full + 5 com cache hit)")
    print()
    print(_BAR)
    print("Daniel: leia cada FEEDBACK_ALUNO acima. Critérios:")
    print("  ✓ Vocabulário acessível (sem 'tópico frasal', 'cadeia")
    print("    argumentativa', 'operador adversativo' etc.)")
    print("  ✓ Cita trecho específico do texto entre aspas")
    print("  ✓ Em ajustes[]: termina com COMO MELHORAR (caminho concreto)")
    print("  ✓ Tom adulto (sem diminutivos, sem 'show!', 'que legal!')")
    print()
    print("FEEDBACK_PROFESSOR (padrão de falha) deve continuar técnico —")
    print("terminologia INEP/oficina ('tese genérica', 'salto lógico').")
    print()
    print("Se algum cenário tiver feedback fora do registro, atualize")
    print("a lista de termos proibidos em FEEDBACK_ALUNO_REGISTRO_GUIDELINE")
    print("(redato_backend/missions/prompts.py) e rode novamente.")
    return 0 if n_err == 0 else 6


if __name__ == "__main__":
    sys.exit(main())
