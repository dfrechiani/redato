# Oficinas da 3ª série — status de integração

**Data:** 2026-05-02
**Migration:** `j0a1b2c3d4e5_seed_missoes_3s` (após `i0a1b2c3d4e5_professor_telefone`)
**Router:** `redato_backend/missions/router.py:_MISSAO_TO_MODE`

## TL;DR

Conteúdo pedagógico: 15 oficinas no livro `LIVRO_ATO_3S_v8_PROF.html`.
Integração no Redato: **11 ativas, 4 pendentes**.

| OF | Título | Modo | Status |
|---|---|---|---|
| OF01 | Redato — seu corretor de bolso | completo_parcial | ✅ ativa |
| **OF02** | **Conectivos + Coesão** | — | ⏳ pendente (chat-only) |
| OF03 | Dossiê: Repertório + Análise | foco_c2 | ✅ ativa |
| OF04 | Dossiê: Tema + Problemática | foco_c2 | ✅ ativa |
| OF05 | Dossiê: Agentes + Proposta | foco_c5 | ✅ ativa |
| OF06 | Dossiê: Proposta Completa | foco_c5 | ✅ ativa |
| OF07 | Jogo do Corretor | completo_parcial | ✅ ativa |
| **OF08** | **Análise de Erros Comuns** | foco_c1 | ⏳ pendente (modo adiado) |
| OF09 | Simulado 1 | completo (FT) | ✅ ativa |
| OF10 | Revisão Cooperativa | completo_parcial | ✅ ativa |
| OF11 | Simulado 2 + IA | completo (FT) | ✅ ativa |
| **OF12** | **Jogo de Redação Completo** | — | ⏳ pendente (cartas 3S) |
| **OF13** | **Jogo de Redação Completo** | — | ⏳ pendente (cartas 3S) |
| OF14 | Simulado Final 1 | completo (FT) | ✅ ativa |
| OF15 | Simulado Final 2 + Fechamento | completo (FT) | ✅ ativa |

## Pendências detalhadas

### OF02 Conectivos + Coesão

Oficina é fluxo de **chat exploratório** sobre conectivos — não tem
produção de redação avaliável pelo Redato. Não cabe nas rubricas
atuais (foco_c1..c5, completo_parcial, completo).

**Decisão:** não cadastrar agora. Possíveis caminhos futuros:
- Modo novo `chat_explorativo` se Redato passar a guiar conversas
  pedagógicas (mudança grande de arquitetura)
- Material físico/PDF acompanhando a oficina, sem Redato
- Mover atividade pra outra plataforma de chat sem corretor

### OF08 Análise de Erros Comuns

Oficina pediria **`foco_c1`** (avaliação de norma culta). O modo está
**adiado** em código por decisão Daniel 2026-04-28 — comentário em
[`router.py:41-43`](../../backend/notamil-backend/redato_backend/missions/router.py)
e [`schemas.py:932-936`](../../backend/notamil-backend/redato_backend/missions/schemas.py).

**Pra ativar foco_c1, fazer (sessão dedicada):**
1. Adicionar `FOCO_C1 = "foco_c1"` no enum `MissionMode`
2. Implementar `FOCO_C1_TOOL` em `missions/schemas.py` (rubrica REJ
   pra C1 — proposta em `docs/redato/v3/proposta_flags_foco_c1_c2.md`)
3. Adicionar entrada em `_DEFAULT_MODEL_BY_MODE` (sonnet-4-6 igual
   outros foco)
4. Branch em `scoring.apply_override` (override determinístico de
   nota ENEM — `scoring.py`)
5. Mapear `RJ3_OF08_MF: MissionMode.FOCO_C1` em `_MISSAO_TO_MODE`
6. Adicionar OF08 no seed (migration nova OU edit do
   `_MISSOES_3S` em `j0a1b2c3d4e5_seed_missoes_3s.py`)

### OF12, OF13 Jogos de Redação Completo (3S)

Oficinas usam **sistema de cartas argumentativas diferente** do 1S:

- **Sistema 1S** (já implementado, ativo em `RJ1·OF14·MF`): cartas
  com classes gramaticais (E01-E63 estruturais + lacunas P/R/K/A/AC/ME/F).
  Catálogo em
  [`portal/models.py`](../../backend/notamil-backend/redato_backend/portal/models.py)
  + [`whatsapp/jogo_partida.py`](../../backend/notamil-backend/redato_backend/whatsapp/jogo_partida.py).

- **Sistema 3S** (não implementado): cartas argumentativas com slots
  **A** (Agente), **AÇ** (Ação), **ME** (Meio), **F** (Finalidade)
  + cartas E01-E64 representando peças do raciocínio. Catálogo
  pedagógico no livro `LIVRO_ATO_3S_v8_PROF.html` mas não modelado
  no banco nem no parser.

**Pra ativar OF12/OF13 (sessão dedicada):**
1. Modelar `cartas_argumentativas_3s` (tabela nova, schema diferente
   das `cartas_estruturais` 1S)
2. Modelar `minidecks_3s` com cartas argumentativas
3. Seed das ~64 cartas argumentativas + ~7 minidecks temáticos
4. Parser equivalente a `validar_partida` mas pra slots A/AÇ/ME/F
5. Sub-estado FSM no bot (`AGUARDANDO_CARTAS_3S` etc.)
6. Adicionar OF12/OF13 no seed migration + router

Ordem de magnitude: 1-2 semanas de trabalho focado, similar ao
sistema 1S do commit `h0a1b2c3d4e5_jogo_redacao_em_jogo`.

## Pra rodar a migration em prod

Antes do deploy do código que mapeia as 11 oficinas no router:

```bash
# Shell do Railway (serviço backend)
cd backend/notamil-backend/redato_backend/portal
alembic upgrade head
```

Sem migration, professor que criar atividade `RJ3·OF09·MF` no portal
vai pegar `IntegrityError` (FK `atividades.missao_id` aponta pra row
inexistente). Após migration, fluxo segue normal — `_MISSAO_TO_MODE`
no código já cobre os 11 casos.

## Outras pendências relacionadas (não-3S)

### Wireframes/cartilha de foto

Aluno tira foto da redação manuscrita pra mandar via WhatsApp. Hoje
sem orientação visual de como posicionar câmera, enquadrar, evitar
sombra/borrado. Wireframes precisam mostrar:
- Posicionamento da folha (paisagem ou retrato)
- Distância da câmera + iluminação adequada
- Estrutura da redação ENEM (cabeçalho, 30 linhas numeradas, margem)
- O que evitar (sombra, borrado, cortado)

Sem QR code (descartado quando OF14 1S não usou no design final).

Dois lugares possíveis pra entregar:
1. Mensagem do bot quando aluno manda foto rejeitada pelo OCR
   (texto + link pra material visual)
2. Material físico/PDF distribuído pela escola como cartilha

**Sessão futura. Não bloqueia uso atual.**
