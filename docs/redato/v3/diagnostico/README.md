# Diagnóstico cognitivo de redação ENEM

**Atualizado:** 2026-05-03 · Fase 3 (visualização)

## Contexto e objetivo

Hoje o pipeline da Redato avalia uma redação e produz `redato_output`
(notas C1-C5, faixas, detectores, análise pedagógica). Isso responde
"que nota o aluno tirou", mas não responde **"o que especificamente
o aluno não domina"** — o que o professor precisa saber pra orientar
intervenção e pra recomendar conteúdo de reforço.

O sistema de diagnóstico cognitivo, a partir de `redato_output` + texto
da redação, infere **lacunas pedagógicas específicas**. Cada redação
gera uma lista de descritores violados (ex.: "C3.007 — Defesa de ponto
de vista"), com confiança e evidência textual.

Pipeline em 5 fases:

| Fase | Entregável |
|---|---|
| **1** Descritores | YAML com 40 descritores observáveis INEP-aligned (este diretório) |
| 2 Inferência LLM | Prompt + endpoint que recebe redação e devolve lista de lacunas |
| 3 Storage | Persistência das lacunas inferidas + agregação por aluno/turma |
| 4 UI | Visualização das lacunas no perfil do aluno (drill da nota → lacuna específica) |
| 5 Recomendação | Bridge lacuna → conteúdo de reforço (oficina/exercício do livro) |

Esta Fase 1 é puramente **documentação estruturada**. Não toca em
backend, frontend ou pipeline.

## Por que lista de descritores e não árvore hierárquica

Cogitamos 3 modelos:

1. **Árvore hierárquica** (Q-Matrix em CDM): nós com pré-requisitos.
   Permite inferir "aluno não domina X porque não domina Y, que é
   pré-requisito". Conceitualmente elegante, dolorido na prática:
   pré-requisitos pedagógicos em redação não são limpos (C3 não
   precede C4 cleanly), e qualquer alteração na árvore exige
   re-validação de todos os links.

2. **Rubrica plana INEP** (5 competências × 5 níveis): o que já temos.
   Bom pra calibração de nota; ruim pra diagnóstico — "C3 nível 3"
   não diz o que falta especificamente.

3. **Lista de descritores observáveis** (escolhido): 40 descritores
   plain, agrupados por competência, sem dependências. Cada descritor
   é binário (presente / ausente / parcial) e tem definição operacional.

A escolha pela lista vem de:

- **Tandfonline 2019** ("A descriptor-based framework for analytic
  writing assessment"): demonstra que 21 descritores observáveis
  cobrem 88% da variância de avaliadores humanos em writing assessment,
  superando rubricas hierárquicas em consistência inter-rater.
- **Language Bottleneck Models 2025** (van der Schaar Lab): trabalho
  recente em diagnostic NLP usa LBM (Language Bottleneck Models) com
  descritores observáveis em vez de árvores latentes. Argumento
  central: LLM cobre nuance qualitativa por descritor; árvore vira
  débito técnico sem ganho preditivo claro.
- **Manutenibilidade**: lista plana é fácil de revisar, versionar e
  estender. Nova categoria entra como novo descritor (próximo número
  livre na competência), sem refactor de pré-requisitos.

## Modelo escolhido

40 descritores, 8 por competência. ID formato `C{n}.{nnn}`:

| Competência | Cobertura |
|---|---|
| **C1** Norma culta | sintaxe, acentuação, ortografia, pontuação, concordância, regência, registro, vocabulário |
| **C2** Compreensão da proposta | tema, recorte, tipo textual, repertório (presença/pertinência/uso/legitimidade) |
| **C3** Argumentação | tese, sustentação, tópico frasal, profundidade, diversidade, articulação, defesa, autoria |
| **C4** Coesão textual | conectivos (variedade/semântica/transição), referenciação, progressão, articulação |
| **C5** Proposta de intervenção | 5 elementos canônicos (agente/ação/meio/finalidade/detalhamento) + articulação + DH + completude |

Cada descritor tem 7 campos obrigatórios:

- `id` — identificador único `C{n}.{nnn}`
- `competencia` — código INEP `C1..C5`
- `categoria_inep` — subdivisão oficial INEP da competência (ex.:
  "Estrutura sintática", "Repertório", "5 elementos da proposta")
- `nome` — rótulo curto humano (4-8 palavras)
- `definicao` — definição operacional 1-3 linhas
- `indicador_lacuna` — como detectar quando aluno NÃO domina
- `exemplo_lacuna` — trecho de redação ilustrando o erro

## Como o YAML é consumido (Fase 2 — implementado)

Pipeline em `redato_backend/diagnostico/`:

```python
from redato_backend.diagnostico.inferencia import inferir_diagnostico

resultado = inferir_diagnostico(
    texto_redacao=texto_ocr,
    redato_output=tool_args,            # cN_audit do FT/Claude
    tema="Tema da proposta",
)
# resultado: dict com 40 descritores classificados (dominio/lacuna/incerto)
# + evidências + lacunas_prioritarias + resumo_qualitativo + recomendacao_breve
# Ver docs/redato/v3/diagnostico/HOWTO_inferencia.md pro schema completo.
```

Storage: coluna nova `envios.diagnostico` (JSONB nullable, migration
`k0a1b2c3d4e5_envios_diagnostico`). Não-bloqueante — falha do
pipeline OpenAI não derruba a entrega da correção ao aluno.

Visibilidade:
- **Aluno**: invisível (frontend ignora a coluna).
- **Professor**: visível no perfil do aluno (Fase 3 entrega UI).

Detalhes operacionais (modelo, custo, env vars, retry endpoint) em
[`HOWTO_inferencia.md`](HOWTO_inferencia.md).

## Fontes de verdade INEP

Os campos `categoria_inep` mapeiam pra subdivisões oficiais da Matriz
de Referência do ENEM 2024-2025. Quando INEP usa termo específico
(ex.: "repertório de bolso" pra referências genéricas tipo "estudos
mostram"), preservamos o termo. Quando o nome do descritor diverge
levemente do INEP (ex.: "Defesa de ponto de vista" vs subcritério
INEP "Posicionamento"), priorizamos o nome operacional pra clareza
do professor — o `categoria_inep` mantém a rastreabilidade.

## Limitações conhecidas

- **Sem pré-requisitos modelados.** Aluno que falha em "C3.001 —
  Existência da tese" provavelmente também falha em "C3.002 —
  Sustentação da tese", mas isso emerge da inferência LLM, não
  está codificado. Trade-off consciente — ver "Por que lista" acima.

- **Granularidade fixa em 8/competência.** Não é uma escolha
  matemática, é um equilíbrio: poucos demais (4-5) viraria rubrica
  INEP plana; muitos (20+) ficaria difícil de escrever evidência
  por descritor. Estado da arte (Tandfonline, LBM) sugere 4-8 por
  dimensão.

- **`exemplo_lacuna` é ilustrativo, não exaustivo.** Um exemplo por
  descritor; redações reais terão variações. LLM da Fase 2 deve
  generalizar, não decorar.

- **Não cobre erros de digitação/OCR.** Lacunas são pedagógicas
  (aluno não dominou competência), não técnicas (foto borrada).
  Erros técnicos ficam em `redato_output.ocr_quality_issues`.

- **Versionamento manual.** Se a lista for atualizada, mudar `versao`
  em [`descritores.yaml`](descritores.yaml) e versionar via git
  (commit deve ser dedicado, não misturado com outras mudanças).
  Pipeline da Fase 2 lê versão do YAML e persiste em
  `diagnostico_lacunas.descritores_versao` pra rastreabilidade.

## Roadmap

| Fase | Status | Descrição |
|---|---|---|
| **1** Descritores | ✅ 2026-05-03 | YAML 40 descritores INEP-aligned (este diretório) |
| **2** Inferência LLM | ✅ 2026-05-03 | Pipeline GPT-4.1 + endpoint `POST /portal/envios/{id}/diagnosticar` + storage em `envios.diagnostico` JSONB |
| **3** Visualização | ✅ 2026-05-03 | Aluno: 3-5 metas via WhatsApp. Professor: heatmap 5×8 + lacunas prioritárias + recomendação + sugestão de oficinas (filtrada por série). Detalhes em [`HOWTO_visualizacao.md`](HOWTO_visualizacao.md). |
| **4** Agregação por turma | ⏳ próxima | Heatmap agregado da turma (% alunos com lacuna em cada descritor) + drill por aluno |
| **5** Validação humana | ⏳ pendente | Métricas de precisão (concordância com avaliador humano) + ajustes de prompt |

## Validação

```bash
python -c "
import yaml
data = yaml.safe_load(open('docs/redato/v3/diagnostico/descritores.yaml'))
assert len(data['descritores']) == 40
print(f'Total: {len(data[\"descritores\"])}')
"
```

Esperado: `Total: 40`. Validações adicionais (8 por competência, IDs
únicos formato `C{n}.{nnn}`, 7 campos obrigatórios) rodaram no commit
inicial — ver mensagem de commit.

## Referências

- Matriz de Referência ENEM 2024-2025 (INEP)
- "A descriptor-based framework for analytic writing assessment"
  (Tandfonline 2019)
- Language Bottleneck Models (van der Schaar Lab, 2025)
