# Séries × Oficinas — declaração canônica (Projeto ATO)

Documento canônico de **o que cada série tem** em termos de oficinas,
quais delas viram missões corrigidas pelo Redato, e em que modo de
correção. Este arquivo é a **fonte da verdade** que alimenta o seed do
catálogo `missoes` no banco.

> **Convenção de prefixo.** Códigos seguem `RJ{1|2|3}·OF{NN}·MF` —
> `RJ` permanece de "Redação em Jogo", nome técnico legado em prompts
> e detectores. App agora chama "Projeto ATO", mas trocar o prefixo
> exige migração coordenada (DB + prompts + detectores + bot legacy).
> Mudança fica fora de escopo desta fase.

## Modelo de declaração

Cada série declara:

1. **Lista completa de oficinas** (1..N) — `numero` + `titulo curto`.
   Inclui oficinas que NÃO vão pra Redato (ex.: roda de leitura,
   simulado escrito a mão sem correção automática, etc.).
2. **Pra cada oficina que vira missão corrigida**:
   - `codigo`: `RJ{serie}·OF{NN}·MF` (snake-stable, fonte de verdade
     pra deep-link, prompt cache, telemetria).
   - `titulo` da missão (texto curto pro menu).
   - `modo_correcao` (enum):
     - `foco_c1` · `foco_c2` · `foco_c3` · `foco_c4` · `foco_c5` —
       avalia 1 competência só.
     - `completo_parcial` — avalia subset (ex.: C2+C3+C4 quando o
       desenho da oficina deixa C1/C5 fora).
     - `completo` — avalia C1-C5 (1000 pontos).
   - `competencias_avaliadas`: lista `[C1..C5]`. Derivável do modo
     mas explicitada pra leitor humano.
3. **Oficinas NÃO-Redato** com motivo curto (presencial, simulado,
   discussão, etc.) — pra rastreabilidade pedagógica.

Tudo o que **não** é (1)/(2)/(3) — objetivos BNCC, checkpoints, blocos
metodológicos — é **metadata pedagógica** e fica em arquivos separados
(ver `redato_1S_criterios.md` etc.). NÃO entra no schema do banco.

## 1S (1ª série) — 14 oficinas

Status pedagógico e ordem das oficinas em
[redato_1S_criterios.md](redato_1S_criterios.md). Resumo aqui:

| # | Oficina (título curto) | Vai pra Redato? | Motivo / código |
|---|---|---|---|
| 1 | Diagnóstico inicial | NÃO | Avaliação de entrada presencial |
| 2 | Estrutura dissertativa | NÃO | Aula expositiva |
| 3 | Tese + introdução | NÃO | Atividade dirigida |
| 4 | Repertório sociocultural | NÃO | Pesquisa + roda |
| 5 | Argumentação C3 (intro) | NÃO | Modelagem em sala |
| 6 | Coesão e conectivos C4 | NÃO | Exercício dirigido |
| 7 | Proposta de intervenção C5 | NÃO | Exercício dirigido |
| 8 | Tutorial Redato | NÃO | Onboarding do bot |
| 9 | Simulado em sala | NÃO | Correção pelo prof |
| 10 | **Foco C3** | **SIM** | `RJ1·OF10·MF` |
| 11 | **Foco C4** | **SIM** | `RJ1·OF11·MF` |
| 12 | **Foco C5** | **SIM** | `RJ1·OF12·MF` |
| 13 | **Completo parcial** | **SIM** | `RJ1·OF13·MF` |
| 14 | **Completo** | **SIM** | `RJ1·OF14·MF` |

### Missões (entram no seed)

```yaml
- codigo: "RJ1·OF10·MF"
  serie: "1S"
  oficina_numero: 10
  titulo: "Foco C3"
  modo_correcao: "foco_c3"
  competencias_avaliadas: ["C3"]

- codigo: "RJ1·OF11·MF"
  serie: "1S"
  oficina_numero: 11
  titulo: "Foco C4"
  modo_correcao: "foco_c4"
  competencias_avaliadas: ["C4"]

- codigo: "RJ1·OF12·MF"
  serie: "1S"
  oficina_numero: 12
  titulo: "Foco C5"
  modo_correcao: "foco_c5"
  competencias_avaliadas: ["C5"]

- codigo: "RJ1·OF13·MF"
  serie: "1S"
  oficina_numero: 13
  titulo: "Completo Parcial"
  modo_correcao: "completo_parcial"
  competencias_avaliadas: ["C2", "C3", "C4"]

- codigo: "RJ1·OF14·MF"
  serie: "1S"
  oficina_numero: 14
  titulo: "Completo"
  modo_correcao: "completo"
  competencias_avaliadas: ["C1", "C2", "C3", "C4", "C5"]
```

Implementação: [redato_backend/portal/seed_missoes.py](../../../backend/notamil-backend/redato_backend/portal/seed_missoes.py).

## 2S (2ª série) — TBD

**Pendente:** declaração da árvore de oficinas + missões da 2ª série.

Esperado:
- Foco C1 e C2 entram em jogo (oficinas que treinam norma culta e
  organização textual em isolado). Por isso `foco_c1`/`foco_c2` viraram
  modos válidos no schema (migração `e9f1c8a2b4d5`, M8+).
- `RJ2·OF{NN}·MF` é o padrão de código.

Escrever no template abaixo quando a equipe pedagógica fechar o
desenho:

```yaml
# 2S — exemplo (PREENCHER)
# - codigo: "RJ2·OFXX·MF"
#   serie: "2S"
#   oficina_numero: XX
#   titulo: "..."
#   modo_correcao: "foco_c1" | "foco_c2" | ... | "completo"
#   competencias_avaliadas: [...]
```

## 3S (3ª série) — TBD

**Pendente.** Tendência: missões `RJ3·OF{NN}·MF`, várias do tipo
`completo` simulando ENEM, com oficinas de revisão por competência
no formato `foco_*`.

## Como adicionar uma nova missão (passo-a-passo)

1. **Atualize este documento** (esta página) com a entrada da missão
   na seção da série correspondente. Sem documentar aqui, o catálogo
   fica órfão.
2. **Edite** [seed_missoes.py](../../../backend/notamil-backend/redato_backend/portal/seed_missoes.py)
   adicionando dict em `MISSOES_REJ_1S` (ou crie `MISSOES_2S` análogo).
3. **Verifique modo válido**: se for `foco_c1`/`foco_c2` ou um modo
   inédito, garanta que `MODO_CORRECAO_VALIDOS` em
   [models.py](../../../backend/notamil-backend/redato_backend/portal/models.py)
   inclui o valor — e que a migration mais recente
   ([e9f1c8a2b4d5](../../../backend/notamil-backend/redato_backend/portal/migrations/versions/e9f1c8a2b4d5_extend_modo_correcao_foco_c1_c2.py) atual) já permite.
4. **Roda local**: `python -m redato_backend.portal.seed_missoes`
   (idempotente — só insere o que falta, atualiza o que mudou).
5. **Cuidado com prompts**: cada `modo_correcao` tem prompt específico
   no `dev_offline.py` do grader. Modos inéditos exigem definir prompt
   antes de virar atividade real.
6. **Cuidado com bot**: aluno digita "10", "11", ... para identificar
   missão. O regex em
   [redato_backend/whatsapp/portal_link.py](../../../backend/notamil-backend/redato_backend/whatsapp/portal_link.py)
   resolve número → código RJ1·OF10·MF. Se a 2S/3S virem missões fora
   do range 10-14, ajustar o resolver.

## Por que isso fica fora do schema

A árvore pedagógica (objetivos BNCC, checkpoints, blocos, ordem
sugerida) muda a cada revisão pedagógica anual. Schema rígido virou
overhead — equipe pedagógica preferia editar markdown que escrever
migration. Decisão final:

- **No schema (Postgres `missoes`)**: o mínimo que a UI/bot precisa pra
  funcionar — codigo, serie, oficina_numero, titulo, modo_correcao.
- **Em markdown (este doc + `redato_1S_criterios.md`)**: tudo o resto.

Custo: precisa lembrar de manter doc + seed sincronizados. Aceitável
porque seed é idempotente e roda em deploy.

## Histórico de mudanças

| Data | Mudança |
|---|---|
| 2026-04-27 | M8 — adiciona `foco_c1`, `foco_c2` ao enum (migração e9f1c8a2b4d5). Documenta template pra 2S/3S. |
| 2026-04-27 | M4 — cria tabela `missoes` com 5 missões REJ 1S (oficinas 10-14). |
