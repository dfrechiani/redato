# HOWTO — Mapeamento descritores → BNCC EM-LP (Fase 5A.2)

**Atualizado:** 2026-05-04

## O que é

Fase 5A.2 cruza os 40 descritores observáveis (Fase 1) com as 54
habilidades BNCC do Ensino Médio — Língua Portuguesa
(EM13LP01-EM13LP54). Pra cada descritor, identifica 1-3 habilidades
BNCC trabalhadas + intensidade + justificativa.

Output: [`mapeamento_descritores_bncc.json`](mapeamento_descritores_bncc.json),
arquivo estático committed no repo. Endpoint `/perfil` lê em
runtime (cache mtime) e enriquece cada lacuna prioritária com a
4ª seção "📋 BNCC".

Uso pedagógico:
- Justificar intervenções para coordenação/escola ("trabalhar
  C5.001 cobre EM13LP29 (produção argumentativa) e EM13LP41")
- Mapear lacunas a habilidades do currículo oficial pra relatórios
  de gestão
- Vincular Redato à BNCC pra prova de conformidade pedagógica

## Status atual: pipeline pronto, geração pendente

Pipeline LLM completo + tests verdes + integração frontend feita.
**JSON ainda não foi gerado** porque sessão de implementação não
tinha `OPENAI_API_KEY`. Placeholder committado com:

```json
{
  "versao": "1.0",
  "status": "nao_gerado_ainda",
  "mapeamentos": []
}
```

UI degrada graciosamente: card de lacuna NÃO mostra a 4ª seção
"📋 BNCC" enquanto JSON estiver com `status="nao_gerado_ainda"`.
Após Daniel rodar o pipeline, status vira `"em_revisao"` e a
seção aparece automaticamente.

## Como rodar o pipeline

```bash
cd backend/notamil-backend
export OPENAI_API_KEY=sk-...
python -m redato_backend.diagnostico.scripts.gerar_mapeamento_bncc
```

Custo estimado: **~$0.40** (40 descritores × ~$0.01 cada).
Latência: **~3 min** (~5s/descritor).

Saída:
```
docs/redato/v3/diagnostico/mapeamento_descritores_bncc.json
```

Sem `--heuristic`: não tem fallback porque heurística keyword-match
sobre BNCC seria muito imprecisa (descrições oficiais usam linguagem
técnica). Melhor falhar barulhento sem chave do que produzir
mapeamento ruim.

### Sincronização do JSON pro Docker

Após gerar:
```bash
cp docs/redato/v3/diagnostico/mapeamento_descritores_bncc.json \
   backend/notamil-backend/redato_backend/diagnostico/mapeamento_descritores_bncc.json
```

Mesmo padrão da Fase 5A.1. Bundle dentro do package garante que o
Docker `COPY . .` cobre.

### Commit do upgrade

```bash
git add docs/redato/v3/diagnostico/mapeamento_descritores_bncc.json \
        backend/notamil-backend/redato_backend/diagnostico/mapeamento_descritores_bncc.json
git commit -m "chore(diagnostico): gera mapeamento BNCC via LLM"
git push
```

## Arquitetura

```
descritores.yaml (Fase 1, 40 descritores)
        │
        ▼
mapeador_bncc.py
  - tool_use forçado
  - schema com enum BNCC_LP_EM (54 códigos)
  - validação dupla (OpenAI + Python)
        │
        ▼
scripts/gerar_mapeamento_bncc.py
  - itera 40 descritores
  - acumula 40 mapeamentos
  - persiste em JSON
        │
        ▼
docs/.../mapeamento_descritores_bncc.json
        │
        │ lido em runtime (cache mtime)
        ▼
bncc.py
  - get_habilidades_bncc_por_descritor(id) → lista habs
  - get_descritores_por_habilidade_bncc(cod) → lista descs (inversa)
        │
        ▼
GET /portal/turmas/{id}/alunos/{aluno_id}/perfil
  → diagnostico_recente.professor.lacunas_enriquecidas[].habilidades_bncc
```

## Catálogo BNCC EM-LP (referência)

`bncc_referencia.py` lista as 54 habilidades organizadas por eixos:

- **Todas as práticas** (LP01-LP07): habilidades transversais
- **Leitura** (LP08-LP18): compreensão e análise de textos
- **Produção de textos** (LP19-LP31): escrita e revisão
- **Análise linguística/semiótica** (LP32-LP46): metalinguagem
- **Oralidade** (LP47-LP54): práticas orais formais

⚠️ **As descrições no `bncc_referencia.py` são RESUMIDAS** (1-2
frases por habilidade) — versão completa da BNCC tem desdobramentos
extras. A versão aqui mantém o núcleo da habilidade pra caber em UI
e prompts. Verificar contra texto oficial INEP/BNCC antes de usar
em material pedagógico publicado oficialmente.

Códigos fora do range LP01-LP54 (ex.: `EM13LGG101`, `EM13LGG701`)
pertencem ao componente **Linguagens GERAL** — fora do escopo da
nossa referência. O mapeador `is_codigo_valido()` rejeita esses
códigos pra evitar contaminação.

## Schema do JSON

```json
{
  "versao": "1.0",
  "gerado_em": "2026-05-04T...",
  "modelo_usado": "gpt-4.1-2025-04-14",
  "status": "em_revisao" | "revisado" | "nao_gerado_ainda",
  "estatisticas": {
    "total_descritores": 40,
    "mapeamentos_ok": 40,
    "mapeamentos_falhos": 0,
    "total_atribuicoes": 95,
    "habilidades_unicas": 30,
    "custo_total_usd": 0.40,
    "latencia_total_min": 2.8
  },
  "mapeamentos": [
    {
      "descritor_id": "C1.005",
      "descritor_nome": "Concordância (verbal e nominal)",
      "descritor_competencia": "C1",
      "habilidades_bncc": [
        {
          "codigo": "EM13LP02",
          "intensidade": "alta",
          "razao": "Descritor trabalha concordância verbal/nominal..."
        },
        ...
      ],
      "area": "Linguagens, Códigos e suas Tecnologias",
      "componente": "Língua Portuguesa",
      "modelo_usado": "gpt-4.1-2025-04-14",
      "latencia_ms": 5012,
      "custo_estimado_usd": 0.0098,
      "input_tokens": 4200,
      "output_tokens": 180,
      "mapeamento_falhou": false
    },
    ... 40 entries
  ]
}
```

## Como Daniel revisa (Fase 5A.2.review)

Workflow proposto:

1. **Inspeção do JSON**: roda script que imprime, pra cada descritor,
   `nome + top habilidades + razões`. Daniel passa olho.
2. **Substituições manuais**: edita entries individuais quando LLM
   atribuiu habilidade errada (ex.: descritor de C5 mapeou pra
   habilidade de leitura).
3. **Re-rodar pipeline em problemáticas**: se >5 erros, ajusta
   prompt do `mapeador_bncc.py` e re-roda só nos descritores
   afetados.
4. **Mudar status**: `"em_revisao"` → `"revisado"`. UI deixa de
   mostrar aviso de revisão.
5. **Commit + push** PR dedicado: `docs(diagnostico): Fase 5A.2.review`.

## Como o frontend consome

Endpoint `GET /portal/turmas/{turma_id}/alunos/{aluno_turma_id}/perfil`
retorna em cada `lacunas_enriquecidas[i]`:

```json
{
  "id": "C1.005",
  "nome": "Concordância (verbal e nominal)",
  ...
  "habilidades_bncc": [
    {
      "codigo": "EM13LP02",
      "intensidade": "alta",
      "razao": "...",
      "descricao": "Estabelecer relações entre as partes do texto..."
    }
  ]
}
```

UI (`MapaCognitivo.tsx`) renderiza 4ª seção compacta no card:

```
📋 BNCC (em revisão)
EM13LP02 (alta), EM13LP38 (media)
```

Hover/touch no código mostra `descricao` + intensidade + razão via
HTML `title` attribute. Lista vazia = seção não aparece (estado
gracioso).

## Limitações conhecidas

- **Descrições resumidas**: não são texto integral da BNCC. Pra
  publicação pedagógica oficial, verificar contra documento da
  base.

- **Sem componente Linguagens GERAL**: códigos `EM13LGG*` (LP01-LP07
  têm versões LGG transversais a Educação Física, Arte, LP) ficam
  fora. Se virar requisito, expandir `bncc_referencia.py` pra
  incluir EM13LGG.

- **Mapeamento determinístico**: mesmo descritor sempre tem mesmas
  habilidades atribuídas (até a próxima revisão pedagógica). Não
  personaliza por aluno/turma — é metadata estática.

- **Heurístico não disponível**: diferente de Fase 5A.1
  (`--heuristic`), aqui não há fallback sem LLM. BNCC tem linguagem
  técnica que keyword-match não capturaria fielmente.

- **Re-rodar pipeline é manual**: igual Fase 5A.1, sem trigger
  automático. Daniel decide quando upgradear (catálogo BNCC mudar,
  prompt melhorar).

## Tests

`backend/notamil-backend/redato_backend/tests/diagnostico/test_bncc.py`
(12 cenários):

- catálogo: 54 habilidades + descrições não-vazias
- mapeador LLM: schema válido, max 3 habilidades, código inválido
  (EM13LP99), código LGG rejeitado
- helpers: lookup direto + inverso, status placeholder
- pipeline: sem API key sai com código 2
- endpoint: schema aceita habilidades_bncc + smoke estrutural

Total: 12 cenários novos. Suite global vai de 588 → 600.

## Deploy checklist

Sem migration nova — Fase 5A.2 é puramente leitura + JSON estático.

1. Push aciona deploy automático (Railway)
2. JSON placeholder está no repo + bundle no package — Docker COPY
   já cobre. UI degrada graciosamente (sem 4ª seção)
3. Smoke pós-deploy: `/turma/{id}/aluno/{id}` continua funcionando
   (cards de lacuna sem a seção BNCC, status='nao_gerado_ainda')
4. Pra ATIVAR: Daniel roda pipeline localmente, copia JSON pro
   bundle, commita, push. UI passa a mostrar a 4ª seção.

Em caso de problema (JSON corrompido após geração):
- Endpoint cai gracioso: `habilidades_bncc: []` em todas as lacunas
- UI esconde a 4ª seção (lista vazia → não renderiza)
- Reverter JSON pro placeholder via `git checkout` no arquivo
