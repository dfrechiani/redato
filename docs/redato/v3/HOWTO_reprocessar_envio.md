# HOWTO — Reprocessar avaliação de envio

**Endpoint:** `POST /portal/envios/{envio_id}/reprocessar`
**UI:** botão "Reprocessar avaliação" na tela de detalhe do envio
(`/atividade/{atividade_id}/aluno/{aluno_id}`).

## Quando usar

O botão aparece pro professor da turma (ou coordenador da escola)
quando o envio tem **correção falha** detectada por uma destas
condições:

1. **`raw_output` é null** — pipeline nunca rodou ou foi nullado.
2. **`raw_output.error` está setado** — pipeline rodou mas falhou
   (timeout do FT, parser fail, exception silenciada como o bug do
   `google.cloud` corrigido em `61137b0`).
3. **`nota_total` é null com texto OCR presente** — caso real do bug
   pré-fix `eb5ddc9`: FT BTBOS5VF emitia 5 cN_audit válidos mas omitia
   `nota_total`, e portal lia o campo direto sem fallback de soma.
   Resultado no portal: "Nota total: __/1000".

O botão **não aparece** quando:
- Aluno ainda não enviou nada (`enviado_em is null`)
- Professor está vendo tentativa anterior (M9.6 — evita confusão sobre
  qual versão é reprocessada)
- Correção está OK (`nota_total` preenchido, sem `error` no raw_output)

## O que faz

1. Carrega o envio do Postgres.
2. Pega o `texto_transcrito` da `Interaction` ligada ao envio
   (interaction_id). Se não tem texto, retorna 400 — peça pro aluno
   reenviar a foto.
3. Roteia via `resolve_mode(activity_id)`:
   - `COMPLETO_INTEGRAL` (OF14) ou modo desconhecido → chama
     `_claude_grade_essay` (que tem fallback FT → Claude com
     graceful degradation).
   - `FOCO_C2/C3/C4/C5`, `COMPLETO_PARCIAL`, etc. → chama
     `grade_mission`.
4. Faz **UPDATE** do `interaction.redato_output` com o novo `tool_args`
   — não cria nova `tentativa_n` (é correção da mesma tentativa).
5. Loga `reprocessing envio %s` no início e `reprocess of envio %s
   done in %dms` no fim. Falha do pipeline gera `logger.exception`.
6. Persiste audit log em `data/portal/audit_log.jsonl` com
   `event=envio_reprocessado, actor_id, modo, elapsed_ms`.

## Comportamento em falhas

- **Sem permissão** (professor de outra turma): 403.
- **Envio inexistente**: 404.
- **Sem texto OCR**: 400 com mensagem orientando o professor.
- **Pipeline falha** (timeout, parser, etc.): retorna **200** com
  `{"ok": false, "error": "..."}`. Status HTTP é 200 porque a falha
  é do conteúdo, não do endpoint. Frontend mostra toast e mantém
  estado anterior.

## Caso de uso típico (caso real, 01/05/2026)

1. Daniel mandou redação OF14 às 15:48 — envio
   `wpp_+556196668856_1777681092`.
2. FT BTBOS5VF retornou 5 cN_audit válidos mas omitiu `nota_total`.
3. Portal mostrava `"Nota total: __/1000"` em vez de `640/1000`.
4. Após o fix `eb5ddc9` (FT calcula soma canônica), correções novas
   já vêm com `nota_total`. Mas o envio antigo continuou com
   `nota_total=null` no banco.
5. Com este endpoint, professor clica "Reprocessar avaliação" no
   detalhe do envio. Backend reroda o pipeline, FT já popula
   `nota_total=640`, portal renderiza corretamente.

Sem esse botão, a única alternativa era pedir o aluno reenviar a foto
via WhatsApp — fluxo frágil porque depende do aluno responder.

## Limitações conhecidas

- Reprocessar **substitui** a correção anterior. Não há histórico da
  versão antiga — quem quiser auditar precisa do `audit_log.jsonl` ou
  Railway logs (`elapsed_ms` + timestamp ficam lá).
- Tema usado é `"Tema livre (foto enviada via WhatsApp)"` — mesmo
  hardcoded do bot. Não puxa tema da atividade (não há tema rico no
  schema atual).
- Não permite reprocessar versão antiga (M9.6 `tentativa_n` < máxima).
  Se professor quiser, precisa primeiro voltar pra mais recente.
- BQ-stub e Firestore-stash em `_claude_grade_essay` ficam silenciosos
  em prod sem GCP (já tratados em `61137b0`). Reprocessar não regride
  essa parte.
