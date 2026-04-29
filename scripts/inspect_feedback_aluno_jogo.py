#!/usr/bin/env python3
"""Inspeção qualitativa do feedback_aluno do modo jogo_redacao com Claude real.

Substitui o `/tmp/inspect_jogo.py` que Daniel rodou em 2026-04-29 pra
validar a calibração do registro do feedback_aluno (commit 3812079).

Chama `grade_jogo_redacao` com a fixture do canário "caso_feliz" e
imprime saída completa em formato legível pra Daniel ler:
- Texto reescrito (input)
- feedback_aluno completo (acertos + ajustes) — alvo da calibração
- feedback_professor completo — pra confirmar que continua técnico
- Notas + transformação + sugestões
- Custo estimado da chamada

Idempotente, sem efeitos colaterais. NÃO toca DB. Não roda em CI.

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

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend" / "notamil-backend"
sys.path.insert(0, str(BACKEND))

try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]
    load_dotenv(BACKEND / ".env")
except ImportError:
    pass


# ──────────────────────────────────────────────────────────────────────
# Fixture do canário caso_feliz — bate com test_jogo_redacao_canarios.py
# ──────────────────────────────────────────────────────────────────────

Lac = namedtuple("Lac", ["codigo", "tipo", "conteudo"])
Est = namedtuple("Est", ["codigo", "secao", "cor", "texto", "lacunas"])


def _build_fixture():
    """Catálogo enxuto de Saúde Mental + cartas escolhidas + texto
    montado + reescrita autoral substancial. Suficiente pra o Claude
    avaliar e produzir feedback_aluno completo."""
    estruturais = {
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
    lacunas = {
        "P01": Lac("P01", "PROBLEMA",
                   "estigma social associado aos transtornos mentais"),
        "R01": Lac("R01", "REPERTORIO",
                   "OMS — 86% das pessoas com transtornos mentais "
                   "no Brasil não recebem tratamento"),
        "K01": Lac("K01", "PALAVRA_CHAVE",
                   "falta de investimento público em saúde mental"),
        "A01": Lac("A01", "AGENTE", "Ministério da Saúde"),
        "AC07": Lac("AC07", "ACAO", "ampliar a rede de CAPS"),
        "ME04": Lac("ME04", "MEIO", "via emendas parlamentares"),
        "F02": Lac("F02", "FIM",
                   "para garantir acesso universal a tratamento "
                   "psicológico"),
    }
    codigos_escolhidos = [
        "E01", "E10", "E17", "E19", "E21", "E33", "E35", "E37",
        "E49", "E51",
        "P01", "R01", "K01", "A01", "AC07", "ME04", "F02",
    ]
    texto_montado = (
        "No Brasil, estigma social associado aos transtornos mentais "
        "persiste como questão central. Conforme OMS — 86% das "
        "pessoas com transtornos mentais no Brasil não recebem "
        "tratamento, demanda atenção urgente.\n\n"
        "Cenário impulsionado por falta de investimento público em "
        "saúde mental.\n\n"
        "Em primeira análise, estigma social associado aos transtornos "
        "mentais liga-se a falta de investimento público em saúde "
        "mental.\n\n"
        "Tal realidade é agravada por falta de investimento público "
        "em saúde mental.\n\n"
        "Comprovado por OMS — 86% das pessoas com transtornos mentais "
        "no Brasil não recebem tratamento.\n\n"
        "Outro fator: falta de investimento público em saúde mental "
        "amplia estigma social associado aos transtornos mentais.\n\n"
        "Há prejuízos para falta de investimento público em saúde "
        "mental.\n\n"
        "Análise encontra respaldo em OMS — 86% das pessoas com "
        "transtornos mentais no Brasil não recebem tratamento.\n\n"
        "Evidencia-se que estigma social associado aos transtornos "
        "mentais exige ampliar a rede de CAPS via emendas "
        "parlamentares.\n\n"
        "Ministério da Saúde tem como prioridade ampliar a rede de "
        "CAPS via emendas parlamentares."
    )
    reescrita = (
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
    return {
        "tema_minideck": "saude_mental",
        "nome_humano_tema": "Saúde Mental",
        "cartas_lacuna_full": list(lacunas.values()),
        "codigos_escolhidos": codigos_escolhidos,
        "estruturais_por_codigo": estruturais,
        "lacunas_por_codigo": lacunas,
        "texto_montado": texto_montado,
        "reescrita_texto": reescrita,
    }


# ──────────────────────────────────────────────────────────────────────
# Render
# ──────────────────────────────────────────────────────────────────────

def _section(title: str) -> str:
    bar = "═" * (len(title) + 4)
    return f"\n{bar}\n  {title}\n{bar}\n"


def _print_lista(items, prefix="• "):
    for item in items or []:
        print(f"  {prefix}{item}")


def _print_feedback_aluno(fa: dict) -> None:
    print(_section("FEEDBACK_ALUNO (alvo da calibração)"))
    print("\n  Acertos:")
    _print_lista(fa.get("acertos") or [])
    print("\n  Ajustes:")
    _print_lista(fa.get("ajustes") or [])


def _print_feedback_professor(fp: dict) -> None:
    print(_section("FEEDBACK_PROFESSOR (continua técnico)"))
    print("\n  Pontos fortes:")
    _print_lista(fp.get("pontos_fortes") or [])
    print("\n  Pontos fracos:")
    _print_lista(fp.get("pontos_fracos") or [])
    print(f"\n  Padrão de falha: {fp.get('padrao_falha', '')}")
    print(f"\n  Transferência: {fp.get('transferencia_competencia', '')}")


def _print_resumo_quantitativo(out: dict) -> None:
    print(_section("Notas + métricas"))
    notas = out.get("notas_enem", {}) or {}
    total = out.get("nota_total_enem", "?")
    transf = out.get("transformacao_cartas", "?")
    inline = " · ".join(
        f"{k.upper()} {notas.get(k, 0)}"
        for k in ("c1", "c2", "c3", "c4", "c5")
    )
    print(f"  Nota total:           {total}/1000")
    print(f"  Por competência:      {inline}")
    print(f"  Transformação cartas: {transf}/100")
    flags = out.get("flags") or {}
    flags_on = [k for k, v in flags.items() if v]
    if flags_on:
        print(f"  Flags ativadas:       {', '.join(flags_on)}")
    sugestoes = out.get("sugestoes_cartas_alternativas") or []
    if sugestoes:
        print(f"\n  Sugestões de cartas alternativas ({len(sugestoes)}):")
        for s in sugestoes:
            print(
                f"    {s.get('codigo_original')} → "
                f"{s.get('codigo_sugerido')}: {s.get('motivo')}"
            )


def _print_custo(elapsed_s: float, model: str) -> None:
    print(_section("Custo estimado"))
    # Estimativa baseada nos custos do Sonnet 4.6: $3/MTok input,
    # $15/MTok output. Tamanho real depende do prompt — usamos
    # ordem de grandeza histórica (~5K input + 1.5K output).
    input_tokens = 5500    # system + catálogo + cartas + texto + reescrita + guideline
    output_tokens = 1800   # tool_args
    cost_in = (input_tokens / 1_000_000) * 3.00
    cost_out = (output_tokens / 1_000_000) * 15.00
    total = cost_in + cost_out
    cached_in = (input_tokens / 1_000_000) * 0.30
    total_cached = cached_in + cost_out
    print(f"  Modelo:                  {model}")
    print(f"  Latência real:           {elapsed_s:.1f}s")
    print(f"  Tokens input estimados:  ~{input_tokens}")
    print(f"  Tokens output estimados: ~{output_tokens}")
    print(f"  Custo SEM cache:         ~${total:.4f}")
    print(f"  Custo COM cache (1h):    ~${total_cached:.4f}")


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

def main() -> int:
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERRO: ANTHROPIC_API_KEY não definido. Defina via env "
              "(ou .env do backend) antes de rodar.")
        return 2

    fixture = _build_fixture()

    print(_section("INPUT — Reescrita do aluno"))
    print(fixture["reescrita_texto"])

    print(_section("INPUT — Cartas escolhidas pelo grupo"))
    print(", ".join(fixture["codigos_escolhidos"]))

    print(_section("Chamando Claude (jogo_redacao)..."))
    from redato_backend.missions.router import grade_jogo_redacao
    model = os.getenv("REDATO_MISSION_MODEL", "claude-sonnet-4-6")
    print(f"  Modelo: {model}")

    t0 = time.monotonic()
    try:
        out = grade_jogo_redacao(fixture)
    except Exception as exc:  # noqa: BLE001
        print(f"\nFALHA: {type(exc).__name__}: {exc}")
        return 3
    elapsed_s = time.monotonic() - t0

    _print_resumo_quantitativo(out)
    _print_feedback_aluno(out.get("feedback_aluno") or {})
    _print_feedback_professor(out.get("feedback_professor") or {})
    _print_custo(elapsed_s, model)

    print()
    print("─" * 60)
    print("Daniel: leia o FEEDBACK_ALUNO acima. Espera-se vocabulário")
    print("acessível, com trecho específico do texto + caminho concreto")
    print("pra melhorar. Termos como 'tópico frasal', 'cadeia argumentativa',")
    print("'operador adversativo' NÃO devem aparecer. Se aparecer, a")
    print("guideline está sendo ignorada — investigar.")
    print()
    print("FEEDBACK_PROFESSOR pode (e deve) usar termos técnicos —")
    print("é referência interna pra planejar próxima aula.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
