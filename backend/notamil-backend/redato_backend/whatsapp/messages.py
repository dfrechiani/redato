"""Mensagens centralizadas do bot (M4).

Princípios:
- Tom de "professora explicando regra": claro, firme, sem sermão.
- Sem emoji excessivo. Pode ter no máximo 1 por mensagem (e só se
  ajudar comprehensão — *não* como decoração).
- Vocativo direto: "você", não "vocês" ou voz passiva culta.
- Evitar "infelizmente", "lamentamos", apelos emocionais. Foco no
  próximo passo concreto pro aluno.

Mensagens **legadas** (NEW/AWAITING_NOME/AWAITING_TURMA do fluxo livre
da Fase A) ficam neste arquivo por organização, mas **não são usadas
em produção pós-M4** — o fluxo livre foi descontinuado. Mantidas pra
compatibilidade com testes que ainda referenciam.
"""
from __future__ import annotations

# ──────────────────────────────────────────────────────────────────────
# Cadastro do aluno (fluxo M4)
# ──────────────────────────────────────────────────────────────────────

MSG_BEM_VINDO_NOVO_ALUNO = (
    "Olá! Eu sou a *Redato*, corretora do Projeto ATO. Pra começar, "
    "preciso vincular você à sua turma.\n\n"
    "Manda o *código da turma* que sua professora compartilhou. "
    "O código tem o formato `TURMA-XXXXX-1A-2026`."
)

MSG_PEDE_NOME_ALUNO = (
    "Achei sua turma: *{turma_codigo}* da *{escola_nome}*.\n\n"
    "Pra finalizar o cadastro, manda seu *nome completo*."
)

MSG_CADASTRO_COMPLETO = (
    "Pronto, {primeiro_nome}. Você está vinculado à turma "
    "*{turma_codigo}* da *{escola_nome}*.\n\n"
    "Quando a professora abrir uma missão, fotografa a redação e "
    "manda aqui com o código da missão (ex.: RJ1OF10MF)."
)

MSG_CODIGO_TURMA_INVALIDO = (
    "Não encontrei essa turma. Confere com sua professora se o código "
    "está correto. O formato é `TURMA-XXXXX-1A-2026`."
)

MSG_TURMA_INATIVA = (
    "Essa turma não está mais ativa. Fala com sua professora ou "
    "coordenação."
)

MSG_JA_CADASTRADO_NESSA_TURMA = (
    "Você já está cadastrado nesta turma como *{nome}*. Não precisa "
    "se cadastrar de novo."
)


# ──────────────────────────────────────────────────────────────────────
# Envio de foto / atividade
# ──────────────────────────────────────────────────────────────────────

MSG_ALUNO_NAO_CADASTRADO = (
    "Você ainda não está em nenhuma turma. Pede o *código da turma* "
    "pra sua professora — ele tem o formato `TURMA-XXXXX-1A-2026`. "
    "Manda o código aqui pra eu te cadastrar."
)

MSG_SEM_ATIVIDADE_ATIVA = (
    "Não há missão *{codigo}* aberta na sua turma agora. Verifica "
    "com sua professora se a atividade já foi disponibilizada."
)

MSG_ATIVIDADE_AGENDADA = (
    "A missão *{codigo}* foi agendada mas ainda não começou. Ela "
    "abre em {data_inicio_pt}."
)

MSG_ATIVIDADE_ENCERRADA = (
    "A missão *{codigo}* já encerrou em {data_fim_pt}. Não dá mais "
    "pra enviar redação dessa atividade."
)

MSG_ESCOLHE_TURMA = (
    "Você está vinculado a {n_turmas} turmas. De qual turma é essa "
    "redação?\n\n{lista_turmas}\n\nResponde com o número."
)

MSG_TURMA_ESCOLHA_INVALIDA = (
    "Não entendi. Responde com o número da turma (1, 2, ...)."
)


# ──────────────────────────────────────────────────────────────────────
# Reenvio de foto duplicada (continuidade do fluxo de M3)
# ──────────────────────────────────────────────────────────────────────

MSG_DUPLICATE_PROMPT = (
    "Recebi essa mesma redação em {data}. O que você quer?\n\n"
    "1\ufe0f\u20e3 Reenviar o feedback que já te dei\n"
    "2\ufe0f\u20e3 Reavaliar como nova tentativa (a IA pode dar outra nota)\n\n"
    "Responde *1* ou *2*."
)

MSG_DUPLICATE_INVALID_CHOICE = (
    "Não entendi. Responde só *1* (reenviar feedback antigo) ou *2* "
    "(reavaliar como nova tentativa)."
)


# ──────────────────────────────────────────────────────────────────────
# OCR errado / qualidade
# ──────────────────────────────────────────────────────────────────────

MSG_OCR_ERRADO_CONFIRMADO = (
    "Ok, vou descartar a última correção. Manda a foto de novo. "
    "Procure boa luz e foto sem inclinação."
)

MSG_OCR_ERRADO_SEM_HISTORICO = (
    "Não tenho correção recente sua pra descartar. Se a Redato leu "
    "errado depois de avaliar, manda a foto de novo com o código da "
    "missão."
)


# ──────────────────────────────────────────────────────────────────────
# Erros gerais
# ──────────────────────────────────────────────────────────────────────

MSG_MISSAO_INVALIDA = (
    "Não reconheci esse código. Manda só o número da missão: "
    "*10*, *11*, *12*, *13* ou *14*."
)

MSG_FALTA_FOTO = (
    "Anotei: missão *{missao}*. Agora manda a foto da redação."
)

MSG_FALTA_MISSAO = (
    "Recebi a foto, mas não sei qual missão é. Me manda o número da "
    "missão: *10*, *11*, *12*, *13* ou *14*."
)

MSG_ERRO_GENERICO = (
    "Algo deu errado na correção. Pode tentar de novo? Se persistir, "
    "fala com seu professor."
)


# ──────────────────────────────────────────────────────────────────────
# Notificação automática (endpoint /portal/atividades/{id}/notificar)
# ──────────────────────────────────────────────────────────────────────

MSG_NOTIFICACAO_NOVA_ATIVIDADE = (
    "Oi, {primeiro_nome}! Sua professora *{nome_prof}* disponibilizou "
    "uma nova missão:\n\n"
    "*{missao_titulo}* — código *{missao_codigo}*\n"
    "Prazo: até {data_fim_pt}\n\n"
    "Quando estiver pronto, fotografa a redação e manda aqui com o "
    "código da missão."
)


# ──────────────────────────────────────────────────────────────────────
# Mensagens legadas (não usadas pós-M4 — preservadas pra testes antigos)
# ──────────────────────────────────────────────────────────────────────

MSG_BOAS_VINDAS = MSG_BEM_VINDO_NOVO_ALUNO  # alias backcompat

MSG_PEDE_TURMA = (
    "Prazer, {nome}. Agora me diz sua *turma* e *escola* numa mensagem só.\n\n"
    "Exemplo: _1A — Colégio Estadual Rui Barbosa_"
)

MSG_CADASTRADO = (
    "Beleza, {nome}! Cadastro feito.\n\n"
    "Pra eu corrigir uma redação, manda a *foto da página do livro* + "
    "o *número da missão* (10, 11, 12, 13 ou 14). Pode mandar tudo na "
    "mesma mensagem ou em mensagens separadas."
)
