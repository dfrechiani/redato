# Proposta — Integração Redação em Jogo (REJ) ↔ Redato

**Status:** PROPOSTA EM REVISÃO. Daniel revisa, ajusta, decide. Não implementar antes.
**Data:** 2026-04-29
**Autor da proposta:** Claude (técnico).
**Objetivo:** Integrar o jogo de cartas do REJ ao Redato pra que a correção da Redato considere as cartas escolhidas pelo grupo + a reescrita individual do aluno.

**Decisões pedagógicas registradas (entrada — Daniel 2026-04-29):**

- **E.1.** Aluno informa códigos exatos das cartas via texto WhatsApp. Sem foto, sem OCR de ficha. Formato: `"E12, E27, P03, R05, K11, ..."`.
- **E.2.** Bot mostra cartas alternativas + fraquezas. Quando uma carta escolhida pelo grupo é fraca, bot sugere OUTRAS cartas do mesmo minideck que estavam disponíveis e teriam funcionado melhor.
- **E.3.** Aluno PODE editar a redação pra contornar fraquezas das cartas escolhidas pelo grupo. Professor vê versão original (montada pelas cartas) E o que o aluno mudou. Comparação visível no dashboard.
- **E.4.** Reescrita individual é obrigatória. Aluno não submete texto montado direto.
- **E.5.** Professor cadastra a partida quando quiser via portal.

**Bases consultadas:**

- `cartas_redacao_em_jogo.xlsx` — deck completo (63 estruturais + 7 minidecks temáticos × ~104 cartas = 791 cartas).
- `docs/redato/v3/livros/LIVRO_ATO_2S_PROF.html` — pedagogia do sistema de cartas + uso por oficina.
- `docs/redato/v3/ATO1S_arvore_objetivos_v2.md` e `ATO2S_arvore_objetivos_v2.md` — quando o jogo aparece em cada série.

---

## A. Entendimento do jogo

### A.1 — Estrutura do deck

**Cartas estruturais (E01–E63):** 63 frases com lacunas, COMPARTILHADAS entre todos os temas. Distribuição por seção:

| Seção           | Cor       | Códigos | Quantidade |
|-----------------|-----------|---------|------------|
| ABERTURA        | Azul      | E01–E09 | 9          |
| TESE            | Azul      | E10–E16 | 7          |
| TÓPICO Dev1     | Amarelo   | E17–E20 | 4          |
| ARGUMENTO Dev1  | Amarelo   | E19–E25 | 7          |
| REPERTÓRIO Dev1 | Amarelo   | (5)     | 5          |
| TÓPICO Dev2     | Verde     | E33–E40 | 7          |
| ARGUMENTO Dev2  | Verde     | (5)     | 5          |
| REPERTÓRIO Dev2 | Verde     | (4)     | 4          |
| RETOMADA        | Laranja   | E49–E50 | 4          |
| PROPOSTA        | Laranja   | E51–E63 | 11         |

Lacunas presentes nas estruturais (5 placeholders):
- `[PROBLEMA]` — preenchido por carta P##
- `[REPERTORIO]` — preenchido por carta R##
- `[PALAVRA_CHAVE]` — preenchido por carta K##
- `[AGENTE]` — preenchido por carta A##
- `[ACAO_MEIO]` — preenchido pela combinação AC## + ME## (verbo + instrumento) ou só por uma delas

**Cartas temáticas (minidecks):** 7 minidecks completos, cada um com ~104 cartas, fechado por tema. O minideck de **Saúde Mental** ilustra a composição típica:

| Tipo            | Código  | Quantidade | Exemplo                                                 |
|-----------------|---------|------------|---------------------------------------------------------|
| PROBLEMA        | P##     | 15         | P01: "estigma social associado aos transtornos mentais" |
| REPERTÓRIO      | R##     | 15         | R01: "OMS (86% sem tratamento adequado)"                |
| PALAVRA-CHAVE   | K##     | 30         | K01: "falta de investimento público em saúde mental"    |
| AGENTE          | A##     | 10         | A01: "Ministério da Saúde"                              |
| AÇÃO            | AC##    | 12         | AC01: "ampliar a rede de CAPS"                          |
| MEIO            | ME##    | 12         | ME01: "via Fundo Nacional de Saúde (FNS)"               |
| FIM             | F##     | 10         | F01: "para garantir acesso universal a tratamento psicológico" |

Os 7 temas implementados hoje:
1. Inclusão Digital (104 cartas)
2. Saúde Mental (104)
3. Violência contra a Mulher (104)
4. Educação Financeira (104)
5. Gênero e Diversidade (104)
6. Meio Ambiente (108)
7. Família e Sociedade (104)

**Total geral: 791 cartas** (63 estruturais + 728 temáticas).

### A.2 — Fluxo do jogo no livro 2S

Pelo livro do professor 2S, o sistema de cartas atravessa o ano inteiro. Oficinas com jogo completo (texto do livro):

- **OF02 Conexões Inesperadas** (relações semânticas)
- **OF03 Fábrica de Notícias** (gênero informativo)
- **OF04 Fontes e Citações** (repertório articulado)
- **OF05 Fato ou Opinião?** (modalizadores)
- **OF06 Da Notícia ao Artigo** (transição do informativo ao argumentativo)
- **OF07 Tese e Argumentos**
- **OF08 Análise de Temas**
- **OF09 Expedição Argumentativa** (camadas problema/causa/raiz)
- **OF10 Leilão de Temas**
- **OF11 Pesquisa e Repertório**
- **OF12 Leilão de Soluções** (proposta de intervenção)
- **OF13 Jogo de Redação Completo** ← **redação inteira pela primeira vez, com cartas**

A OF13 é o ápice: é onde o grupo monta a redação completa usando o sistema E_##/P_##/R_##/K_##/A_##/AC_##/ME_##/F_##, e o aluno faz reescrita individual em cima.

### A.3 — Diferença redação cooperativa vs reescrita individual

**Redação cooperativa (em grupo):** o grupo escolhe um conjunto de cartas (mínimo: 1 estrutural por seção do tabuleiro + cartas de lacuna que preencham os placeholders). O texto montado é a soma literal das estruturais com as lacunas substituídas pelas cartas temáticas escolhidas.

**Reescrita individual:** cada aluno do grupo recebe o texto montado e produz sua própria versão autoral. Pode:
- Manter a estrutura mas reescrever as frases com vocabulário próprio
- Mudar conectivos, adicionar exemplos, aprofundar argumentos
- **Contornar fraquezas das cartas escolhidas pelo grupo** (decisão E.3) — ex.: o grupo escolheu R05 que é genérico, o aluno troca por dado mais específico que ele conhece
- Adicionar repertório próprio que não estava no minideck

A reescrita autoral é **obrigatória** (decisão E.4). Sem ela, o aluno não submete redação.

---

## B. Fluxo proposto aluno ↔ bot

Considerando as 5 decisões pedagógicas de entrada:

### B.1 — Sequência de eventos

1. **Professor cadastra a partida** no portal (decisão E.5) com:
   - `atividade_id` (já existe)
   - `tema` do minideck (1 dos 7: saude_mental, inclusao_digital, etc.)
   - `grupo_codigo` (texto livre, ex.: "Grupo Azul", "Time A")
   - Lista de alunos do grupo (`aluno_turma_id[]`)
   - `prazo_reescrita` (data até quando os alunos podem submeter)

2. **Bot recebe códigos do aluno** via texto WhatsApp:
   ```
   "E01, E10, E17, E22, E33, E37, E49, E51, P03, R05, K11, K22, A02, AC07, ME04"
   ```

3. **Bot valida**:
   - Cada código existe no banco (estruturais + minideck temático da partida)
   - Pelo menos 1 carta de cada seção obrigatória (Abertura, Tese, Tópico Dev1, Argumento Dev1, Tópico Dev2, Argumento Dev2, Retomada/Proposta)
   - As lacunas das estruturais escolhidas têm cartas temáticas correspondentes (ex.: se E01 tem `[PROBLEMA]` e `[REPERTORIO]`, lista deve incluir uma P## e uma R##)
   - Se faltar carta obrigatória OU se aluno mandar carta inexistente, bot reclama com lista das cartas disponíveis

4. **Bot monta texto-base** expandindo placeholders das estruturais:
   ```
   Aplica E01 com {[PROBLEMA] = P03.texto, [REPERTORIO] = R05.texto}
        + E10 com {[PALAVRA_CHAVE] = K11.texto}
        + E17 com {[PROBLEMA] = P03.texto, [PALAVRA_CHAVE] = K22.texto}
        ...
   ```
   Resultado: redação cooperativa completa em prosa contínua.

5. **Bot mostra texto-base ao aluno**:
   ```
   📝 Esta é a redação que o seu grupo montou com as cartas escolhidas:

   "[texto montado completo]"

   ✏️ Agora você pode reescrever em sua versão individual.
      Copie o texto, edite com suas palavras e mande de volta.

   Você pode:
   - Trocar palavras pra ficar mais natural
   - Reforçar argumentos com seu repertório próprio
   - Mudar onde achar que a carta escolhida ficou fraca

   ⚠️ Quando estiver pronto, mande sua versão autoral de volta.
      Você ainda tem [N dias] no prazo da atividade.
   ```

6. **Aluno digita reescrita individual** (texto autoral, pode ter quebras de linha).

7. **Bot envia ao Redato** com contexto enriquecido:
   - Lista de cartas DISPONÍVEIS no minideck temático (catálogo completo)
   - Cartas ESCOLHIDAS pelo grupo
   - Texto montado a partir das cartas
   - Texto reescrito pelo aluno

8. **Redato avalia** via novo modo `jogo_redacao`:
   - Rubrica padrão das 5 competências (escala 0-200 cada, 0-1000 total)
   - Score de transformação (0-100): quanto o aluno foi além do esqueleto
   - Sugestões de cartas alternativas: pra cartas escolhidas pelo grupo que ficaram fracas, lista quais OUTRAS cartas do minideck disponível teriam funcionado melhor

9. **Bot retorna feedback ao aluno** em formato compatível com o renderer atual + nova seção "Comparado ao texto do grupo, sua versão melhorou em..."

10. **Professor vê no dashboard** (tela já existente do aluno):
    - Texto montado original (do grupo)
    - Texto reescrito (autoral do aluno)
    - Diff visual ou versão lado-a-lado
    - Análise da redação (M9.4 — pontos fortes/fracos/padrão/transferência)
    - Cartas escolhidas + sugestões alternativas

### B.2 — Estados FSM novos no bot

Adicionar ao FSM:

```
AGUARDANDO_CARTAS_PARTIDA   — partida ativa, esperando aluno mandar códigos
REVISANDO_TEXTO_MONTADO     — bot já mostrou texto-base, espera reescrita
```

Transições:

```
READY → AGUARDANDO_CARTAS_PARTIDA       (aluno escolheu uma partida ativa)
AGUARDANDO_CARTAS_PARTIDA → REVISANDO_TEXTO_MONTADO  (cartas validadas)
REVISANDO_TEXTO_MONTADO → READY         (aluno enviou reescrita; redato processou)
qualquer estado → READY                 (comando "cancelar")
```

### B.3 — Casos de erro tratados

| Erro                         | Resposta do bot                                                            |
|------------------------------|----------------------------------------------------------------------------|
| Carta inexistente (ex.: P99) | "Não achei a carta P99. Cartas disponíveis: P01–P15. Mande de novo."       |
| Falta seção obrigatória      | "Faltou Abertura. Escolha uma carta E01–E09."                              |
| Lacuna sem preenchimento     | "Sua E01 pede [REPERTORIO] mas você não escolheu carta R##."               |
| Reescrita muito curta (<50ch)| "Texto curto demais. Tem certeza que é sua versão final?"                  |
| Aluno tenta enviar foto      | Bot redireciona: "Esta atividade pede texto, não foto. Manda os códigos." |

---

## C. Arquitetura técnica

### C.1 — Banco de dados

**Tabelas novas:**

```sql
-- Catálogo de minidecks temáticos
CREATE TABLE jogos_minideck (
    id UUID PRIMARY KEY,
    tema TEXT NOT NULL UNIQUE,           -- "saude_mental", "inclusao_digital", ...
    nome_humano TEXT NOT NULL,           -- "Saúde Mental"
    serie TEXT,                          -- "2S" (1S não usa jogo completo nessa fase)
    descricao TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE
);

-- Cartas estruturais (compartilhadas entre todos os temas)
CREATE TABLE cartas_estruturais (
    id UUID PRIMARY KEY,
    codigo TEXT NOT NULL UNIQUE,          -- "E01", "E02", ...
    secao TEXT NOT NULL,                  -- ABERTURA, TESE, TOPICO_DEV1, ...
    cor TEXT NOT NULL,                    -- AZUL, AMARELO, VERDE, LARANJA
    texto TEXT NOT NULL,                  -- frase com placeholders
    lacunas TEXT[] NOT NULL,              -- ["PROBLEMA", "REPERTORIO"]
    ordem INTEGER NOT NULL,               -- 1, 2, ...
    created_at TIMESTAMPTZ NOT NULL,
    CHECK (secao IN ('ABERTURA','TESE','TOPICO_DEV1','ARGUMENTO_DEV1',
                     'REPERTORIO_DEV1','TOPICO_DEV2','ARGUMENTO_DEV2',
                     'REPERTORIO_DEV2','RETOMADA','PROPOSTA'))
);

-- Cartas de lacuna (temáticas), agrupadas por minideck
CREATE TABLE cartas_lacuna (
    id UUID PRIMARY KEY,
    minideck_id UUID NOT NULL REFERENCES jogos_minideck(id),
    tipo TEXT NOT NULL,                   -- PROBLEMA, REPERTORIO, PALAVRA_CHAVE, AGENTE, ACAO, MEIO, FIM
    codigo TEXT NOT NULL,                 -- "P01", "R05", "K22", ...
    conteudo TEXT NOT NULL,               -- texto que substitui a lacuna
    UNIQUE (minideck_id, codigo),
    CHECK (tipo IN ('PROBLEMA','REPERTORIO','PALAVRA_CHAVE','AGENTE',
                    'ACAO','MEIO','FIM'))
);

-- Partidas: instâncias de jogo dentro de uma atividade
CREATE TABLE partidas_jogo (
    id UUID PRIMARY KEY,
    atividade_id UUID NOT NULL REFERENCES atividades(id),
    minideck_id UUID NOT NULL REFERENCES jogos_minideck(id),
    grupo_codigo TEXT NOT NULL,           -- "Grupo Azul"
    cartas_escolhidas JSONB NOT NULL,     -- ["E01", "E10", ..., "P03", "R05", ...]
    texto_montado TEXT NOT NULL,          -- redação cooperativa expandida
    prazo_reescrita TIMESTAMPTZ NOT NULL,
    criada_por_professor_id UUID NOT NULL REFERENCES professores(id),
    created_at TIMESTAMPTZ NOT NULL
);

-- Reescritas individuais dos alunos do grupo
CREATE TABLE reescritas_individuais (
    id UUID PRIMARY KEY,
    partida_id UUID NOT NULL REFERENCES partidas_jogo(id),
    aluno_turma_id UUID NOT NULL REFERENCES alunos_turma(id),
    texto TEXT NOT NULL,                  -- texto autoral do aluno
    redato_output JSONB,                  -- output do modo jogo_redacao
    elapsed_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (partida_id, aluno_turma_id)
);
```

**Migration alembic:** uma única migration `g0a1b2c3d4e5_jogo_redacao_em_jogo.py` cria as 5 tabelas + seed das 63 estruturais (idempotent via ON CONFLICT). Seed dos minidecks via script separado `scripts/seed_minideck.py <tema>` lendo o `cartas_redacao_em_jogo.xlsx`.

### C.2 — Endpoints

```
POST /portal/partidas
  Body: { atividade_id, tema, grupo_codigo, alunos_turma_ids[], prazo_reescrita }
  Validações: professor é dono da turma; tema existe; alunos pertencem à turma
  Retorna: { id, partida }

GET /portal/partidas/{id}
  Retorna: { partida + texto_montado + reescritas[] (se já existem) }
  Permission: professor da turma OR aluno do grupo

POST /portal/partidas/{id}/reescritas
  Body: { aluno_turma_id, texto }
  Triggers: pipeline Redato modo jogo_redacao
  Retorna: { id, redato_output }

GET /portal/atividades/{id}/partidas
  Lista partidas de uma atividade (pra dashboard do professor)

PATCH /portal/partidas/{id}/cartas
  Permite professor corrigir cartas se errou ao cadastrar (idempotente)
```

### C.3 — Bot WhatsApp

**Parsing de códigos** (regex tolerante):

```python
_CODIGO_CARTA_RE = re.compile(
    r'\b(E\d{2}|P\d{2}|R\d{2}|K\d{2}|A\d{2}|AC\d{2}|ME\d{2}|F\d{2})\b',
    re.IGNORECASE,
)

def parse_codigos(text: str) -> List[str]:
    """Extrai códigos de cartas. Aceita separadores: vírgula, espaço, linha."""
    return [m.group(0).upper() for m in _CODIGO_CARTA_RE.finditer(text)]
```

**Validação contra minideck temático:**

```python
def validar_partida(codigos: List[str], partida: Partida) -> Result:
    """Retorna (ok, mensagem_erro_pt). Cobre 4 checks:
    1. Cada código existe (estrutural OU temático do minideck)
    2. Tem >= 1 carta de cada seção obrigatória
    3. Lacunas das estruturais escolhidas têm cartas correspondentes
    4. Sem códigos de outros minidecks (aluno enganou de tema)
    """
```

**Novos handlers:**

```python
def _handle_aguardando_cartas(msg, aluno, partida):
    """Aluno em estado AGUARDANDO_CARTAS_PARTIDA mandou texto.
    Tenta parse de códigos. Se válido → monta texto-base + transição.
    """

def _handle_revisando_texto(msg, aluno, partida):
    """Aluno em estado REVISANDO_TEXTO_MONTADO mandou texto.
    É a reescrita individual. Envia ao Redato modo jogo_redacao.
    """
```

### C.4 — Integração com Redato (prompt enriquecido)

Modificação no `_build_user_msg` em `redato_backend/missions/router.py` quando modo é `jogo_redacao`:

```
## Missão a avaliar
Modo: jogo_redacao | Tema: Saúde Mental | Atividade: RJ2·OF13·MF

## Contexto do jogo

O aluno fez reescrita individual a partir de uma redação cooperativa
montada com cartas. Avalie a versão autoral (não a montada).

### CARTAS DO MINIDECK TEMÁTICO (Saúde Mental — 104 disponíveis)

PROBLEMAS disponíveis:
- P01: estigma social associado aos transtornos mentais
- P02: dificuldade de acesso a serviços de saúde mental no SUS
- P03: preconceito que impede a busca por tratamento
- ... (15 ao todo)

REPERTÓRIOS disponíveis:
- R01: OMS (86% sem tratamento adequado)
- R02: ...
- ... (15 ao todo)

PALAVRAS-CHAVE disponíveis: ... (30)
AGENTES disponíveis: ... (10)
AÇÕES disponíveis: ... (12)
MEIOS disponíveis: ... (12)
FINS disponíveis: ... (10)

### CARTAS QUE O GRUPO ESCOLHEU

Estruturais: E01 (abertura), E10 (tese), E17 (tópico Dev1), E22
(argumento Dev1), E33 (tópico Dev2), E37 (repertório Dev2), E49
(retomada), E51 (proposta).

Lacunas:
- [PROBLEMA] preenchido por P03 ("preconceito que impede...")
- [REPERTORIO] por R05 ("dado IBGE 2022...")
- [PALAVRA_CHAVE] por K11 ("falta de investimento") e K22 ("estigma cultural")
- [AGENTE] por A02 ("Ministério da Saúde")
- [ACAO_MEIO] por AC07 ("ampliar rede de CAPS") + ME04 ("via emendas parlamentares")

### TEXTO MONTADO (redação cooperativa)

[Texto completo expandido a partir das estruturais com placeholders
substituídos pelas cartas escolhidas. ~25-30 linhas.]

### REESCRITA INDIVIDUAL (texto a avaliar)

[Texto autoral do aluno. Pode ter feito mudanças significativas.]

---

## Avalie chamando submit_jogo_redacao

Aplique a rubrica das 5 competências do ENEM no TEXTO REESCRITO. Além
disso:

1. **transformacao_cartas** (0-100): quanto a reescrita supera o
   esqueleto? Score 100 = autoria plena, vai muito além das cartas.
   Score 40 = aluno apenas trocou conectivos. Score 0 = cópia literal.

2. **sugestoes_cartas_alternativas**: pra cada carta escolhida pelo
   grupo que ficou fraca no contexto da redação, sugira UMA outra
   carta do minideck disponível que teria funcionado melhor.
   Formato: { codigo_atual: "P03", codigo_sugerido: "P01",
   motivo: "estigma social cobre o problema central; preconceito é
   sintoma do estigma" }. Lista pode ser vazia se nenhuma escolha
   foi fraca.

3. **feedback_aluno** e **feedback_professor** seguem padrão M9.4
   (4 campos discretos no feedback_professor).
```

### C.5 — Schema do tool `JOGO_REDACAO_TOOL`

Adicionar em `redato_backend/missions/schemas.py`:

```python
JOGO_REDACAO_TOOL: Dict[str, Any] = {
    "name": "submit_jogo_redacao",
    "description": (
        "Avaliação Modo Jogo Redação (OF13). Aluno fez reescrita "
        "individual a partir de redação cooperativa montada com "
        "cartas. Avalie a versão autoral pelas 5 competências do "
        "ENEM + score de transformação + sugestões de cartas "
        "alternativas pra escolhas fracas do grupo."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "modo": {"type": "string", "enum": ["jogo_redacao"]},
            "partida_id": {"type": "string"},
            "atividade_id": {"type": "string"},

            # Notas ENEM (escala 0/40/80/120/160/200 cada)
            "notas_enem": {
                "type": "object",
                "properties": {
                    "c1": {"type": "integer", "enum": _NOTA_ENEM},
                    "c2": {"type": "integer", "enum": _NOTA_ENEM},
                    "c3": {"type": "integer", "enum": _NOTA_ENEM},
                    "c4": {"type": "integer", "enum": _NOTA_ENEM},
                    "c5": {"type": "integer", "enum": _NOTA_ENEM},
                },
                "required": ["c1", "c2", "c3", "c4", "c5"],
            },
            "nota_total_enem": {
                "type": "integer", "minimum": 0, "maximum": 1000,
            },

            # Score de transformação (autoria vs cópia)
            "transformacao_cartas": _score_0_100(),

            # Sugestões de cartas alternativas
            "sugestoes_cartas_alternativas": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "codigo_atual": {"type": "string"},
                        "codigo_sugerido": {"type": "string"},
                        "motivo": {"type": "string"},
                    },
                    "required": ["codigo_atual", "codigo_sugerido", "motivo"],
                },
                "description": (
                    "Lista pode ser vazia. Cada item: carta fraca que o "
                    "grupo escolheu + alternativa do minideck que teria "
                    "funcionado melhor + motivo pedagógico em 1 frase."
                ),
            },

            # Flags (segue padrão dos outros modos foco)
            "flags": {
                "type": "object",
                "properties": {
                    "copia_literal_das_cartas": {"type": "boolean"},
                    "cartas_mal_articuladas": {"type": "boolean"},
                    "fuga_do_tema_do_minideck": {"type": "boolean"},
                    "tipo_textual_inadequado": {"type": "boolean"},
                    "desrespeito_direitos_humanos": {"type": "boolean"},
                },
                "required": [
                    "copia_literal_das_cartas",
                    "cartas_mal_articuladas",
                    "fuga_do_tema_do_minideck",
                    "tipo_textual_inadequado",
                    "desrespeito_direitos_humanos",
                ],
            },

            "feedback_aluno": _feedback_aluno_schema(),
            "feedback_professor": _feedback_professor_schema(
                "150-250 palavras"
            ),
        },
        "required": [
            "modo", "partida_id", "atividade_id",
            "notas_enem", "nota_total_enem", "transformacao_cartas",
            "sugestoes_cartas_alternativas", "flags",
            "feedback_aluno", "feedback_professor",
        ],
    },
}
```

Adicionar em `TOOLS_BY_MODE`: `"jogo_redacao": JOGO_REDACAO_TOOL`.

---

## D. Comparação original vs reescrita

### D.1 — Schema da response do detalhe

`GET /portal/partidas/{id}/reescritas/{aluno_id}` retorna:

```python
class ReescritaDetail(BaseModel):
    partida_id: str
    aluno_id: str
    aluno_nome: str
    tema: str

    # Texto montado (redação cooperativa) — derivado das cartas
    texto_montado_original: str
    cartas_escolhidas: List[Dict[str, Any]]   # [{codigo, tipo, conteudo}]

    # Reescrita autoral
    texto_reescrita_aluno: str
    enviada_em: str

    # Output Redato
    notas_enem: Dict[str, int]                # c1..c5
    nota_total_enem: int
    transformacao_cartas: int                 # 0-100
    sugestoes_cartas_alternativas: List[Dict[str, str]]
    flags: Dict[str, bool]
    feedback_aluno: Dict[str, Any]
    analise_da_redacao: Dict[str, Any]        # padrão M9.4
```

### D.2 — UI (frontend)

Tela nova `/atividade/{aid}/partidas/{pid}/aluno/{atid}` com layout:

```
┌─────────────────────────────────┬─────────────────────────────────┐
│ Texto MONTADO                   │ Reescrita AUTORAL               │
│ (redação do grupo)              │ (versão do aluno)               │
│                                 │                                 │
│ [texto com cartas highlighted]  │ [texto com diff highlights]     │
└─────────────────────────────────┴─────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Notas ENEM (autoral)                                            │
│ C1: 160  C2: 160  C3: 120  C4: 160  C5: 160 = 760               │
│ Transformação: 72/100 (autoria boa — supera esqueleto)          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Cartas que o grupo escolheu — sugestões alternativas            │
│ • P03 (preconceito) → P01 (estigma social, mais central) ...   │
│ • R05 (dado IBGE) → R01 (OMS 86%, mais específico) ...         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Análise da redação (M9.4)                                       │
│ 📌 Pontos fortes: ...                                           │
│ ⚠️ Pontos fracos: ...                                            │
│ 🎯 Padrão de falha: ...                                         │
│ 🔁 Transferência: ...                                            │
└─────────────────────────────────────────────────────────────────┘
```

Diff visual: usar lib `diff-match-patch` ou simples comparação por sentença pra destacar trechos modificados pelo aluno.

---

## E. Escopo de fases

### Fase 1 — Proposta pedagógica (esta entrega) — **EM ANDAMENTO**

Daniel revisa, ajusta as 5 decisões pedagógicas, decide:
- Composição mínima das cartas obrigatórias por seção
- Se um aluno pode submeter reescrita sem todas as cartas (cenário: grupo perdeu prazo, aluno individual tenta salvar)
- Como tratar partidas com >1 grupo na mesma atividade (todos os grupos jogam o mesmo tema?)
- Granularidade do `transformacao_cartas` (5 bandas? 10? análoga à rubrica REJ?)

### Fase 2 — Schema + Catálogo (após aprovação)

- Migration alembic com 5 tabelas
- Seed das 63 estruturais (idempotente)
- Script `scripts/seed_minideck.py <tema>` lendo o xlsx
- Endpoints REST (sem bot ainda)
- Tela do professor pra cadastrar partida via portal
- Smoke local com fixtures de Saúde Mental

### Fase 3 — Bot + Reescrita

- Estados FSM `AGUARDANDO_CARTAS_PARTIDA` + `REVISANDO_TEXTO_MONTADO`
- Parsing de códigos via regex
- Validação contra minideck
- Montagem de texto-base via expansão de placeholders
- Captura da reescrita autoral
- Smoke local em dev_offline (sem chamar Claude)

### Fase 4 — Integração Redato (modo jogo_redacao)

- `JOGO_REDACAO_TOOL` em `schemas.py` + `TOOLS_BY_MODE`
- `_FOCO_JOGO_CONTEXT` em `prompts.py` com contexto enriquecido
- Branch em `scoring.py:apply_override` (caps semânticos? talvez não — modo já é completo)
- Helper render no WhatsApp
- Frontend nova tela com diff visual + sugestões de cartas
- Smoke E2E com 1 minideck completo (Saúde Mental)

### Fase 5 — Adicionar minidecks restantes

Repetir Fase 2 (script seed_minideck) pra os outros 6 temas. Sem código novo — só dados.

---

## F. Riscos e custos

### Riscos

1. **Prompt do Claude fica grande.** Listagem de 104 cartas disponíveis + cartas escolhidas + texto montado + texto reescrito pode passar de 4-5k tokens só de input. Custo por correção ~3x maior que `foco_c2`. Mitigação: prompt caching com TTL 1h por minideck (catálogo é estável).

2. **Modelo pode "alucinar" cartas que não existem nas sugestões.** O LLM pode sugerir `P99` que não está no minideck. Mitigação: enum dinâmico no schema do tool com lista das cartas disponíveis (mas explode pra 100+ valores no enum — pode degradar perf). Alternativa: validar pós-response e silenciar sugestões inválidas.

3. **Banco precisa seed inicial grande.** 63 estruturais + 7 × 104 = 791 rows. Idempotente mas demora. Mitigação: rodar uma vez por deploy se for novo banco; produção já tem o seed.

4. **Manutenção do catálogo.** Daniel atualizar uma carta no xlsx requer re-run do seed. Mitigação: script seed_minideck idempotente via UPSERT em `cartas_estruturais.codigo` e `cartas_lacuna(minideck_id, codigo)`.

5. **Aluno pode burlar o sistema.** Aluno submete texto sem ter mandado códigos de carta — bot processa como reescrita normal. Mitigação: estado FSM impõe ordem (cartas → texto-base → reescrita). Mas aluno pode pular pra `READY` via "cancelar" e mandar foto (fluxo M9.2 atual) — esse cenário é OK porque não cria partida; só resta o registro original do bot atual.

6. **Comparação textual é frágil.** Diff de palavras é trivial; diff de "quanto melhorou pedagogicamente" é o que o `transformacao_cartas` tenta capturar — mas é juízo do LLM, oscila. Mitigação: calibrar score com canários (pares de textos: cópia literal score 0; reescrita boa score 80-100).

7. **Volume de dados no log.** Cada partida + reescrita gera ~5KB no banco. 30 alunos × 7 oficinas com jogo × 1 partida cada = ~1MB por turma por ano. Trivial. Pra 10 escolas × 10 turmas: ~100MB. Ainda OK.

### Custos

| Item                                     | Estimativa                |
|------------------------------------------|---------------------------|
| Migration + seed estruturais             | 4h                        |
| Script seed_minideck + 1 minideck        | 4h                        |
| Endpoints REST + permission              | 6h                        |
| Bot FSM + parsing + validação            | 8h                        |
| Montagem de texto-base                   | 4h                        |
| `JOGO_REDACAO_TOOL` + prompts.py + scoring | 6h                       |
| Frontend tela de partida + diff          | 12h                       |
| Tests unit + integração                  | 8h                        |
| **Total Fase 2 + 3 + 4 (estimativa)**    | **52h ≈ 7 dias úteis**   |

Sem o frontend (entregar via API + curl pra Daniel testar): ~40h ≈ 5 dias. Frontend é 12h adicionais.

### Decisões abertas pra Daniel

1. **Mínimo obrigatório de cartas por partida?** Toda seção precisa (10 estruturais)? Ou só 4 (1 abertura, 1 dev1, 1 dev2, 1 conclusão)?
2. **Grupos múltiplos na mesma atividade?** Suportar `partidas_jogo` 1:N com atividade, ou 1:1?
3. **Aluno pode trocar carta na reescrita?** Decisão E.3 diz que pode "contornar" — mas isso é via reescrita textual ou via re-seleção de cartas?
4. **Time-out da partida.** Se o grupo nunca submete cartas, atividade encerra. Aluno pode submeter reescrita "vazia" mesmo sem partida? (Provavelmente não — estado FSM bloqueia.)
5. **Tema do minideck = tema da redação?** Atividade já tem `missao_id` → `modo_correcao`. A partida adiciona um campo `tema` ortogonal. A correção Redato deve considerar o tema do minideck OU o tema da atividade? (Sugestão: tema do minideck domina.)
6. **`transformacao_cartas` afeta a nota ENEM?** Score independente OU integra na C3 (autoria/projeto de texto)? Decisão pedagógica importante.
7. **Sugestões de cartas alternativas — quantas?** Lista pode ser vazia (LLM diz "nenhuma escolha foi fraca") ou sempre tem N? (Sugestão: dinâmico, 0-3 itens.)

---

**Fim da proposta.** Aguardando revisão do Daniel antes de qualquer implementação técnica.
