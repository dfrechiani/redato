# Repositórios de redações ENEM corrigidas — para treino/avaliação de IA

> Foco: redações padrão ENEM (5 competências), volume médio (1k–10k), com texto, nota global, notas por competência, comentários do corretor e tema da proposta.

---

## TIER 1 — Datasets prontos para download (recomendado começar por aqui)

### 1. AES-ENEM Dataset (kamel-usp) — *o mais completo e atual*
- **URLs:** [HuggingFace dataset](https://huggingface.co/datasets/kamel-usp/aes_enem_dataset) · [Repo de código](https://github.com/kamel-usp/aes_enem)
- **Volume:** ~6.700 redações em múltiplos subsets:
  - `sourceB` — 3.220 (origem Vestibular UOL)
  - `sourceAWithGraders` — 1.170 (com 2 corretores)
  - `sourceAOnly` — 395
  - `PROPOR2024` — 1.160 (split do paper)
  - `JBCS2025` — 770
  - `gradesThousand` — 179 redações nota 1000 do ENEM oficial
- **Campos:** texto, prompt/tema, **5 notas por competência (0–200)**, nota global, IDs de corretor (em alguns subsets duas correções independentes).
- **Licença:** MIT.
- **Como acessar:** `load_dataset("kamel-usp/aes_enem_dataset", "sourceAWithGraders")`
- **Paper de referência:** [PROPOR 2024 — A New Benchmark for AES in Portuguese](https://aclanthology.org/2024.propor-1.23.pdf)
- **Limitação:** comentários textuais do corretor são limitados; o forte é o score multi-competência.

### 2. Essay-BR (Marinho/Anchiêta) — *o clássico de referência*
- **URLs:** [Repo original](https://github.com/rafaelanchieta/essay) · [Versão estendida (lplnufpi)](https://github.com/lplnufpi/essay-br) · [Paper arXiv](https://arxiv.org/abs/2105.09081) · [Paperswithcode](https://paperswithcode.com/dataset/essay-br)
- **Volume:**
  - Versão original: **4.570 redações** (split treino 3.198 / val 686 / teste 686)
  - Versão estendida: **6.577 redações** em 151 prompts (inclui 1.160 do Vestibular UOL + 849 de pesquisas anteriores)
- **Campos:** texto, tema/prompt, nota global (0–1000), **5 notas por competência**, splits prontos.
- **Origem:** raspagem de simuladores ENEM online com correção humana especialista.
- **Comentários textuais:** ausentes — apenas notas.

### 3. UOL Banco de Redações em XML (gpassero)
- **URLs:** [github.com/gpassero/uol-redacoes-xml](https://github.com/gpassero/uol-redacoes-xml) · [Corpus alternativo (sidleal)](https://github.com/sidleal/corpus-redacoes-uol)
- **Volume:** atualização mensal do UOL (~20 redações/mês acumuladas; corpus extraído tem ~1.840 redações dependendo do ano de extração).
- **Campos extraídos:** texto **original** + texto **corrigido pelo avaliador**, tema, **nota final (0–10)** e **notas por critério (0–2 cada)** alinhadas com as 5 competências ENEM, **erros gramaticais e ortográficos marcados** (em redações mais recentes).
- **Diferencial:** é a única fonte pública com **marcações inline do corretor** (correção textual, não só nota).
- **Inclui crawler em Python** caso queira re-raspar para atualizar.

### 4. Brazilian Portuguese Narrative Essays (Kaggle)
- **URL:** [kaggle.com/datasets/moesiof/portuguese-narrative-essays](https://www.kaggle.com/datasets/moesiof/portuguese-narrative-essays)
- **Volume/escopo:** redações narrativas com notas multi-competência. **Atenção:** é narrativo (ensino fundamental), não dissertativo-argumentativo ENEM. Útil só como complementar para diversidade de português escrito anotado.

### 5. AES-PT framework (evelinamorim)
- **URL:** [github.com/evelinamorim/aes-pt](https://github.com/evelinamorim/aes-pt)
- Framework de AES para português com pipeline pronto. Ajuda a preprocessar e benchmarkar contra os datasets acima.

---

## TIER 2 — Fontes oficiais INEP/MEC (qualidade premium, volume baixo)

São cartilhas oficiais com **redações nota alta + comentários extensos da banca avaliadora**, organizadas por competência. Volume baixo (~6 a 12 redações por edição), mas é "ouro" para few-shot e calibragem do modelo:

| Edição | URL direto (INEP) |
|---|---|
| ENEM 2025 | [a_redacao_no_enem_2025_cartilha_do_participante.pdf](https://download.inep.gov.br/publicacoes/institucionais/avaliacoes_e_exames_da_educacao_basica/a_redacao_no_enem_2025_cartilha_do_participante.pdf) |
| ENEM 2024 | [a_redacao_no_enem_2024_cartilha_do_participante.pdf](https://download.inep.gov.br/publicacoes/institucionais/avaliacoes_e_exames_da_educacao_basica/a_redacao_no_enem_2024_cartilha_do_participante.pdf) |
| ENEM 2023 | [a_redacao_no_enem_2023_cartilha_do_participante.pdf](https://download.inep.gov.br/publicacoes/institucionais/avaliacoes_e_exames_da_educacao_basica/a_redacao_no_enem_2023_cartilha_do_participante.pdf) |
| ENEM 2022 | [cartilha_do_participante_enem_2022.pdf](https://download.inep.gov.br/download/enem/cartilha_do_participante_enem_2022.pdf) |
| ENEM 2020 | [a_redacao_do_enem_2020_-_cartilha_do_participante.pdf](https://download.inep.gov.br/publicacoes/institucionais/avaliacoes_e_exames_da_educacao_basica/a_redacao_do_enem_2020_-_cartilha_do_participante.pdf) |
| ENEM 2019 | [redacao_enem2019_cartilha_participante.pdf](https://download.inep.gov.br/educacao_basica/enem/downloads/2019/redacao_enem2019_cartilha_participante.pdf) |
| ENEM 2018 | [manual_de_redacao_do_enem_2018.pdf](https://download.inep.gov.br/educacao_basica/enem/guia_participante/2018/manual_de_redacao_do_enem_2018.pdf) |

- **Conteúdo por cartilha:** matriz oficial, descrição dos níveis (0/40/80/120/160/200) por competência, **textos integrais comentados pela banca** explicando exatamente por que cada competência recebeu cada nota.
- **Licença:** Domínio público (obra do governo federal).
- **Uso recomendado:** parsing dos PDFs com a skill `pdf` para extrair {texto, tema, notas, comentário-por-competência} → dataset gold de poucas centenas de exemplos altíssima qualidade.

---

## TIER 3 — Sites raspáveis (volume grande, exige scraping respeitoso)

Todos seguem rubrica ENEM e têm comentários textuais por competência. Verificar `robots.txt` e termos de uso antes de raspar.

| Fonte | URL | O que tem | Estrutura |
|---|---|---|---|
| **UOL Banco de Redações** | [educacao.uol.com.br/bancoderedacoes](https://educacao.uol.com.br/bancoderedacoes/) | Texto, tema, nota 0–10, nota por critério, comentário do corretor, marcações inline | Já existe crawler pronto (ver Tier 1 #3) |
| **Brasil Escola — Banco de Redações** | [brasilescola.uol.com.br/redacao](https://brasilescola.uol.com.br/redacao) | Correção por equipe humana **e** pela IA "Iara" (nas 5 competências ENEM) | HTML estruturado |
| **coRedação** | [coredacao.com](https://coredacao.com/) | Compilados de redações nota 1000 ENEM por ano (2018–2024) com análise | [Exemplos ENEM 2024](https://coredacao.com/conteudo/redacoes-nota-1000-do-enem-2024/) |
| **Estratégia Vestibulares** | [vestibulares.estrategia.com](https://vestibulares.estrategia.com/portal/materias/redacao/redacao-nota-1000-enem/) | 19+ redações nota 1000 com **análise dos professores por competência** | [ENEM 2025: 6 redações](https://vestibulares.estrategia.com/portal/noticias/redacao-nota-1000-leia-redacoes-do-enem-2025/) · [ENEM 2023: 10 redações](https://vestibulares.estrategia.com/portal/materias/redacao/redacao-nota-1000-leia-10-redacoes-do-enem-2023/) |
| **Toda Matéria** | [todamateria.com.br/redacao-nota-1000-enem-exemplos](https://www.todamateria.com.br/redacao-nota-1000-enem-exemplos/) | Exemplos comentados de redações nota 1000 | Texto + comentário em prosa |
| **Imaginie blog** | [blog.imaginie.com.br/exemplos-redacoes-nota-1000](https://blog.imaginie.com.br/exemplos-redacoes-nota-1000/) | 12 exemplos comentados ao longo dos anos | HTML simples |
| **QueroBolsa** | [querobolsa.com.br/revista/redacoes-nota-1000-enem-2023](https://querobolsa.com.br/revista/redacoes-nota-1000-enem-2023) | Redações nota 1000 com análise | HTML simples |
| **Estuda.com** | [estuda.com/redacao-nota-1000-enem-exemplos](https://estuda.com/redacao-nota-1000-enem-exemplos/) | 15 exemplos | HTML simples |
| **Propostas de Redação** | [propostasderedacao.com.br/banco-de-redacoes](https://www.propostasderedacao.com.br/banco-de-redacoes) | Banco de propostas + redações | HTML simples |

**Sugestão de stack para scraping:** `httpx` + `selectolax` ou `BeautifulSoup`. Para sites com muito JS use Playwright. Salve em `JSONL` com schema `{id, ano, tema_titulo, tema_texto_motivador, redacao_texto, nota_global, c1, c2, c3, c4, c5, comentario_geral, comentarios_por_competencia, fonte, url}`.

---

## TIER 4 — Plataformas comerciais (parceria/contato direto)

Não têm API pública para download em massa. Caminho: **contato institucional** alegando uso acadêmico/pesquisa, com NDA se necessário.

| Plataforma | URL | Volume estimado | Como abordar |
|---|---|---|---|
| **Imaginie** | [imaginie.com.br](https://www.imaginie.com.br/) | Centenas de milhares de redações corrigidas por humanos, com nota por competência, apontamentos e videoaulas. Tem programa "[Imaginie para Todos](https://www.imaginie.com.br/imaginie-para-todos/)" e [parcerias com escolas públicas](https://site.imaginie.com.br/) | Email institucional/comercial pedindo parceria de pesquisa |
| **Redação Online** | [redacaonline.com.br](https://www.redacaonline.com.br/) | Correção em 24h com comentários por parágrafo + videoaulas | Igual |
| **Descomplica** | [redacao.descomplica.com.br](https://redacao.descomplica.com.br/) | 500.000+ redações já corrigidas | Contato comercial |
| **Glau** | [glau.com.vc](https://www.glau.com.vc/) | Correção IA pelas 5 competências | Contato |
| **coRedação** | [coredacao.com](https://coredacao.com/) | Correção IA gratuita instantânea por competência | Contato |
| **Me Salva!** | [mesalva.com/enem-e-vestibulares/redacao](https://www.mesalva.com/enem-e-vestibulares/redacao) | — | Contato |

---

## Estratégia recomendada de ingestão

1. **Comece já** com `kamel-usp/aes_enem_dataset` (HuggingFace) + `Essay-BR estendido` — junto dão **>10k redações** com 5 notas por competência. Dedupe por hash do texto entre os dois (há sobreposição de origem UOL).
2. **Camada de qualidade gold:** parse dos **PDFs do INEP** (skill `pdf`) → ~50–100 redações com comentários extensos da banca por competência. Use isso como **conjunto de validação humana** e para few-shot prompting.
3. **Camada de comentários inline:** clone o `gpassero/uol-redacoes-xml` para ter texto-corrigido-pelo-avaliador e marcações de erro (raro nos demais).
4. **Aumento de volume:** raspe Estratégia Vestibulares + coRedação + Toda Matéria para variedade de temas recentes (2023–2025).
5. **Parceria comercial:** se precisar passar de 20k com qualidade, abordar Imaginie e Redação Online formalmente — eles têm o maior acervo do mercado.

## Schema unificado sugerido

```json
{
  "id": "string",
  "fonte": "essay-br|aes-enem|uol|inep|estrategia|...",
  "ano": 2024,
  "tema": {
    "titulo": "string",
    "textos_motivadores": ["string"]
  },
  "redacao": "string",
  "nota_global": 0,
  "notas_competencia": {"c1": 0, "c2": 0, "c3": 0, "c4": 0, "c5": 0},
  "comentarios": {
    "geral": "string",
    "c1": "string", "c2": "string", "c3": "string", "c4": "string", "c5": "string"
  },
  "marcacoes_inline": [{"trecho": "...", "tipo": "ortografia|coesao|...", "sugestao": "..."}],
  "corretor_ids": ["..."],
  "licenca": "MIT|CC-BY|publico|proprietario"
}
```

## Considerações legais

- **INEP:** obras do governo, uso livre.
- **Essay-BR / AES-ENEM:** licenças permissivas (MIT/CC) — verificar arquivo `LICENSE` em cada repo antes de redistribuir.
- **UOL e demais sites:** raspagem para **uso de pesquisa interno** geralmente tolerada; redistribuição pública dos textos pode violar direito autoral dos autores das redações (estudantes) e dos comentários (corretores). Para produto comercial, prefira parceria formal.
- **LGPD:** redações podem conter PII (nome, escola). Anonimize antes de treinar.
