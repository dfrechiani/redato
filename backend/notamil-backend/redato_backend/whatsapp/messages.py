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

MSG_TURMA_ATIVA_CONFIRMADA = (
    "Turma escolhida: *{turma_codigo}* — *{escola_nome}*. "
    "Vou usar ela pelas próximas {ttl_horas}h. "
    "Pra mudar, manda *trocar turma*."
)

MSG_FOTO_DURANTE_ESCOLHA = (
    "Vi sua foto, mas antes preciso saber: de qual turma é? "
    "Responde com o número:\n\n{lista_turmas}"
)

MSG_TROCAR_TURMA_INICIO = (
    "Beleza, vamos trocar de turma. De qual turma você quer atender "
    "agora?\n\n{lista_turmas}\n\nResponde com o número."
)

MSG_TROCAR_TURMA_UNICA = (
    "Você só tem 1 turma ativa: *{turma_codigo}* — *{escola_nome}*. "
    "Não tem como trocar."
)


# ──────────────────────────────────────────────────────────────────────
# M10 — Dashboard professor via WhatsApp (PROMPT 1/2 — LGPD)
# ──────────────────────────────────────────────────────────────────────

# Aviso LGPD enviado na 1ª mensagem do professor após ele vincular
# telefone no portal. Bot persiste estado AGUARDANDO_LGPD_ACEITE_PROFESSOR
# e bloqueia respostas com dados até receber "sim".
AVISO_LGPD_PROFESSOR = (
    "Olá *{nome}*! Você está acessando o dashboard do Redato via "
    "WhatsApp.\n\n"
    "Aqui você poderá consultar dados das suas turmas — médias, "
    "histórico de alunos, status de atividades.\n\n"
    "⚠️ *AVISO LGPD:*\n"
    "Esses dados incluem nome de alunos, notas e trechos de redações. "
    "São dados pessoais com finalidade pedagógica. Não compartilhe "
    "prints, conversas ou dados com terceiros.\n\n"
    "Use apenas no seu celular pessoal. Se concordar, responda *sim*."
)

# Resposta quando aluno digita algo que não é "sim" / "não" durante
# AGUARDANDO_LGPD_ACEITE_PROFESSOR.
MSG_LGPD_REPETIR_PEDIDO = (
    "Pra usar o dashboard, preciso da sua confirmação.\n\n"
    "Responde *sim* se concordou com o aviso, ou *não* pra "
    "desvincular o telefone."
)

# Resposta quando professor responde "não" ao LGPD. Limpa o telefone
# do banco e retorna READY.
MSG_LGPD_NEGADO = (
    "Tudo bem. Seu telefone foi desvinculado da conta. Se quiser "
    "usar no futuro, vincule novamente em *Perfil* no portal."
)

# Placeholder enquanto PROMPT 2 não implementa os comandos
# (/turma, /aluno, /atividade). Aviso curto pro professor saber
# que vinculou OK mas dashboard ainda está em build.
MSG_DASHBOARD_PLACEHOLDER = (
    "Olá *{nome}*! Dashboard via WhatsApp está em construção.\n\n"
    "Em breve você poderá usar comandos como `/turma 1A` pra ver "
    "resumo da turma, `/aluno <nome>` pra histórico, e `/atividade` "
    "pra status. Aguarde."
)


# ──────────────────────────────────────────────────────────────────────
# M10 PROMPT 2 — Comandos do dashboard professor via WhatsApp
# ──────────────────────────────────────────────────────────────────────
#
# Substitui MSG_DASHBOARD_PLACEHOLDER pelos 4 comandos: /turma,
# /aluno, /atividade, /ajuda. Mensagens curtas (cabem em 1500 chars
# por chunk Twilio); detalhamento fica no portal.

MSG_DASHBOARD_AJUDA = (
    "📚 *Comandos do dashboard*\n\n"
    "*/turma <codigo>*\n"
    "  Resumo da turma. Ex: /turma 1A\n\n"
    "*/aluno <nome>*\n"
    "  Histórico do aluno. Ex: /aluno maria\n"
    "  Aceita nome parcial — mostra lista se houver duplicados.\n\n"
    "*/atividade <codigo>*\n"
    "  Status de uma atividade. Ex: /atividade OF14\n\n"
    "*/ajuda*\n"
    "  Mostra essa mensagem.\n\n"
    "⚠️ Os dados aqui são pra uso pedagógico exclusivo. Não "
    "compartilhe com terceiros."
)

MSG_DASHBOARD_USO_TURMA = (
    "Falta o código da turma.\n"
    "Use: */turma <codigo>* (ex: /turma 1A)"
)

MSG_DASHBOARD_USO_ALUNO = (
    "Falta o nome do aluno.\n"
    "Use: */aluno <nome>* (ex: /aluno maria)"
)

MSG_DASHBOARD_USO_ATIVIDADE = (
    "Falta o código da atividade.\n"
    "Use: */atividade <codigo>* (ex: /atividade OF14)"
)

MSG_TURMA_NAO_ENCONTRADA = (
    "Turma *{codigo}* não encontrada na sua escola.\n\n"
    "Confere o código e tenta de novo."
)

MSG_ALUNO_NAO_ENCONTRADO = (
    "Nenhum aluno encontrado com *{nome}* na sua escola.\n\n"
    "Confere o nome e tenta de novo."
)

MSG_ALUNO_MULTIPLOS_MATCHES = (
    "Encontrei mais de 1 aluno com *{nome}*:\n\n"
    "{lista}\n\n"
    "Responde o *número* (1, 2, ...) pra escolher, ou *cancelar*."
)

MSG_ATIVIDADE_NAO_ENCONTRADA = (
    "Atividade *{codigo}* não encontrada na sua escola.\n\n"
    "Confere o código (ex: OF14) e tenta de novo."
)

MSG_ATIVIDADE_MULTIPLOS_MATCHES = (
    "Encontrei mais de 1 atividade com *{codigo}*:\n\n"
    "{lista}\n\n"
    "Responde o *número* (1, 2, ...) pra escolher, ou *cancelar*."
)

MSG_DASHBOARD_ESCOLHA_INVALIDA = (
    "Não entendi. Responde o *número* (1, 2, ...) pra escolher, "
    "ou *cancelar* pra sair da escolha."
)

MSG_DASHBOARD_ESCOLHA_CANCELADA = (
    "Cancelei. Manda */ajuda* pra ver os comandos disponíveis."
)

MSG_DASHBOARD_DB_INDISPONIVEL = (
    "Não consegui acessar os dados agora. Tenta de novo em alguns "
    "segundos. Se persistir, fala com a coordenação."
)

MSG_DASHBOARD_ERRO_GENERICO = (
    "Tive um problema ao montar a resposta. Tenta de novo. Se "
    "persistir, fala com a coordenação."
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
# Erros gerais e mensagens dinâmicas (M9.2 — listas calculadas no
# runtime a partir das atividades ativas das turmas do aluno).
# ──────────────────────────────────────────────────────────────────────

MSG_MISSAO_INVALIDA = (
    "Não reconheci esse código. Se quiser, manda o código completo "
    "no formato `RJ{N}·OF{NN}·MF` (ex.: RJ2·OF04·MF) ou "
    "*cancelar* pra recomeçar."
)

MSG_FALTA_FOTO = (
    "Anotei: missão *{missao}*. Agora manda a foto da redação."
)

# Versão dinâmica: lista de oficina_numero das atividades ativas do
# aluno. Ex.: "1, 4, 6 ou 7" pra 2S; "10 ou 11" pra 1A com 2 ativas.
MSG_FALTA_MISSAO_DINAMICO = (
    "Recebi a foto, mas não sei qual missão é. Me manda o número da "
    "missão: *{numeros}*."
)

# Quando aluno não tem nenhuma atividade ativa nas turmas dele.
# Pode ser intervalo entre missões — pede pra mandar código completo.
MSG_FALTA_MISSAO_SEM_ATIVAS = (
    "Recebi a foto, mas não há missão aberta na sua turma agora. "
    "Se sua professora já disponibilizou uma, manda o código completo "
    "(ex.: RJ2·OF04·MF) junto. Senão, espera ela abrir a atividade."
)

# Aluno em múltiplas turmas mandou número que casa com >1 atividade
# (ex.: OF12 da 1S e OF12 da 2S). Pede código completo pra desambiguar.
MSG_AMBIGUO_PEDE_COMPLETO = (
    "Achei mais de uma missão *{numero}* nas suas turmas:\n\n{lista}\n\n"
    "Manda o código completo pra eu saber qual é (ex.: RJ2·OF12·MF)."
)

# Comando "cancelar/resetar/sair" volta pra READY a partir de qualquer
# estado pós-cadastro.
MSG_CANCELADO = (
    "OK, voltei ao estado inicial. Manda a foto da redação quando "
    "estiver pronto, ou mande o código da missão (ex.: RJ2·OF04·MF)."
)

# Aliases legados (testes antigos podem importar). Mantidos por
# retrocompat — não usar em código novo.
MSG_FALTA_MISSAO = MSG_FALTA_MISSAO_SEM_ATIVAS

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
    "Pra eu corrigir uma redação, manda a *foto da página do livro*. "
    "Eu identifico a missão pela atividade aberta na sua turma. Se "
    "tiver mais de uma aberta, pergunto."
)
