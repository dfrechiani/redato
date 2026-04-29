"""Lógica pura do fluxo de partida no bot WhatsApp (Fase 2 passo 4).

Sem I/O, sem DB — só funções determinísticas. Bot chama estas funções
passando snapshot do catálogo (`ContextoValidacao`); persistência via
`whatsapp/portal_link.py`.

Cobre:
- `parse_codigos`: extrai E##/P##/R##/K##/A##/AC##/ME##/F## do texto
- `classificar_codigos`: divide por tipo
- `validar_partida`: aplica regras das decisões G.1.1, G.1.5
  - 10 estruturais (1 por seção do tabuleiro)
  - lacunas P/R/K presentes onde estrutural pede
  - >= 2 lacunas A/AC/ME/F (faltar 1-2 = warning; faltar 3-4 = erro)
  - Cartas P/R/K/A/AC/ME/F do minideck da partida
- `montar_texto_montado`: substitui [PROBLEMA]/[REPERTORIO]/etc. nos
  textos das estruturais. Quando lacuna A/AC/ME/F faltar, marca
  "[a definir]" no trecho da proposta (decisão B.1 passo 4).

Spec da rubrica em proposta seção A.1; decisões em adendo G.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ──────────────────────────────────────────────────────────────────────
# Parsing
# ──────────────────────────────────────────────────────────────────────

# Regex tolerante: aceita codigos com ou sem espaço entre prefix/digit,
# múltiplos separadores. Ordem importa: AC e ME (2 letras) ANTES de
# A/M (1 letra) pra não casar AC01 como A + C01. F está antes de FIM
# já que não temos prefixos de 3+ letras.
_CODIGO_CARTA_RE = re.compile(
    r'\b(E\d{2}|P\d{2}|R\d{2}|K\d{2}|AC\d{2}|ME\d{2}|A\d{2}|F\d{2})\b',
    re.IGNORECASE,
)


def parse_codigos(text: str) -> List[str]:
    """Extrai codigos de cartas do texto livre. Aceita separadores
    (vírgula, espaço, linha) e case insensitive. Preserva ordem de
    aparição (importante pra montagem do texto-base).

    Dedupe não é feito — se aluno repetir o mesmo código, retorna
    duplicado. Caller decide se dedupe (montador dedupa por seção).
    """
    if not text:
        return []
    return [m.group(0).upper() for m in _CODIGO_CARTA_RE.finditer(text)]


# Mapping prefixo → tipo enum DB (bate com whatsapp/seed_minideck.py).
PREFIXO_TO_TIPO: Dict[str, str] = {
    "E": "ESTRUTURAL",
    "P": "PROBLEMA",
    "R": "REPERTORIO",
    "K": "PALAVRA_CHAVE",
    "A": "AGENTE",
    "AC": "ACAO",
    "ME": "MEIO",
    "F": "FIM",
}

# Tipos de lacuna que vão na proposta (E51-E63). Pelo menos 2 são
# obrigatórios (decisão G.1.1).
TIPOS_PROPOSTA = ("AGENTE", "ACAO", "MEIO", "FIM")

# Seções estruturais — bate com `models.SECOES_ESTRUTURAIS`. 10 no
# total (tabuleiro tem 10 posições).
SECOES_TABULEIRO = (
    "ABERTURA", "TESE",
    "TOPICO_DEV1", "ARGUMENTO_DEV1", "REPERTORIO_DEV1",
    "TOPICO_DEV2", "ARGUMENTO_DEV2", "REPERTORIO_DEV2",
    "RETOMADA", "PROPOSTA",
)

# Placeholders que aparecem nas estruturais. Bate com regex em
# `scripts/seed_cartas_estruturais.py`.
PLACEHOLDERS_VALIDOS = frozenset({
    "PROBLEMA", "REPERTORIO", "PALAVRA_CHAVE", "AGENTE", "ACAO_MEIO",
})

# Mapping placeholder → tipo de carta que preenche. ACAO_MEIO é
# especial: aceita combinação AC + ME ou só uma das duas.
PLACEHOLDER_TO_TIPO_LACUNA = {
    "PROBLEMA": ("PROBLEMA",),
    "REPERTORIO": ("REPERTORIO",),
    "PALAVRA_CHAVE": ("PALAVRA_CHAVE",),
    "AGENTE": ("AGENTE",),
    "ACAO_MEIO": ("ACAO", "MEIO"),
}


def codigo_to_tipo(codigo: str) -> Optional[str]:
    """Retorna o tipo enum DB ('PROBLEMA', 'ACAO', 'ESTRUTURAL', ...)
    ou None se prefix não bate com nenhum padrão."""
    cod = codigo.upper()
    # Tentar prefixos de 2 letras primeiro
    for pref in ("AC", "ME"):
        if cod.startswith(pref) and cod[2:].isdigit():
            return PREFIXO_TO_TIPO[pref]
    # Depois 1 letra
    for pref in ("E", "P", "R", "K", "A", "F"):
        if cod.startswith(pref) and cod[1:].isdigit():
            return PREFIXO_TO_TIPO[pref]
    return None


def classificar_codigos(codigos: List[str]) -> Dict[str, List[str]]:
    """Agrupa codigos por tipo (preserva ordem de aparição dentro do
    tipo). Ex.: {"ESTRUTURAL": ["E01", "E10"], "PROBLEMA": ["P03"]}."""
    out: Dict[str, List[str]] = {}
    for cod in codigos:
        tipo = codigo_to_tipo(cod)
        if tipo is None:
            continue
        out.setdefault(tipo, []).append(cod)
    return out


# ──────────────────────────────────────────────────────────────────────
# Snapshot do catálogo (read-only) — caller carrega do DB e passa
# ──────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CartaEstruturalSnapshot:
    """Snapshot read-only de `cartas_estruturais`. Caller (bot/portal_link)
    monta lendo do DB; validar/montar não tocam DB."""
    codigo: str
    secao: str
    cor: str
    texto: str
    lacunas: Tuple[str, ...]  # ordem importa pra montagem


@dataclass(frozen=True)
class CartaLacunaSnapshot:
    """Snapshot read-only de `cartas_lacuna`."""
    codigo: str
    tipo: str
    conteudo: str


@dataclass(frozen=True)
class ContextoValidacao:
    """Catálogo necessário pra validar/montar uma partida.

    `estruturais_por_codigo` cobre TODAS as 63 estruturais (compartilhadas).
    `lacunas_por_codigo` cobre apenas as cartas do minideck da partida
    (~104 entradas pra um minideck completo). Cartas de outros minidecks
    NÃO entram aqui — caller usa essa lacuna pra detectar 'tema errado'."""
    estruturais_por_codigo: Dict[str, CartaEstruturalSnapshot]
    lacunas_por_codigo: Dict[str, CartaLacunaSnapshot]
    minideck_tema: str            # slug, ex.: "saude_mental"
    minideck_nome_humano: str     # display, ex.: "Saúde Mental"


# ──────────────────────────────────────────────────────────────────────
# Validação
# ──────────────────────────────────────────────────────────────────────

@dataclass
class ResultadoValidacao:
    """Output de `validar_partida`. Consumer pode renderizar a mensagem
    direto ou montar UI estruturada."""
    ok: bool
    warnings: List[str] = field(default_factory=list)
    mensagem_erro: Optional[str] = None
    # Detalhes pra montagem do texto-base (só populados quando ok=True
    # ou ok=True/warnings). Caller usa direto, evitando reprocessar.
    estruturais_em_ordem: List[str] = field(default_factory=list)
    lacunas_por_tipo: Dict[str, List[str]] = field(default_factory=dict)
    placeholders_vazios: List[str] = field(default_factory=list)


def _ordem_secao(secao: str) -> int:
    """Ordem natural do tabuleiro pra renderização. Volta 99 pra
    secao desconhecida (não deveria acontecer)."""
    try:
        return SECOES_TABULEIRO.index(secao)
    except ValueError:
        return 99


def validar_partida(
    codigos: List[str], ctx: ContextoValidacao,
) -> ResultadoValidacao:
    """Valida lista de codigos contra catálogo do minideck. Aplica:

    1. Cada código existe (E## em estruturais OU P/R/K/A/AC/ME/F no
       minideck). Outros = `mensagem_erro`.
    2. Sem cartas duplicadas (aluno mandou E01 2x). Warning.
    3. Exatamente 1 estrutural por seção do tabuleiro (10 totais).
       Faltar = erro com nome da seção; sobrando = warning.
    4. Lacunas P/R/K presentes onde estruturais pedem (>= 1 carta de
       cada tipo de placeholder usado).
    5. >= 2 lacunas entre A/AC/ME/F (proposta). Faltar 1-2 =
       warning; 3+ = erro.

    Retorna `ResultadoValidacao` com `ok=False, mensagem_erro=...` no
    primeiro erro fatal; ou `ok=True, warnings=[...]` se passou com
    avisos.
    """
    # Dedup defensivo: aluno mandou "E01, E01, E10" — ignoramos a
    # 2ª aparição mas guardamos pra warning.
    codigos_unicos: List[str] = []
    duplicados: List[str] = []
    seen: set = set()
    for c in codigos:
        cu = c.upper()
        if cu in seen:
            duplicados.append(cu)
        else:
            seen.add(cu)
            codigos_unicos.append(cu)

    # Step 1: cada código existe?
    estruturais_escolhidas: List[CartaEstruturalSnapshot] = []
    lacunas_escolhidas: List[CartaLacunaSnapshot] = []
    desconhecidos: List[str] = []
    for cod in codigos_unicos:
        tipo = codigo_to_tipo(cod)
        if tipo is None:
            desconhecidos.append(cod)
            continue
        if tipo == "ESTRUTURAL":
            est = ctx.estruturais_por_codigo.get(cod)
            if est is None:
                desconhecidos.append(cod)
            else:
                estruturais_escolhidas.append(est)
        else:
            lac = ctx.lacunas_por_codigo.get(cod)
            if lac is None:
                # Carta não está no minideck → "tema errado" ou
                # "código não existe". Usamos mensagem específica
                # quando é um tipo conhecido (P/R/K/A/AC/ME/F).
                desconhecidos.append(cod)
            else:
                lacunas_escolhidas.append(lac)

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

    warnings: List[str] = []
    if duplicados:
        warnings.append(
            f"Você repetiu {duplicados[0]} (e talvez outras). "
            f"Considerei só uma vez."
        )

    # Step 2: estruturais — 1 por seção do tabuleiro
    estruturais_por_secao: Dict[str, List[CartaEstruturalSnapshot]] = {}
    for e in estruturais_escolhidas:
        estruturais_por_secao.setdefault(e.secao, []).append(e)

    secoes_faltando = [
        s for s in SECOES_TABULEIRO
        if s not in estruturais_por_secao
    ]
    if secoes_faltando:
        # Constrói mensagem indicando quais codigos válidos preenchem
        # a primeira seção faltando (UX: aluno vê opções disponíveis).
        secao = secoes_faltando[0]
        candidatos = sorted(
            e.codigo for e in ctx.estruturais_por_codigo.values()
            if e.secao == secao
        )
        prefixo = candidatos[0] if candidatos else "E??"
        ultimo = candidatos[-1] if candidatos else "E??"
        return ResultadoValidacao(
            ok=False,
            mensagem_erro=(
                f"Faltou seção {_secao_humana(secao)}. Escolha uma "
                f"carta entre {prefixo} e {ultimo}."
            ),
        )

    secoes_excedentes = [
        s for s, lst in estruturais_por_secao.items() if len(lst) > 1
    ]
    if secoes_excedentes:
        s = secoes_excedentes[0]
        codigos_excedentes = [e.codigo for e in estruturais_por_secao[s]]
        warnings.append(
            f"Você escolheu mais de uma carta da seção "
            f"{_secao_humana(s)} ({', '.join(codigos_excedentes)}). "
            f"Considerei a primeira ({codigos_excedentes[0]})."
        )

    # Captura ordem das estruturais escolhidas (1 por seção, na ordem
    # do tabuleiro). Usado pelo montador.
    estruturais_em_ordem = [
        estruturais_por_secao[s][0].codigo
        for s in SECOES_TABULEIRO
    ]

    # Step 3: lacunas P/R/K cobrem placeholders das estruturais escolhidas
    placeholders_necessarios: set = set()
    for s in SECOES_TABULEIRO:
        e = estruturais_por_secao[s][0]
        for ph in e.lacunas:
            if ph in PLACEHOLDERS_VALIDOS:
                placeholders_necessarios.add(ph)

    # Conta lacunas escolhidas por tipo
    lacunas_por_tipo: Dict[str, List[str]] = {}
    for l in lacunas_escolhidas:
        lacunas_por_tipo.setdefault(l.tipo, []).append(l.codigo)

    # P/R/K obrigatórios em desenvolvimento — se aluno escolheu
    # estrutural com [PROBLEMA] mas não mandou nenhum P##, erro.
    obrigatorios_dev = ("PROBLEMA", "REPERTORIO", "PALAVRA_CHAVE")
    for ph in obrigatorios_dev:
        if ph in placeholders_necessarios:
            tipo_esperado = PLACEHOLDER_TO_TIPO_LACUNA[ph][0]  # único
            if not lacunas_por_tipo.get(tipo_esperado):
                # Identifica qual estrutural pediu pra mensagem
                pediu = next(
                    (estruturais_por_secao[s][0].codigo
                     for s in SECOES_TABULEIRO
                     if ph in estruturais_por_secao[s][0].lacunas),
                    "?",
                )
                prefixo_pra_aluno = {
                    "PROBLEMA": "P##",
                    "REPERTORIO": "R##",
                    "PALAVRA_CHAVE": "K##",
                }[ph]
                return ResultadoValidacao(
                    ok=False,
                    mensagem_erro=(
                        f"Sua {pediu} pede [{ph}] mas você não "
                        f"escolheu carta {prefixo_pra_aluno}."
                    ),
                )

    # Step 4: proposta — A/AC/ME/F. Conta tipos PRESENTES na lacuna
    # escolhida (não placeholders nas estruturais — são todos
    # [ACAO_MEIO] e [AGENTE]).
    placeholders_vazios: List[str] = []
    tipos_proposta_presentes = sum(
        1 for tipo in TIPOS_PROPOSTA
        if lacunas_por_tipo.get(tipo)
    )

    # Faltar 3+ → erro
    if tipos_proposta_presentes < 2:
        faltam = [t for t in TIPOS_PROPOSTA
                  if not lacunas_por_tipo.get(t)]
        return ResultadoValidacao(
            ok=False,
            mensagem_erro=(
                f"Faltam {len(faltam)} lacunas da proposta "
                f"({', '.join(_tipo_humano(t) for t in faltam)}). "
                f"Você precisa de pelo menos 2 cartas entre AGENTE, "
                f"AÇÃO, MEIO e FIM."
            ),
        )
    # Faltar 1-2 → warning
    if tipos_proposta_presentes < 4:
        faltam = [t for t in TIPOS_PROPOSTA
                  if not lacunas_por_tipo.get(t)]
        warnings.append(
            f"A proposta ficou sem {len(faltam)} lacuna(s) "
            f"({', '.join(_tipo_humano(t) for t in faltam)}). O bot "
            f"aceitou e usou as cartas que vocês escolheram. Trechos "
            f"que dependiam só das lacunas faltantes ficaram como "
            f"[a definir]."
        )
        placeholders_vazios = list(faltam)

    return ResultadoValidacao(
        ok=True,
        warnings=warnings,
        estruturais_em_ordem=estruturais_em_ordem,
        lacunas_por_tipo=lacunas_por_tipo,
        placeholders_vazios=placeholders_vazios,
    )


_NOMES_HUMANOS_SECAO = {
    "ABERTURA": "Abertura",
    "TESE": "Tese",
    "TOPICO_DEV1": "Tópico Dev1",
    "ARGUMENTO_DEV1": "Argumento Dev1",
    "REPERTORIO_DEV1": "Repertório Dev1",
    "TOPICO_DEV2": "Tópico Dev2",
    "ARGUMENTO_DEV2": "Argumento Dev2",
    "REPERTORIO_DEV2": "Repertório Dev2",
    "RETOMADA": "Retomada",
    "PROPOSTA": "Proposta",
}


def _secao_humana(secao: str) -> str:
    return _NOMES_HUMANOS_SECAO.get(secao, secao)


_NOMES_HUMANOS_TIPO = {
    "PROBLEMA": "PROBLEMA", "REPERTORIO": "REPERTÓRIO",
    "PALAVRA_CHAVE": "PALAVRA-CHAVE",
    "AGENTE": "AGENTE", "ACAO": "AÇÃO",
    "MEIO": "MEIO", "FIM": "FIM",
}


def _tipo_humano(tipo: str) -> str:
    return _NOMES_HUMANOS_TIPO.get(tipo, tipo)


# ──────────────────────────────────────────────────────────────────────
# Montagem do texto-base (redação cooperativa)
# ──────────────────────────────────────────────────────────────────────

def montar_texto_montado(
    estruturais_em_ordem: List[str],
    lacunas_por_tipo: Dict[str, List[str]],
    ctx: ContextoValidacao,
    placeholders_vazios: Optional[List[str]] = None,
) -> str:
    """Expande as estruturais em texto único, substituindo placeholders
    pelo conteúdo das lacunas escolhidas.

    Regras de substituição:
    - [PROBLEMA] → conteúdo da 1ª P## escolhida (mantém a mesma em todos
      os slots — coerência narrativa)
    - [REPERTORIO] → idem 1ª R##
    - [PALAVRA_CHAVE] → 1ª K## no 1º slot, 2ª K## no 2º (gira por slot)
    - [AGENTE] → 1ª A##
    - [ACAO_MEIO] → "AC## conteúdo + ME## conteúdo" (ambos), OU só um
      se outro faltar, OU "[a definir]" se nenhum existir
    - Se `placeholders_vazios` lista um tipo, substitui por "[a definir]"
      mesmo se houver carta (decisão B.1 passo 4 do adendo G — usado
      quando partida foi aceita com warning de proposta incompleta)

    Retorna texto único concatenando as 10 estruturais em ordem do
    tabuleiro (ABERTURA → TESE → ... → PROPOSTA), separadas por
    parágrafos.
    """
    placeholders_vazios = placeholders_vazios or []

    # Helper: pra placeholder X, retorna o conteúdo a substituir.
    # `slot_index` aumenta a cada aparição do placeholder no texto
    # — relevante pra [PALAVRA_CHAVE] que aparece 2x em E04 etc.
    def _conteudo_pra_placeholder(
        ph: str, slot_index: int,
    ) -> str:
        # ACAO_MEIO é especial — combinação de AC + ME
        if ph == "ACAO_MEIO":
            ac_codigos = lacunas_por_tipo.get("ACAO", [])
            me_codigos = lacunas_por_tipo.get("MEIO", [])
            ac_vazio = "ACAO" in placeholders_vazios
            me_vazio = "MEIO" in placeholders_vazios
            partes: List[str] = []
            if ac_codigos and not ac_vazio:
                ac_cod = ac_codigos[slot_index % len(ac_codigos)]
                partes.append(ctx.lacunas_por_codigo[ac_cod].conteudo)
            if me_codigos and not me_vazio:
                me_cod = me_codigos[slot_index % len(me_codigos)]
                partes.append(ctx.lacunas_por_codigo[me_cod].conteudo)
            if not partes:
                return "[a definir]"
            return " ".join(partes)

        # Outros placeholders: mapping direto
        tipos = PLACEHOLDER_TO_TIPO_LACUNA.get(ph, ())
        if not tipos:
            return f"[{ph}]"
        tipo = tipos[0]
        if tipo in placeholders_vazios:
            return "[a definir]"
        codigos = lacunas_por_tipo.get(tipo, [])
        if not codigos:
            return "[a definir]"
        cod = codigos[slot_index % len(codigos)]
        return ctx.lacunas_por_codigo[cod].conteudo

    paragrafos: List[str] = []
    # Contador de slots por placeholder pra distribuir múltiplas K##
    slot_contador: Dict[str, int] = {}

    for cod in estruturais_em_ordem:
        est = ctx.estruturais_por_codigo[cod]
        texto = est.texto
        # Substitui placeholders na ordem de aparição em `est.lacunas`
        # (que respeita a ordem do texto). Pra cada [PH], pega o
        # próximo conteúdo do counter.
        for ph in est.lacunas:
            slot_idx = slot_contador.get(ph, 0)
            conteudo = _conteudo_pra_placeholder(ph, slot_idx)
            slot_contador[ph] = slot_idx + 1
            # Substitui APENAS a primeira ocorrência do placeholder
            # — preserva múltiplos slots (E04 com 2x [PALAVRA_CHAVE]
            # consome 2 cartas distintas).
            texto = texto.replace(f"[{ph}]", conteudo, 1)
        paragrafos.append(texto)

    return "\n\n".join(paragrafos)
