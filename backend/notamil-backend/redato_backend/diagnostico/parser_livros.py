"""Parser dos HTMLs dos livros do professor (Fase 5A.1).

Lê os 3 HTMLs (`LIVRO_1S_PROF`, `LIVRO_ATO_2S_PROF`, `LIVRO_ATO_3S_PROF`)
e extrai estruturas pedagógicas: oficinas, seções, indicação de
avaliabilidade pelo Redato (presença de `.mf-redato-page`).

Output alimenta `mapeador.py` que envia conteúdo ao GPT-4.1 pra
classificar quais dos 40 descritores cada oficina trabalha.

Estratégias de extração (combinadas):
1. **HTML comments** `<!-- ════ OFICINA NN — TITLE ════ -->` (1S)
2. **Cover blocks** `font-size:22rem` com número grande (2S, 3S)
3. **Block markers** `font-size: 0.58rem` com texto "Oficina NN ·
   Bloco N" (2S, 3S)

A extração é defensiva: tenta todas as 3 e usa a primeira que dá
resultados. Se livro futuro mudar layout, basta adicionar nova
strategy aqui.

NÃO chama LLM — esse módulo é puramente parsing local. Mapper LLM
fica em `mapeador.py`.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup, Tag, NavigableString

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Tipos
# ──────────────────────────────────────────────────────────────────────

@dataclass
class Secao:
    """Sub-bloco pedagógico de uma oficina (Abertura, DOJ, Ponte, etc.)."""
    tipo: str                # "abertura" | "doj" | "ponte" | "missao_final" | "exercicio" | "outro"
    titulo: Optional[str]    # H2/H3 da seção (None se não houver)
    conteudo_texto: str      # texto plano, limitado a MAX_CHARS_SECAO

    def to_dict(self) -> dict:
        return {
            "tipo": self.tipo,
            "titulo": self.titulo,
            "conteudo_texto": self.conteudo_texto,
        }


@dataclass
class OficinaLivro:
    """Oficina extraída de um livro do professor."""
    codigo: str              # ex.: "RJ1·OF03·MF" (gerado a partir de série + número)
    serie: str               # "1S" | "2S" | "3S"
    oficina_numero: int      # 1..15
    titulo: str              # nome da oficina (ex.: "Conectivos Argumentativos")
    tem_redato_avaliavel: bool
    """True se a oficina tem `.mf-redato-page` no HTML — i.e., produz
    foto-redação avaliável pelo bot."""
    secoes: List[Secao] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "codigo": self.codigo,
            "serie": self.serie,
            "oficina_numero": self.oficina_numero,
            "titulo": self.titulo,
            "tem_redato_avaliavel": self.tem_redato_avaliavel,
            "secoes": [s.to_dict() for s in self.secoes],
        }

    def conteudo_consolidado(self, max_chars: int = 6000) -> str:
        """Concatena seções num bloco único pro prompt do LLM.
        Trunca em max_chars total (não por seção) pra balancear
        custo de tokens vs cobertura."""
        partes: List[str] = [f"# {self.titulo} ({self.codigo})"]
        if self.tem_redato_avaliavel:
            partes.append("[Esta oficina é avaliável pelo Redato]")
        for s in self.secoes:
            cabec = f"## {s.titulo}" if s.titulo else f"## ({s.tipo})"
            partes.append(cabec)
            partes.append(s.conteudo_texto)
        bloco = "\n\n".join(partes)
        if len(bloco) <= max_chars:
            return bloco
        # Trunca preservando final ("...") — o final costuma ter
        # missao final que importa pra mapeamento
        head = bloco[: max_chars - 200]
        tail = bloco[-150:]
        return head + "\n\n[...]\n\n" + tail


# ──────────────────────────────────────────────────────────────────────
# Constantes
# ──────────────────────────────────────────────────────────────────────

MAX_CHARS_SECAO = 2000
"""Limite por seção pra evitar prompt explodir em oficinas longas."""

MAX_OFICINAS_POR_LIVRO = 20
"""Cap defensivo. Livros têm 13-15 oficinas; > 20 = bug do parser."""

# Mapping título-keyword → tipo de seção (case-insensitive)
TIPO_POR_KEYWORD = [
    (r"\babertura\b", "abertura"),
    (r"\bvis(ã|a)o\b|\bregras\b|\bm(ã|a)os\s+(à|a)\s+obra\b", "regras"),
    (r"\bpalavras\s+do\s+dia\b|\bpalavras-do-dia\b", "palavras"),
    (r"\bjogo\b|\bdoj\b|\bdecodificando\s+o\s+jogo\b", "doj"),
    (r"\bponte\b", "ponte"),
    (r"\bmiss(ã|a)o\s+final\b|\bproduç(ã|a)o\b", "missao_final"),
    (r"\bcheckpoint\b", "checkpoint"),
    (r"\bexerc(í|i)cio\b", "exercicio"),
    (r"\bdoss[iî]?[eê]\b", "dossie"),
    (r"\bsimulado\b", "simulado"),
]


def _classificar_tipo(titulo: Optional[str]) -> str:
    """Classifica tipo da seção pelo título (regex case-insensitive).
    Fallback 'outro' quando nenhum keyword bate."""
    if not titulo:
        return "outro"
    t = titulo.lower()
    for pattern, tipo in TIPO_POR_KEYWORD:
        if re.search(pattern, t, re.IGNORECASE):
            return tipo
    return "outro"


# ──────────────────────────────────────────────────────────────────────
# Detecção de oficinas
# ──────────────────────────────────────────────────────────────────────

def _detectar_oficinas_via_comentarios(
    soup: BeautifulSoup, html_text: str,
) -> List[Tuple[int, int, str]]:
    """Estratégia 1 (1S): comentários '<!-- ════ OFICINA NN — TITLE ════ -->'.

    Retorna lista de (numero, posição_no_html, titulo).
    """
    out: List[Tuple[int, int, str]] = []
    pattern = re.compile(
        r"<!--\s*[═=]+\s*OFICINA\s+(\d+)\s*[—\-:]\s*([^═=\n<]+?)\s*[═=]+\s*-->",
        re.IGNORECASE,
    )
    for m in pattern.finditer(html_text):
        try:
            num = int(m.group(1))
            titulo = m.group(2).strip()
            out.append((num, m.start(), titulo))
        except (ValueError, IndexError):
            continue
    return out


def _detectar_oficinas_via_cover(
    soup: BeautifulSoup, html_text: str,
) -> List[Tuple[int, int, str]]:
    """Estratégia 2 (2S/3S): blocos cover com `font-size:22rem` mostrando
    o número da oficina. Procura próximo h1/h2 pra título.

    Retorna lista de (numero, posição_no_html, titulo).
    """
    out: List[Tuple[int, int, str]] = []
    # Busca via regex porque bs4 perde o offset original
    pattern = re.compile(
        r'font-size:22rem[^"\']*"[^>]*>\s*(\d{1,2})\s*<',
        re.IGNORECASE,
    )
    for m in pattern.finditer(html_text):
        try:
            num = int(m.group(1))
            if num < 1 or num > MAX_OFICINAS_POR_LIVRO:
                continue
            # Tenta encontrar título no mesmo trecho HTML — h2 mais
            # próximo após o cover
            window = html_text[m.end(): m.end() + 3000]
            h_match = re.search(
                r"<h[12][^>]*>([^<]+)</h[12]>", window, re.IGNORECASE,
            )
            titulo = h_match.group(1).strip() if h_match else f"Oficina {num}"
            out.append((num, m.start(), titulo))
        except (ValueError, IndexError):
            continue
    return out


def _detectar_oficinas_via_block_marker(
    soup: BeautifulSoup, html_text: str,
) -> List[Tuple[int, int, str]]:
    """Estratégia 3: marcador 'Oficina NN · Bloco N' usado no header.

    Retorna lista de (numero, posição_no_html, titulo).
    """
    out: List[Tuple[int, int, str]] = []
    pattern = re.compile(
        r"Oficina\s+(\d{1,2})\s*[·•]\s*Bloco",
        re.IGNORECASE,
    )
    for m in pattern.finditer(html_text):
        try:
            num = int(m.group(1))
            if num < 1 or num > MAX_OFICINAS_POR_LIVRO:
                continue
            window = html_text[m.end(): m.end() + 3000]
            h_match = re.search(
                r"<h[12][^>]*>([^<]+)</h[12]>", window, re.IGNORECASE,
            )
            titulo = h_match.group(1).strip() if h_match else f"Oficina {num}"
            out.append((num, m.start(), titulo))
        except (ValueError, IndexError):
            continue
    return out


def _dedup_e_ordena_oficinas(
    detec: List[Tuple[int, int, str]],
) -> List[Tuple[int, int, str]]:
    """Mantém PRIMEIRA ocorrência por número (defensa contra cover
    + comment + block referindo a mesma oficina) e ordena por
    posição no HTML."""
    visto: dict = {}
    for num, pos, titulo in detec:
        if num not in visto:
            visto[num] = (num, pos, titulo)
    ordered = sorted(visto.values(), key=lambda x: x[1])
    return ordered


# ──────────────────────────────────────────────────────────────────────
# Extração de seções dentro de uma oficina
# ──────────────────────────────────────────────────────────────────────

def _texto_limpo_de_node(node: Tag) -> str:
    """Extrai texto plano do node, descartando scripts/styles/comments
    e colapsando whitespace.
    """
    if not node:
        return ""
    # Clone defensivo pra não mutar a soup original
    text = node.get_text(separator=" ", strip=True)
    # Colapsa whitespace + remove caracteres-fantasma
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extrair_secoes_da_fatia(
    fatia_html: str, max_chars_secao: int = MAX_CHARS_SECAO,
) -> List[Secao]:
    """Quebra a fatia HTML em seções por H2/H3 e devolve lista
    de Secao com tipo classificado.

    Heurística simples:
    - Cada H2/H3 é início de uma nova seção
    - Conteúdo da seção = texto entre esse heading e o próximo
    - Tipo é inferido pelo título via _classificar_tipo
    - Se não houver headings, devolve uma única seção 'outro' com
      todo o texto
    """
    soup = BeautifulSoup(fatia_html, "html.parser")
    # Remove scripts/styles antes de extrair texto
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()

    headings = soup.find_all(["h2", "h3"])
    if not headings:
        texto = _texto_limpo_de_node(soup)[:max_chars_secao]
        if not texto:
            return []
        return [Secao(tipo="outro", titulo=None, conteudo_texto=texto)]

    secoes: List[Secao] = []
    for i, h in enumerate(headings):
        titulo = h.get_text(strip=True)
        if not titulo:
            continue
        # Coleta texto até o próximo heading
        partes = []
        for sib in h.next_siblings:
            if isinstance(sib, Tag) and sib.name in ("h2", "h3"):
                break
            if isinstance(sib, NavigableString):
                txt = str(sib).strip()
                if txt:
                    partes.append(txt)
            elif isinstance(sib, Tag):
                # Pula scripts/styles
                if sib.name in ("script", "style"):
                    continue
                txt = _texto_limpo_de_node(sib)
                if txt:
                    partes.append(txt)
        conteudo = " ".join(partes)
        conteudo = re.sub(r"\s+", " ", conteudo).strip()[:max_chars_secao]
        secoes.append(Secao(
            tipo=_classificar_tipo(titulo),
            titulo=titulo,
            conteudo_texto=conteudo,
        ))
    return secoes


def _gerar_codigo_oficina(serie: str, numero: int) -> str:
    """Gera código canônico 'RJ{N}·OF{NN}·MF'."""
    serie_num = serie[0] if serie else "?"
    return f"RJ{serie_num}·OF{numero:02d}·MF"


# ──────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────

def extrair_oficinas_do_livro(
    html_path: str,
    serie: str,
    *,
    max_chars_secao: int = MAX_CHARS_SECAO,
) -> List[OficinaLivro]:
    """Parseia HTML do livro e extrai cada oficina.

    Args:
        html_path: caminho absoluto pro HTML do livro.
        serie: "1S" | "2S" | "3S" — pra gerar código canônico.
        max_chars_secao: limite por seção. Default 2000 chars.

    Returns:
        Lista de OficinaLivro ordenada por número da oficina.

    Raises:
        FileNotFoundError: HTML não existe.
        ValueError: serie inválida.
    """
    if serie not in ("1S", "2S", "3S"):
        raise ValueError(f"serie inválida: {serie!r}")
    path = Path(html_path)
    if not path.exists():
        raise FileNotFoundError(f"livro não encontrado: {html_path}")

    html_text = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html_text, "html.parser")

    # Tenta as 3 estratégias e combina (pode dar 0 ou múltiplas matches
    # por oficina; dedup_e_ordena_oficinas resolve)
    via_comments = _detectar_oficinas_via_comentarios(soup, html_text)
    via_cover = _detectar_oficinas_via_cover(soup, html_text)
    via_block = _detectar_oficinas_via_block_marker(soup, html_text)

    detectadas = _dedup_e_ordena_oficinas(via_comments + via_cover + via_block)
    if not detectadas:
        logger.warning(
            "[parser] %s: nenhuma oficina detectada. Verifique o "
            "layout do HTML.", html_path,
        )
        return []

    # Pra cada oficina, extrai a fatia entre seu start e o start da
    # próxima oficina (ou EOF). Aplica _extrair_secoes_da_fatia.
    out: List[OficinaLivro] = []
    for i, (num, pos, titulo) in enumerate(detectadas):
        fim = (
            detectadas[i + 1][1] if i + 1 < len(detectadas) else len(html_text)
        )
        fatia = html_text[pos:fim]
        # Avaliável pelo Redato? procura mf-redato-page na fatia
        tem_avaliavel = "mf-redato-page" in fatia
        secoes = _extrair_secoes_da_fatia(fatia, max_chars_secao=max_chars_secao)
        out.append(OficinaLivro(
            codigo=_gerar_codigo_oficina(serie, num),
            serie=serie,
            oficina_numero=num,
            titulo=titulo or f"Oficina {num}",
            tem_redato_avaliavel=tem_avaliavel,
            secoes=secoes,
        ))

    logger.info(
        "[parser] %s: %d oficinas extraídas (%d avaliáveis pelo Redato)",
        html_path,
        len(out),
        sum(1 for o in out if o.tem_redato_avaliavel),
    )
    return out
