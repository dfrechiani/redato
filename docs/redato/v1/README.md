# Redato — Calibration set

8 redações-canário com gabarito fechado, usadas como **regressão** a cada mudança
no system prompt / schema / modelo. Cada canário isola um viés específico da
LLM corretora; falha em 2+ canários bloqueia deploy.

## Arquivos

- [`canarios.yaml`](canarios.yaml) — fonte da verdade. Cada entrada tem
  `id`, `function`, `bias_detected`, `essay`, `gabarito` e `structural_checks`.
- [`schema_and_fewshots.md`](schema_and_fewshots.md) — especificação do schema
  auditado, few-shots trabalhados e regras de validação.

## Como rodar

```bash
cd backend/notamil-backend
REDATO_DEV_OFFLINE=1 python ../../scripts/run_calibration_eval.py
```

- Sem flags: roda a suíte completa (8 canários, ~6 min, ~US$ 0,40 em API).
- `--baseline`: salva `baseline_YYYY-MM-DD.json`.
- `--only c1_seven_graves`: roda apenas um canário específico.
- `--compare baseline.json`: reporta delta vs baseline.
- Exit code `1` se ≥ 2 canários falharem.

## Tolerância

- **Numérica:** ±40 pontos (1 nível INEP) por competência.
- **Estrutural:** cada canário declara checagens específicas (ex.: C1 deve
  reportar ≥ 6 desvios graves). Todas precisam passar.

## Quando adicionar um canário novo

Sempre que um revisor humano pegar um miss da LLM em produção:

1. Transforma a redação + gabarito em uma entrada do YAML com `bias_detected`.
2. Roda `run_calibration_eval.py --only <novo_id>` — confirma que falha hoje.
3. Patcha o prompt (ou schema, ou few-shot).
4. Roda a suíte completa — confirma que o novo canário passa SEM regredir os outros.
5. Faz commit das duas mudanças (yaml + patch) juntas.

Isso troca o ciclo reativo "miss → patch" por "miss → canário → eval → patch testado".

## Limites conhecidos

- Todos os canários são sobre um único tema (redes sociais). Em produção,
  expandir para 2-3 temas adicionais pra garantir que os viés detectados são
  competency-level, não tema-específicos.
- Não-determinismo do Claude: uma mesma redação pode variar ±1 nível entre
  execuções. A tolerância de 40 pontos absorve essa variância.
