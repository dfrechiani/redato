"""Correção B2C — reutiliza o MESMO motor do fluxo escola.

Não reimplementa grader nem OCR (D6, seção "Não fazer" do spec). Só:
1. transcreve a foto com o OCR existente
   (`whatsapp.ocr.transcribe_with_quality_check`);
2. corrige o texto com o pipeline completo v2 (5 competências) via
   `dev_offline._claude_grade_essay` — passando `activity_id=None`, que
   roteia pro caminho ENEM completo (não pra um modo Foco/Parcial);
3. normaliza o `tool_args` do grader num `ResultadoCorrecao` enxuto pras
   copies M3/M6.

`grader` e `transcritor` são injetáveis: os testes passam fakes e não
tocam API nem OCR real.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ResultadoCorrecao:
    nota_total: int
    notas: Dict[str, int]          # {"c1":..,"c2":..,"c3":..,"c4":..,"c5":..}
    ponto_forte: str
    foco_melhoria: str
    raw: Dict[str, Any] = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────
# Extração pura do tool_args do grader → ResultadoCorrecao
# ──────────────────────────────────────────────────────────────────────

_COMPETENCIAS = ("c1", "c2", "c3", "c4", "c5")


def _nota_competencia(tool_args: Dict[str, Any], c: str) -> int:
    """Tenta `notas_enem[cN]`; se ausente, cai pro bloco de auditoria
    `cN_audit.nota` (schema v2)."""
    notas = tool_args.get("notas_enem") or {}
    if c in notas and notas[c] is not None:
        try:
            return int(notas[c])
        except (TypeError, ValueError):
            pass
    audit = tool_args.get(f"{c}_audit")
    if isinstance(audit, dict) and audit.get("nota") is not None:
        try:
            return int(audit["nota"])
        except (TypeError, ValueError):
            pass
    return 0


def extrair_resultado(tool_args: Dict[str, Any]) -> ResultadoCorrecao:
    """Pure. Converte o output do grader nas 5 notas + destaque + foco."""
    notas = {c: _nota_competencia(tool_args, c) for c in _COMPETENCIAS}

    total = tool_args.get("nota_total_enem")
    if total is None:
        total = tool_args.get("nota_total")
    try:
        nota_total = int(total) if total is not None else sum(notas.values())
    except (TypeError, ValueError):
        nota_total = sum(notas.values())

    fa = tool_args.get("feedback_aluno") or {}
    acertos: List[str] = [a for a in (fa.get("acertos") or []) if a]
    ajustes: List[str] = [a for a in (fa.get("ajustes") or []) if a]

    ponto_forte = acertos[0] if acertos else "sua redação tem base pra crescer"
    foco_melhoria = ajustes[0] if ajustes else "revise a estrutura e o repertório"

    return ResultadoCorrecao(
        nota_total=nota_total, notas=notas,
        ponto_forte=ponto_forte, foco_melhoria=foco_melhoria,
        raw=tool_args,
    )


# ──────────────────────────────────────────────────────────────────────
# Motor default (produção) — reutiliza o pipeline v2
# ──────────────────────────────────────────────────────────────────────

Grader = Callable[[str], Dict[str, Any]]
Transcritor = Callable[[Any], Any]


def _default_grader(texto: str, tema: Optional[str] = None) -> Dict[str, Any]:
    """Chama o grader ENEM completo pelo módulo público `grading` — MESMO
    ponto que o bot (B2G) usa (D12). Import lazy (mesmo padrão do bot no
    ramo OF14) pra não puxar dependências pesadas na import time.

    `activity_id=None` roteia pro caminho ENEM completo (5 competências).
    """
    import time
    from redato_backend.grading import grade_essay_completo
    return grade_essay_completo(
        texto,
        tema=tema or "Tema livre (redação enviada via WhatsApp)",
        activity_id=None,
        request_id=f"b2c_{int(time.time())}",
        user_id="b2c",
        force_claude=True,   # ADENDO §D7: FT não usa tema; B2C sempre Claude v2
    )


def transcrever(image_path: Any) -> Any:
    """Wrapper do OCR existente. Ponto de monkeypatch nos testes.
    Retorna um OcrResult (`.text`, `.rejected`, `.quality_issues`)."""
    from redato_backend.whatsapp.ocr import transcribe_with_quality_check
    return transcribe_with_quality_check(image_path)


def corrigir_texto(
    texto: str, *, tema: Optional[str] = None,
    grader: Optional[Grader] = None,
) -> ResultadoCorrecao:
    """Corrige um texto já transcrito CONTRA um tema (D7). `grader`
    injetável pros testes."""
    g = grader or _default_grader
    tool_args = g(texto, tema)
    return extrair_resultado(tool_args)


def estimar_custo_correcao_centavos(texto: str) -> int:
    """Estimativa de custo por correção (§D11), em centavos de BRL.

    Fórmula (documentada, aproximada por tokens):
      - OCR (Claude vision, 1 página): ~R$ 0,06 fixo.
      - Grader Claude v2: entrada ≈ prompt(~1200 tok) + redação(len/4 tok);
        saída ≈ 1500 tok. A ~US$3/1M in e US$15/1M out, câmbio ~R$5,5:
        custo ≈ (in*3 + out*15)/1e6 * 5,5 * 100 centavos.
    Não é contabilidade fiscal — é sinal de margem pro dashboard.
    """
    tokens_in = 1200 + max(0, len(texto)) // 4
    tokens_out = 1500
    grader_usd = (tokens_in * 3 + tokens_out * 15) / 1_000_000
    total_brl = 0.06 + grader_usd * 5.5
    return max(1, round(total_brl * 100))
