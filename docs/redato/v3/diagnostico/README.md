# Diagnóstico cognitivo de redação ENEM

**Atualizado:** 2026-05-03 · Fase 1 (descritores)

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

## Como o YAML é consumido (Fase 2)

O pipeline da Fase 2 (não construído ainda) lerá
[`descritores.yaml`](descritores.yaml) e usará pra montar prompt do LLM:

```python
import yaml

descritores = yaml.safe_load(open("descritores.yaml"))["descritores"]

prompt = f"""
Você é avaliador de redação ENEM. Dada a redação abaixo + saída
do corretor automático, identifique quais descritores cognitivos
o aluno NÃO domina.

DESCRITORES (40 disponíveis):
{render_descritores(descritores)}

REDAÇÃO: {texto_redacao}
SAÍDA DO CORRETOR: {redato_output}

Para cada descritor que o aluno NÃO domina, retorne:
- id do descritor
- confianca (0.0-1.0)
- evidencia (trecho exato da redação que prova a lacuna)
"""
```

A Fase 2 vai rodar esse prompt por redação e persistir o output
estruturado (lacunas inferidas) em tabela nova
`diagnostico_lacunas` (modelagem na Fase 3).

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
| **2** Inferência LLM | ⏳ próxima | Endpoint `POST /portal/envios/{id}/diagnosticar` que lê descritores.yaml + redato_output e devolve lacunas |
| **3** Storage | ⏳ pendente | Modelo `DiagnosticoLacuna` + agregação por aluno (perfil) e turma (dashboard) |
| **4** UI | ⏳ pendente | Visualização das lacunas no perfil do aluno + drill nota → lacuna específica |
| **5** Recomendação | ⏳ pendente | Mapear lacuna → oficina/exercício do livro pra reforço (livro 1S/2S/3S) |

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
