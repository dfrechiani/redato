# IMPLEMENTATION_GUIDE · Redato

> Guia de implementação orientado a tarefas para o Claude Code.
> Cada tarefa lista os arquivos de referência que devem ser consultados, os critérios de aceitação, e dependências.

## Filosofia de implementação

A Redato é um produto pedagógico antes de ser um produto técnico. Isso significa:

- **Correção deve ser rápida em percepção, não em realidade.** Streaming de tokens é mais importante que tempo de resposta absoluto. Aluno esperando 30s sem feedback visual é pior que 60s com streaming.
- **Erros de IA devem ser recuperáveis, não bloqueantes.** Se a Claude retornar JSON inválido, o backend deve tentar reparar antes de mostrar erro ao aluno.
- **O professor é cliente tanto quanto o aluno.** Dashboards de turma precisam agregar dados de correção (distribuição de notas, competências mais fracas, progressão individual).
- **Privacidade de menores é crítica.** Textos de alunos não saem do ambiente controlado; não entram em treinamento de modelo.

---

## Tarefa 1 — Extrair o system prompt para TypeScript

**Prioridade:** Alta (bloqueia tudo)

### Contexto

O system prompt da Redato está documentado em markdown (`docs/redato/redato_system_prompt.md`). Para produção, precisa virar um arquivo TypeScript que exporte strings estruturadas.

### Arquivos de referência

- `docs/redato/redato_system_prompt.md` — fonte canônica
- `docs/redato/redato_apendices.md` — dados concretos (Palavras do Dia, personagens, temas)

### O que fazer

Criar `src/lib/prompts/system-prompt.ts` com:

```typescript
// Parte A — prompt base (identidade, tom, rubrica, modos, calibração)
export const SYSTEM_PROMPT_BASE: string = `...`;

// Parte B — contextos por atividade (43 códigos)
export const ACTIVITY_CONTEXTS: Record<ActivityCode, ActivityContext> = {
  "RJ1·OF02·MF": { ... },
  "RJ1·OF04·MF": { ... },
  // ... todos os 43 códigos
};

// Função de montagem final
export function buildSystemPrompt(code: ActivityCode): string {
  const context = ACTIVITY_CONTEXTS[code];
  return `${SYSTEM_PROMPT_BASE}\n\n## Contexto desta atividade\n\n${formatContext(context)}`;
}
```

### Critérios de aceitação

- [ ] Todo o conteúdo da Parte A do markdown está em `SYSTEM_PROMPT_BASE`
- [ ] Todos os 43 códigos da Parte B estão em `ACTIVITY_CONTEXTS`
- [ ] Função `buildSystemPrompt` retorna prompt válido para qualquer código
- [ ] Testes unitários validam que prompt montado não excede 15k tokens
- [ ] Tipagem `ActivityCode` está definida como union type literal

### Notas

- **Não hardcodar texto dentro do TS.** Se puder ler o markdown em build-time e converter, melhor (facilita manutenção).
- **Versionar o prompt.** Adicionar constante `PROMPT_VERSION` exportada para rastreabilidade.

---

## Tarefa 2 — Implementar schemas Zod para cada modo

**Prioridade:** Alta (depende de tarefa 1)

### Contexto

A Redato tem 6 modos com schemas JSON distintos (documentados em `redato_system_prompt.md` Parte C e exemplificados em `redato_exemplos_correcao.md`). Cada modo precisa de:

1. Tipagem TypeScript
2. Validador Zod para runtime
3. Parser que converte JSON da Claude API em objeto tipado

### Arquivos de referência

- `docs/redato/redato_system_prompt.md` Parte C (schemas canônicos)
- `docs/redato/redato_exemplos_correcao.md` (exemplos válidos de cada modo)

### O que fazer

Criar um arquivo por modo em `src/lib/schemas/`:

```typescript
// src/lib/schemas/correcao-completa.ts
import { z } from 'zod';

export const CorrecaoCompletaSchema = z.object({
  tipo: z.literal('correcao_completa'),
  codigo_atividade: z.string(),
  aluno_id: z.string(),
  tema_detectado: z.string().optional(),
  linhas_estimadas: z.number().optional(),
  notas: z.object({
    c1: z.number().refine(n => [0, 40, 80, 120, 160, 200].includes(n)),
    c2: z.number().refine(n => [0, 40, 80, 120, 160, 200].includes(n)),
    c3: z.number().refine(n => [0, 40, 80, 120, 160, 200].includes(n)),
    c4: z.number().refine(n => [0, 40, 80, 120, 160, 200].includes(n)),
    c5: z.number().refine(n => [0, 40, 80, 120, 160, 200].includes(n)),
    total: z.number().min(0).max(1000),
  }),
  // ... continua
});

export type CorrecaoCompleta = z.infer<typeof CorrecaoCompletaSchema>;
```

Repetir para: `foco_competencia`, `foco_duplo`, `correcao_reescrita_turno1`, `correcao_reescrita_turno2`, `chat`.

### Critérios de aceitação

- [ ] Cada um dos 6 schemas é validado contra os exemplos do `redato_exemplos_correcao.md` (devem passar)
- [ ] Notas individuais só aceitam valores discretos da escala INEP (0, 40, 80, 120, 160, 200)
- [ ] Nota total é soma das 5 individuais (validação cruzada)
- [ ] Parser tenta recuperar JSONs malformados (falta de vírgula, aspas extras) antes de falhar

### Notas importantes

- **A escala é discreta.** Não aceitar notas intermediárias como 150 ou 175. Se a Claude retornar 150, tratar como erro e rejuvaliar ou arredondar para nível mais próximo.
- **Total deve bater.** Se `notas.total !== c1+c2+c3+c4+c5`, é erro de LLM — log warning e corrigir recalculando.

---

## Tarefa 3 — Cliente da Claude API com streaming

**Prioridade:** Alta (depende de tarefas 1 e 2)

### Contexto

A Redato faz chamadas à API da Claude Sonnet 4.6 (modelo atual mais adequado). As correções são textos longos (JSON estruturado com feedback detalhado), portanto streaming é essencial para UX.

### Arquivos de referência

- Docs oficiais Claude API: https://docs.claude.com/en/api/messages
- `docs/redato/redato_exemplos_correcao.md` — formato esperado de saída

### O que fazer

Criar `src/lib/api/claude-client.ts`:

```typescript
import Anthropic from '@anthropic-ai/sdk';
import { buildSystemPrompt } from '../prompts/system-prompt';
import { validateResponse } from '../schemas';

const client = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY!,
});

export async function correctEssay(params: {
  code: ActivityCode;
  studentId: string;
  essayText: string;
  onToken?: (token: string) => void; // para streaming
}) {
  const systemPrompt = buildSystemPrompt(params.code);
  
  const stream = await client.messages.stream({
    model: 'claude-sonnet-4-6',
    max_tokens: 4096,
    system: systemPrompt,
    messages: [
      {
        role: 'user',
        content: buildUserMessage(params.studentId, params.essayText),
      },
    ],
  });

  let fullText = '';
  for await (const chunk of stream) {
    if (chunk.type === 'content_block_delta' && chunk.delta.type === 'text_delta') {
      fullText += chunk.delta.text;
      params.onToken?.(chunk.delta.text);
    }
  }

  return validateResponse(params.code, fullText);
}
```

### Critérios de aceitação

- [ ] Suporta streaming de tokens (onToken callback funciona)
- [ ] Retry automático em erro de rate limit (3 tentativas com exponential backoff)
- [ ] Timeout de 90 segundos por chamada
- [ ] Logs estruturados (código, aluno_id, tempo total, tokens consumidos)
- [ ] Validação via schema Zod antes de retornar ao caller
- [ ] Tratamento de erro específico para JSON malformado (tenta reparar 1x antes de falhar)

### Notas

- **Custo.** Sonnet 4.6 tem pricing específico; acompanhar consumo por correção. Alvo: R$ 0,30-0,50 por redação completa.
- **Cache.** Considerar prompt caching da Anthropic para o system prompt (ele é fixo para cada código de atividade, 10k+ tokens, se beneficia muito de cache).
- **Modelo.** Usar o modelo literal `claude-sonnet-4-6` (verificar nome exato vigente na doc da Anthropic antes de hardcodar).

---

## Tarefa 4 — Pipeline de OCR para redações manuscritas

**Prioridade:** Média

### Contexto

Alunos frequentemente escrevem redações à mão no papel. O professor fotografa e sobe na Redato. O sistema precisa extrair o texto via OCR antes de mandar para a Claude.

### Arquivos de referência

- Docs Google Cloud Vision API
- `docs/redato/redato_apendices.md` — glossário de termos específicos do programa (para pós-processamento do OCR)

### O que fazer

Criar `src/lib/api/ocr.ts` que:

1. Recebe imagem (PNG, JPG, HEIC)
2. Envia para Google Cloud Vision API
3. Aplica pós-processamento específico para português escolar:
   - Correção de tremidos ("1h" → "n")
   - Preservação de parágrafos
   - Contagem de linhas (crítico para checar limite de 7 linhas da nota zero)

### Critérios de aceitação

- [ ] Taxa de acerto ≥ 95% em amostras de teste (manuscritos do programa)
- [ ] Preserva quebras de parágrafo
- [ ] Retorna também número de linhas detectadas
- [ ] Fallback gracioso se Vision API indisponível (aceitar digitação manual)

---

## Tarefa 5 — Testes de regressão usando exemplos validados

**Prioridade:** Alta (qualidade crítica)

### Contexto

O arquivo `redato_exemplos_correcao.md` contém 7 exemplos de saídas JSON validadas, cada um correspondendo a um modo de operação. Esses exemplos são fixtures de teste.

### Arquivos de referência

- `docs/redato/redato_exemplos_correcao.md` — fixtures
- `docs/redato/redato_calibragem_competencias.md` — exemplos contra-intuitivos para testar armadilhas específicas

### O que fazer

Criar `src/tests/regression/redato-correcao.test.ts`:

```typescript
import { parseExamples } from '../utils/markdown-examples';
import { correctEssay } from '@/lib/api/claude-client';

const examples = parseExamples('docs/redato/redato_exemplos_correcao.md');

describe('Redato regression', () => {
  examples.forEach((example) => {
    it(`matches expected output for ${example.title}`, async () => {
      const result = await correctEssay({
        code: example.code,
        studentId: example.student_id,
        essayText: example.essay,
      });

      // Comparações tolerantes (Claude não é determinístico)
      expect(result.tipo).toBe(example.expected.tipo);
      expect(result.codigo_atividade).toBe(example.expected.codigo_atividade);

      // Notas permitem variação de ±1 nível (40 pontos)
      if ('notas' in result && 'notas' in example.expected) {
        expect(Math.abs(result.notas.c1 - example.expected.notas.c1)).toBeLessThanOrEqual(40);
        // ... outras competências
      }
    });
  });
});
```

### Critérios de aceitação

- [ ] Todos os 7 exemplos passam consistentemente
- [ ] Teste especial para o **Exemplo 2b** (calibração de aposição em C5) — este é o canário da calibração
- [ ] Rodado em CI a cada PR
- [ ] Relatório de drift (quanto a saída real divergiu da esperada) em cada execução

### Notas

- **Não é determinístico.** Claude pode variar nota de uma competência em ±1 nível (40 pontos) entre execuções. Testes devem tolerar isso.
- **Exemplo 2b é crítico.** Se a Redato der menos de 200 em C5 para o parágrafo que termina em "adolescentes do ensino médio da rede pública", há problema de calibração — bloquear deploy.

---

## Tarefa 6 — Modelo de dados (Prisma)

**Prioridade:** Média (depende da direção do produto)

### Contexto

Precisamos persistir correções para:
- Histórico do aluno (progressão)
- Dashboard do professor
- Análise pedagógica agregada

### O que fazer

Propor schema Prisma para:

```prisma
model Student {
  id          String   @id
  name        String
  grade       String   // "1S", "2S", "3S"
  classId     String
  class       Class    @relation(fields: [classId], references: [id])
  corrections Correction[]
}

model Correction {
  id              String   @id @default(cuid())
  studentId       String
  student         Student  @relation(fields: [studentId], references: [id])
  activityCode    String   // "RJ3·OF09·MF"
  mode            String   // "correcao_completa", "foco_competencia", etc.
  essayText       String   @db.Text
  essayLines      Int?     // linhas detectadas
  response        Json     // JSON completo retornado pela Redato
  notaC1          Int?
  notaC2          Int?
  notaC3          Int?
  notaC4          Int?
  notaC5          Int?
  notaTotal       Int?
  createdAt       DateTime @default(now())
  correctionTime  Int      // ms
  tokensUsed      Int?
  promptVersion   String   // para rastreabilidade
}

model Class {
  id        String    @id
  name      String
  teacherId String
  students  Student[]
  school    String
}
```

### Critérios de aceitação

- [ ] Migrations funcionando (dev e produção)
- [ ] Queries de dashboard (distribuição de notas por turma, progressão individual) rodando em < 500ms
- [ ] Campos de notas indexados para agregação rápida
- [ ] Soft delete (não apagar correções, marcar como arquivada)

---

## Tarefa 7 — Destilação da calibração para o system prompt ✅ CONCLUÍDA

**Status:** Feito na v1.3 do system prompt (abril 2026).

### O que foi entregue

A Seção 6 "Calibração operacional" foi adicionada ao `docs/redato/redato_system_prompt.md`, destilando o conteúdo de `redato_calibragem_competencias.md` em ~3k tokens.

### Estrutura da seção

- **6.1** Princípio geral — "Na dúvida, vá para o nível superior"
- **6.2** Escala discreta — só 0, 40, 80, 120, 160, 200
- **6.3** Ordem de verificação (nota zero antes de competências)
- **6.4** Mudanças críticas 2025 (C4 qualitativo, C5 ação=-120, C2-C3 dialogando)
- **6.5** Calibração por competência (C1, C2, C3, C4, C5) — cada uma com falsos-negativos típicos
- **6.6** Exemplos-canário de calibração correta
- **6.7** 8 heurísticas resumidas

### Para a implementação TypeScript (Tarefa 1)

A Parte A do system prompt agora inclui a Seção 6. Ao implementar `buildSystemPrompt()`, **não separe** a calibração do resto da Parte A — ela é parte do comportamento base da Redato em todas as chamadas.

**Arquitetura final:**
```
Parte A (~11k tokens, sempre enviado):
  1. Identidade e papel
  2. Tom e voz
  3. Contexto do programa
  4. Estrutura canônica das oficinas
  5. Rubrica oficial ENEM
  6. Calibração operacional (NEW v1.3)
  7. Modos de operação (era 6, renumerado)
  8. Comportamento em casos-limite (era 7)
  9. Restrições éticas (era 8)
```

### Teste de regressão crítico

Após implementar a Tarefa 1 com o prompt v1.3, executar o **Exemplo 2b** do `redato_exemplos_correcao.md` (o canário de C5). A Redato deve retornar C5 = 200 para aquele parágrafo com aposição "órgão responsável pela formulação e coordenação do SUS". Se der menos de 200, há bug de calibração — não fazer deploy.

---

## Tarefa 8 — Dashboard do professor

**Prioridade:** Média (product-dependent)

### Contexto

Professores precisam ver:
- Turma como um todo: distribuição de notas, competências fracas
- Aluno individual: progressão ao longo do ano, evolução por competência
- Comparação entre oficinas (antes/depois)

### O que fazer

Páginas em `src/app/professor/`:

- `/professor/turmas/[classId]` — visão geral da turma
- `/professor/alunos/[studentId]` — detalhe individual
- `/professor/oficinas/[code]` — resultados de uma MF específica

### Critérios de aceitação

- [ ] Gráfico de distribuição de notas (histograma por competência)
- [ ] Comparação progressão: primeira vs última correção do aluno
- [ ] Filtros: por turma, por oficina, por competência
- [ ] Export CSV para análise externa

---

## Dependências entre tarefas

```
✅ Tarefa 7 (destilação calibração) — JÁ FEITA (integrada ao prompt v1.3)

Tarefa 1 (prompt TS, inclui calibração já destilada)
    └──▶ Tarefa 2 (schemas)
            └──▶ Tarefa 3 (API client)
                    └──▶ Tarefa 5 (testes regressão) ⬅ valida calibração
                    └──▶ Tarefa 6 (modelo dados)
                            └──▶ Tarefa 8 (dashboard)

Tarefa 4 (OCR) — independente, pode ser em paralelo
```

## Ordem sugerida de execução

*Tarefa 7 (destilação da calibração) já está concluída e refletida no system prompt v1.3.*

1. **Tarefa 1** — system prompt em TS (base de tudo, já inclui a calibração)
2. **Tarefa 2** — schemas Zod (base da tipagem)
3. **Tarefa 3** — API client (core do backend)
4. **Tarefa 5** — testes de regressão (valida 1-3, com atenção especial ao Exemplo 2b — canário de C5)
5. **Tarefa 6** — modelo de dados (persistência)
6. **Tarefa 4** — OCR (feature paralela, pode começar em paralelo com 1)
7. **Tarefa 8** — dashboard (última, depende de dados acumulados)

## Checkpoints pedagógicos

Algumas mudanças precisam de aprovação do autor (Daniel), não só code review técnico:

- **Qualquer modificação do system prompt** (`redato_system_prompt.md`)
- **Qualquer modificação da calibração** (`redato_calibragem_competencias.md`)
- **Texto de feedback** em exemplos ou em prompts
- **Lista de códigos de atividade** (adicionar/remover/renomear)
- **Mapeamento código → modo de operação**

Esses arquivos são **fonte-de-verdade pedagógica**. Mudanças neles passam por revisão antes do merge.

## Referência rápida dos documentos

| Quero... | Leio... |
|---|---|
| Entender comportamento da IA | `docs/redato/redato_system_prompt.md` |
| Saber o que tem em cada atividade | `docs/redato/redato_apendices.md` |
| Ver exemplo de saída esperada | `docs/redato/redato_exemplos_correcao.md` |
| Calibrar uma competência específica | `docs/redato/redato_calibragem_competencias.md` |
| Decidir estrutura do código | `CLAUDE.md` + este arquivo |

---

*Versão 1.0 · abril de 2026*
