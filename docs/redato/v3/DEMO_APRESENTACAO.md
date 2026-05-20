# Demo Redato — roteiro pra apresentação

**Tempo total:** 5-7 min de tela + 1-2 min de Q&A.
**Última atualização:** 2026-05-04.

## TL;DR do roteiro

```
1. Aluno manda foto pelo WhatsApp        (30s)
2. Aguarda correção chegar               (~25s)
3. Lê feedback no celular                (30s)
4. Abre portal do professor              (1 min)
5. Mostra Dashboard storytelling         (1-2 min)
6. Drilla no perfil do aluno             (1-2 min)
7. Pergunta-resposta                     (1-2 min)
```

## Pre-flight (15 min antes da apresentação)

### 1. Confirma backend UP

```bash
curl -fsS https://backend-production-3bd7.up.railway.app/admin/health/full | jq
```

Esperado: `"status":"ok"` + `twilio_configured: true`.

Se der erro: avisa que está ofline, pula pra **Plano B** (slides + screenshots).

### 2. ⚠️ EVITA OF14 — usa FOCO

Bug conhecido (registrado em PENDÊNCIAS): OF14 cai no fallback
Sonnet v2 porque a chave OpenAI desta conta NÃO tem acesso ao FT
`BTBOS5VF`. Sintomas visuais: **`nota_total = —`**, **bloco
"Análise da redação" some**. Não vai ser bom em apresentação.

**Use missão FOCO** — Sonnet direto, schema completo, ~25s:

| Missão | Foco | Tempo | Recomendado pra demo |
|---|---|---|---|
| `RJ1·OF12·MF` Leilão de Soluções | C5 (proposta) | ~25s | ⭐ **Use esta** — tem oficinas mapeadas, feedback rico |
| `RJ1·OF11·MF` Conectivos Argumentativos | C4 (coesão) | ~25s | Alternativa |
| `RJ1·OF10·MF` Tese e Argumentos | C3 (argumentação) | ~25s | Alternativa |

### 3. Garante turma + atividade + aluno cadastrado

Acesse o portal:
```
https://frontend-production-74ab7.up.railway.app
```

Login como professor. Confirma:
- [ ] Turma de demo existe (ex.: `TURMA-DEMO-1A-2026`)
- [ ] Atividade ativa com `RJ1·OF12·MF` (data_fim > hoje)
- [ ] Pelo menos 1 aluno cadastrado (você mesmo, com seu telefone)
- [ ] **Pelo menos 3-5 envios prévios** com nota — sem isso, o
      Dashboard fica vazio e perde graça na demo

Se faltar envios prévios, gera agora:
- Manda 3-5 fotos diferentes do mesmo celular (varia o conteúdo
  da redação pra ter variação nas notas)
- Cada envio ~25s, total ~2 min

### 4. Faz pelo menos 1 envio com diagnóstico cognitivo populado

Diagnóstico cognitivo (Fase 2+) roda ~12s DEPOIS da correção
terminar. Pra a tela "Mapa Cognitivo" aparecer com lacunas + heatmap
+ sugestões pedagógicas, **precisa de envios diagnosticados**.

Verifica via shell Railway:
```bash
psql "$DATABASE_URL" -c "
  SELECT COUNT(*) FROM envios WHERE diagnostico IS NOT NULL;
"
```

Se for 0, manda mais 1 foto, aguarda ~1 min total, re-confere.

### 5. Pré-carrega abas do navegador

Pra demo fluir sem ficar digitando URL:

- **Aba 1**: `https://frontend-production-74ab7.up.railway.app/turma/<id>?aba=dashboard`
- **Aba 2**: `https://frontend-production-74ab7.up.railway.app/turma/<id>/aluno/<aluno-id>`
- **Aba 3**: WhatsApp Web (pra mostrar a conversa do bot)

### 6. Celular carregado + WhatsApp opt-in

- Bateria > 50%
- Já mandou `join <duas-palavras>` antes (sandbox Twilio)
- Cabo USB ou screen mirroring pronto se for projetar a tela do celular

## Roteiro da demo (5-7 min)

### Cena 1 — Hook (30s)

> "Imaginem um aluno do ensino médio que mora numa cidade pequena,
> não tem cursinho, e a única coisa que tem é um celular com WhatsApp.
> Hoje vou mostrar como ele consegue feedback de redação ENEM em
> tempo quase real, sem app instalado, sem cadastro de cartão, sem
> nada."

[Mostra o celular com WhatsApp aberto na conversa do bot]

### Cena 2 — Aluno envia (30s)

> "Ele tira foto da redação manuscrita e manda pro bot. Aqui."

[No celular, na conversa com o bot:]
1. Tira foto da redação (ou usa uma já tirada)
2. Manda foto + texto `RJ1OF12MF`

> "Pronto. Agora a gente espera ~25 segundos."

### Cena 3 — Correção chega (1 min)

[Bot responde no WhatsApp]

> "Olha o que ele recebeu. Não é um número solto — é feedback
> pedagógico estruturado pelas 5 competências do ENEM."

[Lê em voz alta as 2-3 primeiras linhas do feedback recebido]

> "Repara que ele aponta o quê tá bom, o quê tá faltando, e dá um
> próximo passo concreto. Não é assistido por humano — é o Claude
> da Anthropic rodando em pipeline customizado com prompt caching
> e self-critique."

### Cena 4 — Perspectiva do professor (1 min)

[Troca pra Aba 1 do navegador — Dashboard da turma]

> "Mas o pulo do gato não é o aluno. É o professor."
>
> "Ele entra no portal e vê o que a turma TODA precisa. Não envio
> por envio — visão coletiva."

[Aponta pro bloco "🎯 O que sua turma precisa agora"]

> "Essa frase é gerada automaticamente pelo diagnóstico cognitivo.
> Diz exatamente: 'Dos 18 alunos da turma 1A, X têm dificuldade em
> proposta de intervenção. A lacuna mais comum é em Agente —
> não nomeiam quem vai executar.'"

[Aponta pros 3 blocos de ações:]

> "Embaixo, 3 listas de ação — agora, esta semana, este mês.
> O 'Trabalhar agora' já vem com a oficina sugerida pra mini-aula
> coletiva. Um clique aqui [aponta no botão Criar atividade] e a
> atividade vai ativada pra turma toda."

### Cena 5 — Drill no aluno individual (1-2 min)

[Troca pra Aba 2 — Perfil do aluno]

> "Se ele quer descer ao individual, abre o aluno."

[Mostra o bloco "Mapa cognitivo"]

> "Aqui é onde fica interessante. Cada quadrado é um descritor
> observável — são 40 ao todo, baseados na Matriz INEP. Verde =
> domínio, amarelo = incerto, vermelho = lacuna."
>
> "E pra cada lacuna prioritária, o sistema explica em 3 partes:
> O QUE É a lacuna, ONDE aparece no texto do aluno, e COMO o
> professor trabalha isso. Trecho real da redação como evidência."

[Hover num código BNCC]

> "Cada descritor vem mapeado pras habilidades BNCC oficiais do
> Ensino Médio. Pro coordenador da escola pedir justificativa
> pedagógica, já tá pronto: 'estamos trabalhando EM13LP29 e
> EM13LP38'."

### Cena 6 — Fecha (30s)

> "Resumindo o que vocês viram:
> 1. Aluno usa o celular que ele já tem, sem aprender app novo
> 2. Recebe feedback em ~25 segundos, 24h por dia
> 3. Professor vê visão coletiva da turma com plano de ação
> 4. Coordenador tem rastreabilidade BNCC automática
>
> Tudo isso por R$X por aluno por mês — comparado a uma redação
> corrigida por professor cursinho que custa R$Y."

## Plano B — se algo travar

### Backend offline

- Tela 1: screenshot do Dashboard storytelling salvo em
  `/Users/danielfrechiani/Desktop/redato_hash/docs/demo_screenshots/`
  (TIRA ANTES se não tiver)
- Narra o roteiro com base nos screenshots
- "Pra demo ao vivo, agendar com 1 dia de antecedência pra eu
  garantir que tá tudo no ar"

### Correção demora > 1 min

- Não fica olhando o celular parado
- "Enquanto a IA pensa, vou contar a história do projeto…"
- Pivota pra contexto: 5 fases entregues, decisões de arquitetura,
  custo por correção, parcerias com cursinhos

### Nota vem em branco / análise some

- Reconhece: "Esse é o caso de OF14 que tá no fallback Sonnet —
  conta OpenAI atual não tem o FT vencedor. Tô usando hoje foco_c5
  que vem completo. Migração de volta pro FT tá na próxima sprint."
- Mostra o C1-C5 individuais pelo menos: "soma = 280"
- Pivota pro Dashboard storytelling (que NÃO depende dessa correção)

### Aluno não cadastrado no Twilio sandbox

- Sandbox expira `join` em 3 dias inativo
- Manda `join <duas-palavras>` ao vivo: dá pra Twilio responder
  "joined" em <5s — vira parte da demo "olha como é fácil opt-in"

## Cheatsheet — comandos prontos pra colar

### Conferir saúde
```bash
curl -fsS https://backend-production-3bd7.up.railway.app/admin/health/full | jq
```

### Ver última correção do aluno (Railway shell)
```bash
psql "$DATABASE_URL" -c "
  SELECT i.resposta_aluno
  FROM interactions i
  JOIN envios e ON e.interaction_id = i.id
  ORDER BY e.enviado_em DESC LIMIT 1;
"
```

### Listar envios diagnosticados
```bash
psql "$DATABASE_URL" -c "
  SELECT id, diagnostico->>'modelo_usado',
         jsonb_array_length(diagnostico->'descritores') as n_desc
  FROM envios
  WHERE diagnostico IS NOT NULL
  ORDER BY created_at DESC LIMIT 5;
"
```

### Reprocessar correção que falhou (via API)
```bash
curl -X POST \
  https://backend-production-3bd7.up.railway.app/portal/envios/<envio_id>/reprocessar \
  -H "Authorization: Bearer <jwt>"
```

## FAQ provável da audiência

**"E se a foto for ruim?"**
OCR roda quality checks antes de gastar API (brilho < 60, blur,
texto < 50 chars). Rejeita e pede foto melhor. Custo da rejeição:
~$0.001.

**"Quanto custa por correção?"**
Foco (Sonnet 4.6): ~$0.03. Completo OF14 (Sonnet+self-critique):
~$0.86 com cache; FT BTBOS5VF: ~$0.05. Diagnóstico cognitivo:
+$0.04. Total OF14 completo: ~$0.90/redação no caso pior.

**"Como sabe que a nota é boa?"**
INEP validação: 9/11 canários acertam dentro de ±40 pontos
(ensemble de 3). Baseline humano de 2 corretores ENEM: 12-15% de
divergência > 100 pts. Estamos no mesmo range.

**"E LGPD?"**
Aluno opta-in mandando "join" pro sandbox Twilio. Foto fica
criptografada em volume Railway. Nome + telefone são os únicos
PII; mascarado por default no portal. Retenção: 6 meses.

**"Funciona offline?"**
Não. WhatsApp precisa de internet pro celular do aluno. Mas
funciona em 3G fraco — foto comprime no envio, resposta cabe em
800 chars.

**"E se OpenAI/Anthropic cair?"**
Fallback graceful: bot persiste o envio com `redato_output:
{"error": "..."}`, professor vê na lista com botão "Reprocessar
avaliação" e clica quando o provider voltar.

**"Como escala pra mais escolas?"**
1 backend Railway aguenta ~1k alunos ativos. Acima disso,
horizontal scaling (separa portal de bot) — refactor pequeno
documentado.

## Pontos de venda principais

Memorizar 3 frases pra usar em qualquer transição:

1. **"O aluno usa o celular que ele já tem."**
2. **"O professor vê o que a turma TODA precisa, não envio por envio."**
3. **"A IA explica O QUE É a lacuna, MOSTRA evidência, e SUGERE como ensinar."**
