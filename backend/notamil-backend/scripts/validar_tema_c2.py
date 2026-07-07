#!/usr/bin/env python3
"""Validação qualitativa dirigida: o tema derruba a C2 quando a redação foge?
(ADENDO §D7 — mitigação 2. PASSO OBRIGATÓRIO do runbook antes de
REDATO_B2C_ENABLED=true.)

Motivo: o teste automatizado prova só PLUMBING (o tema chega no payload
do grader). NÃO prova COMPORTAMENTO (o modelo usa o tema pra penalizar
tangenciamento). E "C2 avaliada contra o tema" é a promessa central do
B2C — foi por isso que matamos o modo LIVRE. Este script corrige a MESMA
redação com (a) tema aderente e (b) tema deliberadamente off-topic, e
imprime C1–C5 lado a lado. Se a C2 despenca no par off-topic, o produto
entrega o que promete.

NÃO é teste de pytest (LLM real é flaky e custa dinheiro por chamada).
Rodar manualmente com a chave real:

    ANTHROPIC_API_KEY=sk-... python scripts/validar_tema_c2.py

Usa o MESMO motor do B2C: grade_essay_completo(..., force_claude=True).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _carregar_env() -> None:
    """Carrega ANTHROPIC_API_KEY do backend/.env (gitignored) se não
    estiver já no ambiente. Nunca commitar a chave; o .env fica fora do
    git (ver .gitignore)."""
    env_path = BACKEND / ".env"
    if os.environ.get("ANTHROPIC_API_KEY") or not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        # `setdefault` NÃO serve: o shell pode ter a var setada como STRING
        # VAZIA (ex.: `export ANTHROPIC_API_KEY=` no profile), e setdefault
        # não sobrescreve chave existente. Sobrescrevemos quando o valor
        # atual está ausente OU vazio.
        if not os.environ.get(k):
            os.environ[k] = v


_carregar_env()


# (redação, tema_aderente, tema_off_topic)
PARES = [
    (
        "A democratização do acesso à leitura no Brasil ainda é um desafio. "
        "Bibliotecas públicas escassas e o preço elevado dos livros afastam "
        "grande parte da população do hábito de ler. Investir em bibliotecas "
        "comunitárias e em programas de distribuição de obras é essencial "
        "para formar leitores críticos e reduzir desigualdades. A escola, "
        "aliada a políticas públicas de incentivo, cumpre papel central "
        "nesse processo, garantindo que o livro chegue a quem mais precisa.",
        "Os desafios da democratização do acesso à leitura no Brasil",
        "O impacto da inteligência artificial no mercado de trabalho",
    ),
    (
        "O combate à desinformação exige responsabilidade coletiva. "
        "As redes sociais amplificam boatos em velocidade sem precedentes, "
        "colocando em risco a saúde pública e a democracia. Educação "
        "midiática nas escolas, transparência das plataformas e checagem "
        "independente formam um tripé necessário. Sem cidadãos capazes de "
        "avaliar fontes, qualquer política pública perde eficácia diante da "
        "mentira que circula livremente.",
        "Caminhos para combater a desinformação nas redes sociais",
        "A valorização das manifestações culturais nordestinas",
    ),
    (
        "A mobilidade urbana sustentável é urgente nas grandes cidades. "
        "O transporte individual motorizado congestiona vias e polui o ar, "
        "enquanto o transporte coletivo segue precário. Ampliar o metrô, "
        "criar ciclovias seguras e incentivar tarifas acessíveis muda a "
        "lógica das cidades. Planejamento urbano integrado é o que garante "
        "deslocamentos dignos e um meio ambiente mais equilibrado.",
        "Mobilidade urbana sustentável nas grandes cidades brasileiras",
        "Os efeitos do sedentarismo na saúde dos jovens",
    ),
]


def _linha_notas(res) -> str:
    n = res.notas
    return (f"total {res.nota_total:>4} | C1 {n['c1']:>3} · C2 {n['c2']:>3} · "
            f"C3 {n['c3']:>3} · C4 {n['c4']:>3} · C5 {n['c5']:>3}")


def main() -> int:
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERRO: defina ANTHROPIC_API_KEY (chave real) pra rodar.")
        return 1

    from redato_backend.b2c.correction import corrigir_texto

    print("=" * 78)
    print("VALIDAÇÃO TEMA → C2 (ADENDO §D7). Espera-se C2 MENOR no off-topic.")
    print("=" * 78)

    alertas = 0
    for i, (redacao, tema_ok, tema_off) in enumerate(PARES, 1):
        print(f"\n### Par {i}")
        print(f"  tema aderente : {tema_ok}")
        print(f"  tema off-topic: {tema_off}")
        res_ok = corrigir_texto(redacao, tema=tema_ok)
        res_off = corrigir_texto(redacao, tema=tema_off)
        print(f"  ADERENTE  → {_linha_notas(res_ok)}")
        print(f"  OFF-TOPIC → {_linha_notas(res_off)}")
        delta_c2 = res_ok.notas["c2"] - res_off.notas["c2"]
        print(f"  ΔC2 (aderente − off) = {delta_c2:+d}  "
              f"(esperado > 0: off-topic deve cair)")
        print(f"  foco off-topic: {res_off.foco_melhoria}")
        if delta_c2 <= 0:
            print("  ⚠️  ALERTA: C2 NÃO penalizou a fuga ao tema neste par.")
            alertas += 1

    print("\n" + "=" * 78)
    if alertas:
        print(f"❌ {alertas}/{len(PARES)} pares SEM penalização de C2. "
              "NÃO ligar REDATO_B2C_ENABLED — o produto não entrega a "
              "promessa 'C2 contra o tema'. Investigar o prompt do grader.")
        return 2
    print("✅ Todos os pares penalizaram a fuga ao tema na C2. Gate liberado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
