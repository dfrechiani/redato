# INVESTIGATION — Passo 7b: correção parcial de códigos no Jogo de Redação

**Data:** 2026-05-01
**Status:** investigação concluída, sem alteração de código.
**Pendência endereçada:** "quando aluno corrige 1 código, bot revalida só essa carta sozinha contra partida inteira" — comportamento errado, deveria acumular as correções com os códigos já válidos.

## TL;DR

O bug é **arquitetural**, não de uma linha. O bot processa a lista de códigos do aluno **toda como atômica**: ou todos válidos (persistir + montar texto), ou retorna erro e **descarta tudo**. Não há mecanismo pra acumular o que era válido na 1ª tentativa com a correção da 2ª.

**Pontos principais:**
1. `validar_partida` em [`jogo_partida.py:188`](../../backend/notamil-backend/redato_backend/whatsapp/jogo_partida.py) é **fail-fast**: o primeiro código desconhecido faz a função retornar `ok=False` imediatamente. Os 16 códigos válidos antes dele nem chegam a ser persistidos.
2. `_handle_aguardando_cartas_partida` em [`bot.py:1408-1523`](../../backend/notamil-backend/redato_backend/whatsapp/bot.py) na 2ª mensagem chama `validar_partida(codigos, ctx)` com **apenas os códigos novos** que o aluno digitou — sem buscar os códigos da 1ª tentativa.
3. `partida.cartas_escolhidas` (campo JSONB no Postgres) é **só populado quando validação inteira passa** — não há histórico parcial.
4. Se o aluno corrigir só o código errado, falha por falta de estruturais. Aluno é forçado a **redigitar todos os 17 códigos** mesmo que 16 estivessem corretos antes.

**Recomendação de abordagem (detalhe na §6):** persistir códigos **válidos parciais** mesmo quando a tentativa falha como um todo, e na próxima mensagem **fazer merge** entre o que está persistido e o que o aluno mandou agora antes de chamar `validar_partida`. Idempotência natural via dedup que já existe na função.

---

## 1. Fluxo atual em prosa

O Jogo de Redação (Fase 2 passo 4+) é uma partida cooperativa onde 2-4 alunos da mesma turma montam um texto a partir de cartas de um baralho temático ("minideck"). Cada carta tem um código (`E01`, `P03`, `K22`, `AC07`, etc.) e o texto montado é a expansão dos placeholders das cartas estruturais (`E##`) com o conteúdo das cartas-lacuna (`P##` problema, `R##` repertório, `K##` conector, `A##`/`AC##`/`ME##`/`F##` proposta).

**Cadeia de decisão (caminho feliz):** o aluno está no estado FSM `AGUARDANDO_CARTAS_PARTIDA|<partida_id>` (SQLite local do bot). Manda mensagem de texto com os códigos separados por espaço/vírgula (ex.: `E01 E10 E17 E19 E21 E33 E35 E37 E49 E51 P03 R05 K22 A01 AC07 ME04 F02`). O handler `_handle_aguardando_cartas_partida` ([`bot.py:1408-1523`](../../backend/notamil-backend/redato_backend/whatsapp/bot.py)) faz:

1. Decodifica `partida_id` do estado FSM ([`bot.py:1424`](../../backend/notamil-backend/redato_backend/whatsapp/bot.py)).
2. Busca a partida no Postgres via `PL.get_partida_by_id(...)` — verifica que ainda existe e não expirou.
3. Parseia os códigos do texto via `parse_codigos(text)` em [`jogo_partida.py:42-52`](../../backend/notamil-backend/redato_backend/whatsapp/jogo_partida.py) — extrai tokens regex `(E|P|R|K|AC|ME|A|F)\d+`.
4. Carrega `ContextoValidacao` (catálogo de cartas válidas pra esse minideck) via `PL.carregar_contexto_validacao(...)`.
5. **Chama `validar_partida(codigos, ctx)`** em [`bot.py:1475`](../../backend/notamil-backend/redato_backend/whatsapp/bot.py) — passa os códigos **da mensagem atual** apenas.
6. Se válido: monta texto via `montar_texto_montado(...)`, persiste via `PL.persist_cartas_e_texto(...)` em [`bot.py:1493-1497`](../../backend/notamil-backend/redato_backend/whatsapp/bot.py), transiciona FSM pra `REVISANDO_TEXTO_MONTADO|<partida_id>` e responde com o texto.

**Cadeia quando algum código é inválido:** `validar_partida` retorna `ok=False, mensagem_erro="Não achei a carta K99 no tema X..."` ([`jogo_partida.py:245-254`](../../backend/notamil-backend/redato_backend/whatsapp/jogo_partida.py)). O handler retorna apenas a mensagem de erro em [`bot.py:1476-1477`](../../backend/notamil-backend/redato_backend/whatsapp/bot.py):

```python
resultado = validar_partida(codigos, ctx)
if not resultado.ok:
    return [OutboundMessage(resultado.mensagem_erro or "Validação falhou.")]
```

**Estado FSM permanece `AGUARDANDO_CARTAS_PARTIDA|<partida_id>`** — nada é persistido. O campo `partida.cartas_escolhidas` continua intacto (vazio se 1ª tentativa, ou com a última escolha completa que passou de tentativas anteriores).

**Quando aluno corrige (2ª mensagem):** o handler é chamado de novo, parse de `parse_codigos` retorna **só os códigos novos** que o aluno digitou (ex.: `K22` se ele corrigiu apenas o `K99`). `validar_partida(["K22"], ctx)` é chamado com lista de 1 elemento. A função roda Step 1 (existe? sim). Mas Step 2 (1 estrutural por seção do tabuleiro, [`jogo_partida.py:264+`](../../backend/notamil-backend/redato_backend/whatsapp/jogo_partida.py)) falha porque não há **nenhuma** estrutural na lista de 1 código. Retorna `ok=False` com mensagem sobre estrutural faltando.

**Isso é o bug pro aluno:** ele recebe um erro novo ("falta estrutural na seção X") sobre uma estrutural que ele já tinha mandado certo na 1ª tentativa. Pra fazer a partida funcionar, precisa redigitar todos os 17 códigos juntos com a correção embutida.

---

## 2. Trecho exato do código com o bug

O bug não está em **uma** linha — está na **ausência de mecanismo de acumulação**. Os pontos relevantes são:

### 2.a — `_handle_aguardando_cartas_partida` ([`bot.py:1454-1477`](../../backend/notamil-backend/redato_backend/whatsapp/bot.py))

```python
text = (msg.text or "").strip()
codigos = parse_codigos(text)
# ↑ codigos só vem do que o aluno digitou AGORA. Não é mergeado com
#   códigos válidos persistidos da 1ª tentativa.

if not codigos:
    # Texto sem códigos — repete a saudação como prompt.
    ...

# Carrega catálogo do minideck pra validar
ctx = PL.carregar_contexto_validacao(partida.minideck_id)
...

resultado = validar_partida(codigos, ctx)
# ↑ validar contra lista que TÁ FALTANDO os válidos da 1ª tentativa.
if not resultado.ok:
    return [OutboundMessage(resultado.mensagem_erro or "Validação falhou.")]
# ↑ retorna erro sem persistir os válidos parciais que estão em `codigos`.
```

### 2.b — `persist_cartas_e_texto` ([`portal_link.py:809-829`](../../backend/notamil-backend/redato_backend/whatsapp/portal_link.py))

```python
def persist_cartas_e_texto(
    *,
    partida_id: uuid.UUID,
    codigos: List[str],
    texto_montado: str,
) -> None:
    ...
    cartas = dict(partida.cartas_escolhidas or {})
    cartas["codigos"] = list(codigos)
    # ↑ SUBSTITUI a lista. Pra acumular precisaria fazer
    #   cartas["codigos"] = list(set(cartas.get("codigos", []) + codigos))
    #   (com dedup) — ou mover acumulação pro caller.
    partida.cartas_escolhidas = cartas
    partida.texto_montado = texto_montado
    session.commit()
```

Esse helper só é chamado **quando a validação passa inteira** ([`bot.py:1493-1497`](../../backend/notamil-backend/redato_backend/whatsapp/bot.py)) — não tem como acumular válidos parciais com a estrutura atual do código.

### 2.c — `validar_partida` é fail-fast ([`jogo_partida.py:245-254`](../../backend/notamil-backend/redato_backend/whatsapp/jogo_partida.py))

```python
if desconhecidos:
    return ResultadoValidacao(
        ok=False,
        mensagem_erro=(
            f"Não achei a carta {desconhecidos[0]} no tema "
            f"{ctx.minideck_nome_humano!r}. Confere se o código "
            f"está certo e se você está jogando o tema dessa "
            f"partida."
        ),
    )
# ↑ Para no PRIMEIRO desconhecido. Não retorna lista de válidos
#   parciais que poderia ser persistida.
```

Mesmo se a função fosse modificada pra retornar a lista de válidos junto com a mensagem de erro, o handler `_handle_aguardando_cartas_partida` não teria onde persistir essa lista parcial — `persist_cartas_e_texto` exige `texto_montado` que só existe quando todas as estruturais válidas estão presentes.

---

## 3. Schema do estado relevante

### 3.a — FSM no SQLite local (bot)

[`bot.py:53`](../../backend/notamil-backend/redato_backend/whatsapp/bot.py): `AGUARDANDO_CARTAS_PARTIDA = "AGUARDANDO_CARTAS_PARTIDA"`. Estado armazenado em `alunos.estado` no formato:

```
AGUARDANDO_CARTAS_PARTIDA|<uuid_partida>
```

Sem payload de histórico. Apenas o `partida_id` é codificado. Não há slot pra "códigos válidos da 1ª tentativa".

### 3.b — Tabela `partidas_jogo` no Postgres

Model em [`portal/models.py:848-905`](../../backend/notamil-backend/redato_backend/portal/models.py): `PartidaJogo`.

Campo crítico:

| Campo | Tipo | Estado normal | Estado em erro de validação |
|---|---|---|---|
| `cartas_escolhidas` | `JSONB` (default `list`) | `{"codigos": ["E01", "E10", ..., "F02"], "_alunos_turma_ids": [...]}` após validação OK | inalterado entre tentativas (continua `{"codigos": []}` ou último estado válido) |
| `texto_montado` | `Text` | preenchido com expansão | `NULL` ou último valor |
| `prazo_reescrita` | `TIMESTAMP` | usado pra expirar partida | — |
| `_alunos_turma_ids` | dentro de `cartas_escolhidas` | preservado entre tentativas | preservado |

Não existe campo de "histórico de tentativas" nem "códigos válidos parciais". O comentário do model em [`portal/models.py:854-857`](../../backend/notamil-backend/redato_backend/portal/models.py) diz: *"snapshot com a lista de codigos [...]. Não é FK pra preservar histórico"* — mas na prática só guarda o **último estado completo válido**.

### 3.c — `ResultadoValidacao` em memória ([`jogo_partida.py:166-176`](../../backend/notamil-backend/redato_backend/whatsapp/jogo_partida.py))

```python
@dataclass
class ResultadoValidacao:
    ok: bool
    mensagem_erro: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    estruturais_em_ordem: List[str] = field(default_factory=list)
    lacunas_por_tipo: Dict[str, List[str]] = field(default_factory=dict)
    placeholders_vazios: List[str] = field(default_factory=list)
```

Quando `ok=False`, os campos `estruturais_em_ordem` e `lacunas_por_tipo` **podem estar parcialmente preenchidos** (a função pré-aloca antes do return). Mas o handler atual não usa esses campos em caso de erro — descarta o objeto inteiro.

---

## 4. Cenários de teste pra validação futura

Os 3 cenários abaixo cobrem o espaço de comportamentos esperados após o fix. Todos assumem partida ativa, prazo não expirado, aluno em `AGUARDANDO_CARTAS_PARTIDA|<partida_id>`.

### Cenário A — Correção parcial de 1 código

**Setup:** minideck exige 10 estruturais (E01..E51 sem repetir seção) + ≥1 lacuna por tipo de placeholder + ≥2 lacunas de proposta. Total típico: 17 cartas.

**Passo 1 (1ª mensagem):** aluno manda
```
E01 E10 E17 E19 E21 E33 E35 E37 E49 E51 P03 R05 K99 A01 AC07 ME04 F02
                                           ^^^ inválido
```
**Esperado:**
- Bot retorna mensagem "Não achei K99 no tema X..." apontando o código errado.
- **NOVO:** persiste em `partida.cartas_escolhidas["codigos_validos_parciais"]` os 16 códigos válidos: `["E01", "E10", "E17", "E19", "E21", "E33", "E35", "E37", "E49", "E51", "P03", "R05", "A01", "AC07", "ME04", "F02"]`.
- FSM permanece em `AGUARDANDO_CARTAS_PARTIDA`.

**Passo 2 (correção):** aluno manda apenas
```
K22
```
**Esperado:**
- Bot lê `cartas_escolhidas["codigos_validos_parciais"]` da 1ª tentativa.
- Faz merge: `codigos_acumulados = list(válidos_parciais) + ["K22"]` (com dedup via `validar_partida` que já tem isso embutido em [`jogo_partida.py:209-218`](../../backend/notamil-backend/redato_backend/whatsapp/jogo_partida.py)).
- Chama `validar_partida(codigos_acumulados, ctx)` → passa.
- Persiste `cartas_escolhidas["codigos"]` (lista final completa) + `texto_montado`.
- Limpa `codigos_validos_parciais` (já consumido).
- Transiciona pra `REVISANDO_TEXTO_MONTADO|<partida_id>`.

### Cenário B — Aluno corrige todos os faltantes em 1 mensagem

**Passo 1:** aluno manda lista com 3 códigos inválidos (ex.: K99, AC99, F99 — todos errados).

**Passo 2 (correção tripla):** aluno manda
```
K22 AC03 F08
```
**Esperado:** merge dos 14 válidos + 3 novos = 17 totais. Validação passa, texto monta, persistência completa.

### Cenário C — Idempotência: corrige um código que já era válido

**Passo 1:** aluno manda 17 códigos com K99 inválido. 16 válidos persistidos parciais.

**Passo 2 (idempotente):** aluno manda
```
E01 K22
```
(re-envia E01 que já era válido + a correção K22)

**Esperado:** merge `[E01, ..., F02 (16 válidos), E01, K22]` → dedup automático no `validar_partida` ([`jogo_partida.py:213-218`](../../backend/notamil-backend/redato_backend/whatsapp/jogo_partida.py) faz `set` com warning de duplicatas). E01 não vira duplicata fatal — só warning. K22 entra. Validação passa.

**Caso especial:** se aluno re-envia um código de **lacuna** que já estava válido com **outro código do mesmo tipo** (ex.: K22 quando 1 K já estava persistido), a partida pode acabar com 2 conectores K. Comportamento atual de `validar_partida` permite mais de 1 lacuna por tipo (Step 4 só exige `>= 1`). Não é regressão. Documentar como aceitável.

---

## 5. Edge cases e considerações pra design

- **Expiração da partida entre tentativas:** se `prazo_reescrita` passa entre passo 1 e passo 2, [`bot.py:1444-1448`](../../backend/notamil-backend/redato_backend/whatsapp/bot.py) já trata. Códigos parciais persistidos não precisam ser limpos — quando próximo aluno entrar, partida já não está válida.

- **Aluno sai e volta dias depois:** `cartas_escolhidas["codigos_validos_parciais"]` permaneceria. Isso pode confundir se ele lembrar errado quais códigos digitou. Sugestão de mitigação: TTL no campo (só considera parciais escritos nas últimas 24h). Ou: limpar parciais quando aluno sai do estado FSM (mas FSM SQLite local não tem trigger pra isso — ficaria órfão). Aceito o design simples sem TTL e documenta.

- **Concorrência: 2 alunos da mesma partida mandando mensagens simultaneamente:** `cartas_escolhidas` é `JSONB` com leitura-escrita não-atômica. Se aluno A persiste parciais ao mesmo tempo que aluno B, um sobrescreve o outro. Mitigação: usar `UPDATE ... SET cartas_escolhidas = jsonb_set(...)` com cláusula que combina campos. **Não é** regressão deste fix — `persist_cartas_e_texto` atual já tem o mesmo problema. Documentar como pendência separada se for relevante.

- **Códigos parciais com erro no Step 2-5** (não só Step 1 desconhecido): se o aluno manda 17 códigos e a falha é "duas estruturais na seção `argumentacao`", os parciais persistidos são quais? Sugestão: persistir apenas os códigos do `Step 1` que existiram (`estruturais_escolhidas + lacunas_escolhidas` ainda não-deduplicadas pra seção). O `validar_partida` precisa expor isso na próxima iteração — hoje só retorna `mensagem_erro` na falha do Step 2+.

---

## 6. Recomendação de abordagem do fix

**Estratégia em 3 camadas, ordenadas por impacto + risco crescentes.** Daniel decide quanto implementar.

### Camada 1 — Persistir parciais quando Step 1 (código existe) passa pra todos

**Mudança mínima viável.** Em [`jogo_partida.py:188-254`](../../backend/notamil-backend/redato_backend/whatsapp/jogo_partida.py), `validar_partida` ganha um parâmetro `codigos_existentes_acumulados: List[str] = []` e o handler em [`bot.py:1475`](../../backend/notamil-backend/redato_backend/whatsapp/bot.py) passa o que está em `cartas_escolhidas["codigos_validos_parciais"]` (se houver). Antes do Step 1, deduplica `(codigos_acumulados + codigos_novos)` pra rodar tudo junto.

Adicional: handler persiste `codigos_validos_parciais` quando Step 1 falha (algum código desconhecido) — listando os que foram aceitos no Step 1 mas o erro veio depois. Helper novo em `portal_link.py`: `persist_codigos_parciais(partida_id, codigos)` que faz `UPDATE` com `jsonb_set`.

**Cenários cobertos:** A, B, C parcialmente. Se aluno tem erro Step 2+ (estruturais duplicadas, etc.) na 1ª tentativa, ainda redigita tudo na 2ª — porque parciais não foram persistidos.

**Risco:** baixo. Função `validar_partida` mantém comportamento existente quando `codigos_existentes_acumulados=[]`. Compatibilidade com testes existentes preservada.

### Camada 2 — Step 2-5 também retornam parciais válidos

`ResultadoValidacao` ganha campo `codigos_aceitos: List[str]` que representa "esses códigos passaram em todas as validações até onde a função conseguiu validar". Mesmo em `ok=False`, esse campo é populado.

`_handle_aguardando_cartas_partida` persiste sempre `resultado.codigos_aceitos` em parciais quando `ok=False`. Próxima tentativa: merge antes de validar.

**Cenários cobertos:** A, B, C completamente. Cobre erros Step 2-5.

**Risco:** médio. Mais campos pra preencher em `validar_partida` em todos os return statements. Testes precisam confirmar que `codigos_aceitos` está consistente.

### Camada 3 — UI guiada por fase (estruturais → lacunas → proposta)

Bot orquestra a fase: pede estruturais primeiro, valida, persiste, depois pede lacunas, depois proposta. Cada fase é um sub-estado FSM (`AGUARDANDO_CARTAS_PARTIDA_ESTRUTURAIS`, `AGUARDANDO_CARTAS_PARTIDA_LACUNAS`, etc.). Aluno só vê erros do que mandou na fase atual; correções são naturalmente parciais.

**Cenários cobertos:** A, B, C + UX significativamente melhor pra alunos.

**Risco:** alto. Refactor completo do FSM. Mensagens novas. Testes existentes a refazer.

### Decisão sugerida

**Camada 1 + parte da Camada 2** (só `codigos_aceitos` em `ResultadoValidacao`, persistido pelo handler em qualquer falha). Cobre os 3 cenários listados + edge cases típicos. Mantém `validar_partida` retrocompatível (campo novo é opcional). Refactor proporcional ao bug.

Camada 3 fica como pendência futura — pode ser plano de UX separado, com validação pedagógica antes (alunos jogando partidas reais decidem se gostam mais do fluxo guiado).

---

## 7. Testes existentes (lacunas)

Em [`tests/whatsapp/test_bot_jogo_partida.py`](../../backend/notamil-backend/redato_backend/tests/whatsapp/test_bot_jogo_partida.py) e [`test_bot_jogo_partida_completa.py`](../../backend/notamil-backend/redato_backend/tests/whatsapp/test_bot_jogo_partida_completa.py):

| Teste existente | Cobre? |
|---|---|
| `test_codigo_inexistente_recusa` (~L382-393) | Recusa erro único, **não** retentativa |
| `test_segunda_mensagem_em_aguardando_sem_codigos_repete_prompt` (~L585-592) | 2ª mensagem sem códigos repete prompt — caso degenerado, não correção parcial |
| `test_lacuna_dev_obrigatoria_falta_recusa` (~L595-608) | Erro de lacuna obrigatória — uma só tentativa |
| `test_jogo_partida_logic.py` (várias) | Funções puras (`validar_partida`, `montar_texto_montado`, `parse_codigos`) sem cenário iterativo |

**Lacuna confirmada:** **0 testes** cobrem fluxo "aluno manda inválidos parciais → recebe erro → retenta com correção". Os 3 cenários da §4 deste documento devem virar testes novos quando o fix for implementado.

---

## 8. Apêndice — paths absolutos e linhas-chave

| Componente | Path | Linhas-chave |
|---|---|---|
| Estado FSM `AGUARDANDO_CARTAS_PARTIDA` | `backend/notamil-backend/redato_backend/whatsapp/bot.py` | 53 |
| Handler entrypoint | mesmo | 1408-1523 |
| Chamada `validar_partida` | mesmo | 1475 |
| Return em erro (sem persistir parciais) | mesmo | 1476-1477 |
| `validar_partida` (fail-fast Step 1) | `backend/notamil-backend/redato_backend/whatsapp/jogo_partida.py` | 188-254 |
| Dedup de códigos repetidos | mesmo | 209-218 |
| `parse_codigos` (regex extrator) | mesmo | 42-52 |
| `ResultadoValidacao` dataclass | mesmo | 166-176 |
| `persist_cartas_e_texto` (substitui, não acumula) | `backend/notamil-backend/redato_backend/whatsapp/portal_link.py` | 809-829 |
| Substituição (`cartas["codigos"] = list(codigos)`) | mesmo | 826 |
| Model `PartidaJogo` (Postgres) | `backend/notamil-backend/redato_backend/portal/models.py` | 848-905 |
| Campo `cartas_escolhidas` (JSONB) | mesmo | 870-871 |
| Tests existentes | `backend/notamil-backend/redato_backend/tests/whatsapp/` | `test_bot_jogo_partida{,_completa}.py`, `test_jogo_partida_logic.py` |

---

_Investigação realizada em 2026-05-01. Sem mudanças em código de produção. Próximos passos sugeridos: revisão do design pela Camada 1 + Camada 2 parcial; implementação + testes dos 3 cenários da §4._

---

## RESOLVIDO em commit `fix(jogo): bot acumula códigos parciais entre correções (Passo 7b)`

**Data do fix:** 2026-05-01.
**Estratégia escolhida:** Camadas 1+2 combinadas (decisão do Daniel).

### Mudanças

**`backend/notamil-backend/redato_backend/whatsapp/jogo_partida.py`**
- `ResultadoValidacao` ganhou campo `codigos_aceitos: List[str]` (default `[]`).
- `validar_partida(codigos, ctx, codigos_existentes_acumulados=None)`:
  parâmetro novo opcional. Quando passado, faz prepend dos parciais
  antes do dedup defensivo. Idempotência natural (dedup já existia).
- Cada return `ok=False` agora popula `codigos_aceitos` com `[e.codigo
  for e in estruturais_escolhidas] + [l.codigo for l in lacunas_escolhidas]`
  — códigos que passaram Step 1, qualquer que seja a etapa que falhou.
- Return `ok=True` final também popula (consistência; caller usa pra
  saber quanto persistir).

**`backend/notamil-backend/redato_backend/whatsapp/portal_link.py`**
- Novo: `get_codigos_parciais(partida_id) -> List[str]`. Lê
  `cartas_escolhidas["codigos_parciais"]` defensivo (vazio se ausente).
- Novo: `persist_codigos_parciais(partida_id, codigos_aceitos)`. UPDATE
  do JSONB preservando `_alunos_turma_ids` e outros campos.
- `persist_cartas_e_texto` (caminho feliz): agora também limpa
  `codigos_parciais = []` ao gravar lista final. Higiene caso partida
  seja re-aberta no futuro.

**`backend/notamil-backend/redato_backend/whatsapp/bot.py`**
- `_handle_aguardando_cartas_partida` (linhas ~1475-1510):
  - Lê parciais via `PL.get_codigos_parciais(partida_id)` antes de validar.
  - Passa pro `validar_partida(..., codigos_existentes_acumulados=...)`.
  - Em caso de erro (`resultado.ok == False`), persiste
    `resultado.codigos_aceitos` em parciais (try/except + logger,
    falha aqui não derruba a UX do aluno).
  - Em caso de sucesso, `persist_cartas_e_texto` já limpa parciais —
    nada extra no handler.

### Cobertura de testes (todos passando)

**`tests/whatsapp/test_jogo_partida_logic.py`** (+6 testes):
1. `test_validar_partida_acumula_parciais_step1_falha` — 1 desconhecido
   no Step 1, 16 válidos populam `codigos_aceitos`.
2. `test_validar_partida_acumula_parciais_step2_falha` — falta seção
   PROPOSTA, 9 estruturais + 3 lacunas em `codigos_aceitos`.
3. `test_validar_partida_acumula_parciais_passa_quando_completa` —
   cenário A do briefing: 16 parciais + 1 corrigido = 17, `ok=True`.
4. `test_validar_partida_idempotente_re_envio_de_codigo_valido` —
   cenário C: aluno re-envia E01 válido + K22, dedup funciona, total 17.
5. `test_validar_partida_codigos_aceitos_caminho_feliz_sem_acumulado`
   — aluno manda 17 numa só, `codigos_aceitos` espelha lista válida.
6. `test_validar_partida_codigos_existentes_acumulados_none_eh_default`
   — chamadas legadas sem o param novo continuam funcionando.

**Resultado pytest:** 375 → 381 passed (+6), 35 skipped, 0 regressão.

### Schema final de `partida.cartas_escolhidas` (JSONB)

```jsonc
{
  "codigos": ["E01", ..., "F02"],          // só populado quando partida completa OK
  "codigos_parciais": ["E01", ..., "F02"], // populado entre tentativas, limpo ao final
  "_alunos_turma_ids": [...]               // sempre preservado
}
```

### Cenários cobertos (referência §4 acima)

- ✅ A (correção parcial de 1 código): aluno corrige só `K99 → K22`, bot
  faz merge com 16 parciais, validação passa.
- ✅ B (correção tripla em 1 mensagem): aluno corrige 3 errados juntos,
  merge com 14 parciais, total 17 valida.
- ✅ C (idempotência): aluno re-envia E01 já válido + K22, dedup natural.

### Fora do escopo deste fix (pendências futuras)

- **Camada 3** (UX guiada por fase: estruturais → lacunas → proposta).
  Refactor do FSM completo + sub-estados. Pendência não-urgente — UX
  atual com Camada 1+2 já resolve o bug operacional.
- **Concorrência** entre alunos da mesma partida atualizando
  `cartas_escolhidas` simultaneamente. Problema **pré-existente** em
  `persist_cartas_e_texto`, não regressão deste fix. Mitigação ideal:
  `jsonb_set` com lock pessimista; aceitável atualmente porque alunos
  costumam jogar em sequência, não simultâneo.
- **TTL nos parciais**: aluno volta dias depois com parciais antigos —
  decisão atual é não TTL (cada partida é UUID nova, não há acúmulo
  global). Reavaliar se aparecer reclamação operacional.
