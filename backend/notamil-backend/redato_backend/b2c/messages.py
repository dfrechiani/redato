"""Copies do bot B2C (M0–M15 + foto ilegível). SPEC_B2C_REDATO.md §6.

Placeholders `{{...}}` do spec viram `{...}` de str.format aqui. NENHUMA
mensagem exibe % de share nem termos comerciais internos (D4, critério
de aceite #9) — o preço em reais aparece, o percentual do parceiro
JAMAIS.

`nome_publico`, `nome_professor`, emoji e assinatura vêm do branding do
parceiro (D6). A função `assinar` aplica a assinatura opcional ao fim.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


# ──────────────────────────────────────────────────────────────────────
# Onboarding / degustação (F1–F2)
# ──────────────────────────────────────────────────────────────────────

M0_SEM_CODIGO = (
    "Oi! 👋 Aqui é a correção de redação por WhatsApp. Você chegou pelo "
    "link de qual professor(a)? Me manda o código que aparece na bio "
    "dele(a) (ex.: LUMA) que eu te coloco na turma certa."
)

M1_BOAS_VINDAS = (
    "Bem-vindo(a) à *{nome_publico}*! ✍️ Aqui você manda a FOTO da sua "
    "redação manuscrita e recebe em minutos a correção nas 5 "
    "competências do ENEM, no padrão do(a) prof. {nome_professor}. "
    "Antes de começar: seus textos e dados são usados só para a sua "
    "correção e evolução (política: {link_politica}). Ao continuar, "
    "você concorda. Como você se chama?"
)

M2_CONVITE_GRATIS = (
    "Prazer, {nome}! 🎁 Sua primeira correção é por nossa conta. "
    "Fotografa sua redação (folha inteira, boa luz) e manda aqui "
    "*com o tema na legenda da foto*."
)

M_PEDE_CPF = (
    "Pra gerar sua assinatura preciso do seu *CPF* (só números). "
    "Ele é usado apenas pra emissão da cobrança."
)

M_CPF_INVALIDO = (
    "Esse CPF não parece válido 🤔 Manda os 11 números do seu CPF, "
    "por favor."
)

M3_ENTREGA_DEGUSTACAO = (
    "📝 Tema: {tema}\n"
    "✅ Correção pronta! Nota: *{nota_total}/1000* — C1 {c1} · C2 {c2} · "
    "C3 {c3} · C4 {c4} · C5 {c5}. 💪 Destaque: {ponto_forte}. 🎯 Para "
    "subir: {foco_melhoria}. Essa foi sua correção gratuita da "
    "{nome_publico}!"
)

M4_PAYWALL = (
    "Quer treinar TODOS os dias até o ENEM? A assinatura {nome_publico} "
    "te dá correção ilimitada, em minutos, aqui no WhatsApp, por "
    "R$ {preco}/mês. 👉 {link_checkout} (cancela quando quiser)"
)

# ──────────────────────────────────────────────────────────────────────
# Assinante (F3–F5)
# ──────────────────────────────────────────────────────────────────────

M5_LIBERADO = (
    "🎉 Assinatura ativa! Pode mandar redação sem limite, {nome}. Dica: "
    "escreve → recebe o diagnóstico → reescreve em cima do erro → manda "
    "de novo. É assim que se chega no 900+."
)

# M6 (rev.): abre com o tema; bloco de evolução é CONDICIONAL (só com
# ≥2 corrigidos no histórico — §9.2). O router compõe base + (evolução) +
# fecho.
M6_BASE = (
    "📝 Tema: {tema}\n"
    "✅ *{nota_total}/1000* — C1 {c1} · C2 {c2} · C3 {c3} · C4 {c4} · "
    "C5 {c5}. 💪 {ponto_forte}. 🎯 {foco_melhoria}."
)
M6_EVOLUCAO_LINE = " 📈 Sua evolução: {ultimas_notas}."
M6_FECHO = " Manda a próxima quando quiser!"

# Aviso pedagógico de fuga ao tema (backlog B2C). Quando o motor zera a C2
# por fuga TOTAL ao tema, o B2C — ao contrário do ENEM oficial, que ANULA a
# redação (zero global) — pontua ~400 e entrega diagnóstico, porque nota zero
# seca não ensina e C2 zerada + diagnóstico ensina. Esta linha torna a
# divergência EXPLÍCITA (o público conhece a regra "padrão ENEM"), virando
# feature pedagógica em vez de divergência silenciosa do INEP. O router anexa
# a M3/M6 via `alerta_fuga_tema`. NÃO mexe no motor nem no prompt do grader.
M_ALERTA_FUGA_TEMA = (
    " ⚠️ No ENEM oficial, fugir do tema anula a redação inteira (zero). "
    "Aqui a gente pontua e mostra onde melhorar pra você treinar."
)

M7_FAIR_USE = (
    "Você treinou MUITO hoje ({n} redações!) 🔥 Pra correção manter a "
    "qualidade, seguimos amanhã. Que tal reescrever a de hoje aplicando "
    "o diagnóstico?"
)

# ──────────────────────────────────────────────────────────────────────
# Inadimplência / cancelamento (F6–F7)
# ──────────────────────────────────────────────────────────────────────

M8_OVERDUE_D0 = (
    "Oi {nome}! Não conseguimos renovar sua assinatura {nome_publico}. "
    "Pra não parar seu treino: {link_fatura}"
)

M9_OVERDUE_D3 = (
    "Seu acesso vence em 2 dias, {nome}. Renova aqui pra não perder o "
    "ritmo (e o histórico da sua evolução): {link_fatura}"
)

# M10 (rev. §D10): copy honesta — sem prometer fila de correção. Regularizou,
# reenvia a foto, corrige na hora.
M10_BLOQUEADO = (
    "Recebi sua redação! 📥 Pra eu corrigir, regulariza sua assinatura "
    "aqui: {link_fatura}. Assim que ativar, me manda a foto de novo que a "
    "correção sai na hora."
)

M11_CANCELAR = (
    "Sem problema, {nome}. Confirma o cancelamento respondendo SIM. Seu "
    "acesso continua até {fim_ciclo} e seu histórico fica guardado se "
    "voltar. 💙"
)

# ──────────────────────────────────────────────────────────────────────
# Comandos (F8)
# ──────────────────────────────────────────────────────────────────────

M12_EVOLUCAO = (
    "📈 Suas últimas notas: {lista}. Média C1–C5: {medias}. Competência "
    "pra focar: {pior_comp}."
)

M13_AJUDA = (
    "Comandos: manda uma FOTO da redação *com o tema na legenda* pra "
    "corrigir · 'evolução' pra ver seu histórico · 'tema' pra receber uma "
    "proposta de treino · 'cancelar' pra encerrar."
)

M14_TEMA = (
    "🎯 Tema de treino: '{tema}'. 30 linhas, caneta preta, e me manda a "
    "foto *com o tema na legenda* ao terminar. Bora!"
)

# ── Resolução do tema (D7 §1) ──────────────────────────────────────────

M16_PEDE_TEMA = (
    "Recebi sua redação! ✍️ Sobre qual tema você escreveu? Me manda o "
    "enunciado que a correção sai em seguida."
)

M16A_ATALHO_SORTEADO = (
    "Recebi sua redação! Foi sobre o tema que te mandei — "
    "'{ultimo_tema}'? Responde SIM ou me manda o enunciado certo."
)

M16B_CONFIRMA_LEGENDA = (
    "Recebi! Só confirmando: o tema é '{caption}'? Responde SIM ou me "
    "manda o enunciado completo."
)

M17_ANTI_LOOP = (
    "Me manda o enunciado completo do tema, vai ser rapidinho 🙂"
)

M15_FALLBACK = (
    "Não entendi 🤔 Manda uma FOTO da redação pra eu corrigir, ou "
    "'ajuda' pra ver o que sei fazer."
)

M_FOTO_ILEGIVEL = (
    "Não consegui ler bem sua letra nessa foto 😅 Tenta de novo: folha "
    "inteira no quadro, luz de frente, sem sombra. Se preferir, digita "
    "o texto."
)


# ──────────────────────────────────────────────────────────────────────
# Branding helpers
# ──────────────────────────────────────────────────────────────────────

def alerta_fuga_tema(notas: Dict[str, Any]) -> str:
    """Linha de aviso de fuga ao tema, ou "" se não houver fuga.

    Sinal: C2 == 0. O motor deriva a C2 CONTRA o tema (ADENDO §D7) e a zera
    na fuga total — mesmo comportamento que o gate `validar_tema_c2.py`
    exige. Pura: só olha as notas, não toca no motor."""
    return M_ALERTA_FUGA_TEMA if notas.get("c2") == 0 else ""


def assinar(texto: str, branding: Optional[Dict[str, Any]]) -> str:
    """Aplica a assinatura do parceiro ao fim da mensagem, se houver.

    branding = {"saudacao","emoji","assinatura","cor"}. Só a assinatura
    é anexada; saudacao/emoji são usados nas copies via placeholders.
    NUNCA anexa share_pct — branding não carrega dado comercial."""
    if not branding:
        return texto
    assinatura = (branding.get("assinatura") or "").strip()
    if not assinatura:
        return texto
    return f"{texto}\n\n_{assinatura}_"
