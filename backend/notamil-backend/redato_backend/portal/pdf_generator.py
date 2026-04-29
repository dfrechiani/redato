"""Geração de PDF dos dashboards (M8).

**Decisão técnica:** usamos ReportLab (puro Python) em vez de WeasyPrint
porque WeasyPrint depende de pango/cairo do sistema, o que segfaulta
em alguns setups macOS+conda. ReportLab é portável (zero deps de
sistema) e suficiente pros 5 elementos visuais que precisamos
renderizar — distribuição, top detectores, alunos em risco, evolução
e resumo.

Saída: bytes PDF (chamador grava em disco e registra em `PdfGerado`).
"""
from __future__ import annotations

import io
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    BaseDocTemplate, Frame, KeepTogether, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)
from reportlab.platypus.flowables import Flowable

from sqlalchemy import select
from sqlalchemy.orm import Session

from redato_backend.portal.db import get_engine
from redato_backend.portal.formatters import (
    format_missao_label_humana, format_serie,
)
from redato_backend.portal.models import (
    AlunoTurma, Atividade, Escola, Missao, Professor, Turma,
)


# ──────────────────────────────────────────────────────────────────────
# Estilos compartilhados — paleta Redato (ink + lime)
# ──────────────────────────────────────────────────────────────────────

INK = colors.HexColor("#0f1117")
LIME = colors.HexColor("#b9f01c")
INK_400 = colors.HexColor("#6b7280")
BORDER = colors.HexColor("#e6e8ec")
MUTED = colors.HexColor("#f7f7f6")
DANGER = colors.HexColor("#c43c3c")
AMBER = colors.HexColor("#f59e0b")


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle(
        name="Kicker", fontName="Helvetica-Bold", fontSize=8,
        textColor=INK_400, spaceAfter=2, leading=10,
    ))
    s.add(ParagraphStyle(
        name="DisplayTitle", fontName="Helvetica-Bold", fontSize=22,
        textColor=INK, leading=26, spaceAfter=10,
    ))
    s.add(ParagraphStyle(
        name="SectionH", fontName="Helvetica-Bold", fontSize=13,
        textColor=INK, leading=16, spaceBefore=14, spaceAfter=6,
    ))
    s.add(ParagraphStyle(
        name="Body", fontName="Helvetica", fontSize=9.5,
        textColor=INK, leading=13, spaceAfter=4,
    ))
    s.add(ParagraphStyle(
        name="Mono", fontName="Courier", fontSize=8,
        textColor=INK_400, leading=10,
    ))
    s.add(ParagraphStyle(
        name="MutedSmall", fontName="Helvetica", fontSize=8,
        textColor=INK_400, leading=10,
    ))
    return s


# ──────────────────────────────────────────────────────────────────────
# Cabeçalho / rodapé
# ──────────────────────────────────────────────────────────────────────

def _on_page(c: rl_canvas.Canvas, doc):
    """Header com logo Redato + Projeto ATO + data, footer com página
    + LGPD."""
    width, height = A4
    margin_x = 1.5 * cm

    # Header
    c.saveState()
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin_x, height - 1.3 * cm, "Redato")
    c.setFillColor(LIME)
    c.circle(margin_x + 1.6 * cm, height - 1.25 * cm, 1.2, fill=1, stroke=0)
    c.setFillColor(INK_400)
    c.setFont("Helvetica", 8)
    c.drawString(margin_x + 2.1 * cm, height - 1.3 * cm,
                 "· Projeto ATO — Portal do Professor")
    # Data no canto direito — exibe BRT pro professor brasileiro
    # ler "agora" em horário local (M9.5).
    from redato_backend.utils.timezone import now_brt
    c.drawRightString(
        width - margin_x, height - 1.3 * cm,
        now_brt().strftime("%d/%m/%Y %H:%M BRT"),
    )
    c.setStrokeColor(BORDER)
    c.line(margin_x, height - 1.6 * cm,
           width - margin_x, height - 1.6 * cm)

    # Footer
    c.setFillColor(INK_400)
    c.setFont("Helvetica", 7)
    c.drawString(
        margin_x, 1.1 * cm,
        "Documento gerado automaticamente. Notas calculadas pela IA "
        "Redato com revisão pedagógica humana.",
    )
    c.drawString(
        margin_x, 0.8 * cm,
        "LGPD: dados de alunos identificados visíveis apenas a "
        "responsáveis autorizados. Não compartilhe.",
    )
    c.drawRightString(
        width - margin_x, 0.95 * cm,
        f"página {doc.page}",
    )
    c.restoreState()


def _build_doc(buf: io.BytesIO, title: str) -> BaseDocTemplate:
    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=2.2 * cm, bottomMargin=1.6 * cm,
        title=title, author="Redato — Projeto ATO",
    )
    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height, id="normal",
    )
    template = PageTemplate(
        id="redato", frames=[frame], onPage=_on_page,
    )
    doc.addPageTemplates([template])
    return doc


# ──────────────────────────────────────────────────────────────────────
# Flowables custom: barras horizontais, line chart simples
# ──────────────────────────────────────────────────────────────────────

class HBarChart(Flowable):
    """Bar chart horizontal compacto. `data` = lista de (label, valor)."""

    def __init__(self, data: List[Tuple[str, int]], *,
                 width: float = 17 * cm, bar_height: float = 8,
                 row_spacing: float = 14, max_value: Optional[int] = None):
        super().__init__()
        self.data = data
        self.bar_w = width
        self.bar_h = bar_height
        self.row_h = row_spacing
        self.max_value = max_value or max((v for _, v in data), default=1) or 1

    def wrap(self, _avail_w, _avail_h):
        height = max(1, len(self.data)) * self.row_h
        return self.bar_w, height

    def draw(self):
        c = self.canv
        label_w = 2.6 * cm
        bar_x = label_w + 0.2 * cm
        bar_w = self.bar_w - bar_x - 1 * cm
        for i, (label, v) in enumerate(self.data):
            y = (len(self.data) - 1 - i) * self.row_h + 2
            # label
            c.setFont("Courier", 8)
            c.setFillColor(INK_400)
            c.drawString(0, y + 1, str(label))
            # track
            c.setFillColor(MUTED)
            c.rect(bar_x, y, bar_w, self.bar_h, stroke=0, fill=1)
            # bar
            pct = max(0, min(1, v / self.max_value))
            c.setFillColor(INK)
            c.rect(bar_x, y, bar_w * pct, self.bar_h, stroke=0, fill=1)
            # valor
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold", 8)
            c.drawRightString(self.bar_w, y + 1, str(v))


class LineChart(Flowable):
    """Line chart simples — pontos com linha conectando-os.

    `pontos` = lista de (label, valor). Eixo Y de 0 a `y_max`.
    """

    def __init__(self, pontos: List[Tuple[str, float]], *,
                 width: float = 17 * cm, height: float = 4.5 * cm,
                 y_max: float = 1000, y_label: str = "Nota"):
        super().__init__()
        self.pontos = pontos
        self.width = width
        self.height = height
        self.y_max = y_max
        self.y_label = y_label

    def wrap(self, _avail_w, _avail_h):
        return self.width, self.height

    def draw(self):
        c = self.canv
        if not self.pontos:
            c.setFont("Helvetica", 9)
            c.setFillColor(INK_400)
            c.drawString(0, self.height / 2, "Sem dados pra plotar.")
            return

        pad_l, pad_r, pad_t, pad_b = 1.1 * cm, 0.4 * cm, 0.3 * cm, 0.7 * cm
        plot_w = self.width - pad_l - pad_r
        plot_h = self.height - pad_t - pad_b
        ox, oy = pad_l, pad_b

        # eixos
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.5)
        c.line(ox, oy, ox + plot_w, oy)             # X
        c.line(ox, oy, ox, oy + plot_h)             # Y

        # ticks Y: 0, max/2, max
        c.setFont("Courier", 7)
        c.setFillColor(INK_400)
        for v in (0, self.y_max / 2, self.y_max):
            ypx = oy + (v / self.y_max) * plot_h
            c.line(ox - 2, ypx, ox, ypx)
            c.drawRightString(ox - 4, ypx - 2, f"{int(v)}")

        # pontos
        n = len(self.pontos)
        xs = [
            ox + (i / max(1, n - 1)) * plot_w if n > 1 else ox + plot_w / 2
            for i in range(n)
        ]
        ys = [
            oy + (max(0, min(1, v / self.y_max))) * plot_h
            for _, v in self.pontos
        ]

        # linha
        c.setStrokeColor(INK)
        c.setLineWidth(1.5)
        for i in range(1, n):
            c.line(xs[i - 1], ys[i - 1], xs[i], ys[i])
        # pontos
        c.setFillColor(INK)
        for x, y in zip(xs, ys):
            c.circle(x, y, 2.4, fill=1, stroke=0)

        # labels X (rotação leve não — só primeiros/últimos pra não poluir)
        c.setFont("Courier", 7)
        c.setFillColor(INK_400)
        labels_to_show = list(range(n)) if n <= 5 else [
            0, n // 4, n // 2, 3 * n // 4, n - 1,
        ]
        for i in labels_to_show:
            label = str(self.pontos[i][0])[:8]
            c.drawCentredString(xs[i], oy - 9, label)


# ──────────────────────────────────────────────────────────────────────
# Helpers de data + storage
# ──────────────────────────────────────────────────────────────────────

def storage_root() -> Path:
    """Diretório raiz dos PDFs. Em prod, deve ser volume persistente."""
    p = os.environ.get("STORAGE_PDFS_PATH")
    if p:
        return Path(p)
    base = Path(__file__).resolve().parents[2]
    return base / "data" / "portal" / "pdfs"


def _pdf_subpath(tipo: str, escopo_id: uuid.UUID,
                 gerado_em: datetime) -> Path:
    """Caminho relativo: <ano>/<mes>/<tipo>_<escopo>_<timestamp>.pdf"""
    ano = gerado_em.strftime("%Y")
    mes = gerado_em.strftime("%m")
    ts = gerado_em.strftime("%Y%m%dT%H%M%S")
    fname = f"{tipo}_{escopo_id.hex[:8]}_{ts}.pdf"
    return Path(ano) / mes / fname


def salvar_pdf(pdf_bytes: bytes, *, tipo: str, escopo_id: uuid.UUID,
               gerado_em: Optional[datetime] = None) -> Tuple[Path, int]:
    """Persiste o PDF no storage. Retorna (caminho_relativo, tamanho).

    Cria o diretório se não existir.
    """
    gerado_em = gerado_em or datetime.now(timezone.utc)
    rel = _pdf_subpath(tipo, escopo_id, gerado_em)
    full = storage_root() / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(pdf_bytes)
    return rel, len(pdf_bytes)


# ──────────────────────────────────────────────────────────────────────
# Blocos comuns reutilizáveis
# ──────────────────────────────────────────────────────────────────────

def _bloco_resumo(s, dados: List[Tuple[str, str]]) -> Flowable:
    """Tabela de 'cards' lado-a-lado: Label / Valor."""
    rows = [
        [Paragraph(f'<font color="#6b7280">{label}</font>', s["MutedSmall"]),
         Paragraph(f'<b>{valor}</b>', s["Body"])]
        for label, valor in dados
    ]
    t = Table(rows, colWidths=[5 * cm, 12 * cm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, BORDER),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _bloco_top_detectores(
    s, top: List[Dict[str, Any]], outros: int,
) -> List[Flowable]:
    flow: List[Flowable] = []
    if not top:
        flow.append(Paragraph("Nenhum detector pedagógico acionado.", s["Body"]))
        return flow
    rows = [
        [Paragraph(d["nome"], s["Body"]),
         Paragraph(f"×{d['contagem']}", s["Mono"])]
        for d in top
    ]
    if outros > 0:
        rows.append([
            Paragraph(f'<i>(+{outros} outros não-canônicos)</i>',
                      s["MutedSmall"]),
            Paragraph(" ", s["Body"]),
        ])
    t = Table(rows, colWidths=[14 * cm, 3 * cm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, BORDER),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    flow.append(t)
    return flow


def _bloco_distribuicao_modo(
    s, dist: Dict[str, int], modo_label: str,
) -> List[Flowable]:
    """Renderiza um bar chart pra um modo (foco ou completo)."""
    keys_foco = ["0-40", "41-80", "81-120", "121-160", "161-200"]
    keys_completo = ["0-200", "201-400", "401-600", "601-800", "801-1000"]
    keys = keys_foco if modo_label.lower().startswith("foco") else keys_completo
    data = [(k, dist.get(k, 0)) for k in keys]
    return [
        Paragraph(modo_label, s["MutedSmall"]),
        Spacer(1, 2),
        HBarChart(data),
        Spacer(1, 6),
    ]


def _bloco_alunos_risco(
    s, alunos: List[Dict[str, Any]],
) -> List[Flowable]:
    if not alunos:
        return [Paragraph(
            '<font color="#0f1117">✓ Nenhum aluno em risco identificado.</font>',
            s["Body"]
        )]
    rows = [["Aluno", "Missões abaixo", "Última nota"]]
    for a in alunos:
        rows.append([
            a["nome"],
            f"{a['n_missoes_baixa']}",
            str(a["ultima_nota"]) if a.get("ultima_nota") is not None else "—",
        ])
    t = Table(rows, colWidths=[10 * cm, 4 * cm, 3 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), MUTED),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, BORDER),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("TEXTCOLOR", (0, 1), (0, -1), INK),
    ]))
    return [t]


# ──────────────────────────────────────────────────────────────────────
# Função pública: gerar PDF dashboard turma
# ──────────────────────────────────────────────────────────────────────

@dataclass
class _TurmaCtx:
    turma_id: uuid.UUID
    codigo: str
    serie: str
    ano_letivo: int
    escola_nome: str
    professor_nome: str


def _carregar_turma_ctx(session: Session, turma_id: uuid.UUID) -> _TurmaCtx:
    turma = session.get(Turma, turma_id)
    if turma is None:
        raise ValueError(f"Turma {turma_id} não encontrada")
    escola = session.get(Escola, turma.escola_id)
    prof = session.get(Professor, turma.professor_id)
    return _TurmaCtx(
        turma_id=turma.id, codigo=turma.codigo, serie=turma.serie,
        ano_letivo=turma.ano_letivo,
        escola_nome=escola.nome if escola else "",
        professor_nome=prof.nome if prof else "",
    )


def gerar_pdf_dashboard_turma(
    turma_id: uuid.UUID, dashboard: Dict[str, Any],
    *, periodo_inicio: Optional[datetime] = None,
    periodo_fim: Optional[datetime] = None,
) -> bytes:
    """Gera PDF do dashboard de uma turma. Recebe `dashboard` no shape do
    endpoint `/portal/turmas/{id}/dashboard` (pra evitar duplicar a query)."""
    s = _styles()
    buf = io.BytesIO()
    with Session(get_engine()) as session:
        ctx = _carregar_turma_ctx(session, turma_id)

    doc = _build_doc(
        buf, title=f"Dashboard {ctx.codigo} — {ctx.escola_nome}",
    )
    flow: List[Flowable] = []

    # Cabeçalho
    flow.append(Paragraph(
        f'{ctx.escola_nome} · {format_serie(ctx.serie)} · {ctx.ano_letivo}',
        s["Kicker"]
    ))
    flow.append(Paragraph(f"Turma {ctx.codigo}", s["DisplayTitle"]))
    flow.append(Paragraph(
        f"Professor(a): {ctx.professor_nome}", s["MutedSmall"]
    ))
    if periodo_inicio or periodo_fim:
        from redato_backend.utils.timezone import fmt_brt
        ini = fmt_brt(periodo_inicio, "%d/%m/%Y") if periodo_inicio else "início"
        fim = fmt_brt(periodo_fim, "%d/%m/%Y") if periodo_fim else "agora"
        flow.append(Paragraph(f"Período: {ini} → {fim}", s["MutedSmall"]))
    flow.append(Spacer(1, 10))

    # 1. Resumo
    flow.append(Paragraph("Resumo", s["SectionH"]))
    flow.append(_bloco_resumo(s, [
        ("Alunos ativos", str(dashboard["turma"]["n_alunos_ativos"])),
        ("Atividades total", str(dashboard["atividades_total"])),
        ("Em curso", str(dashboard["atividades_ativas"])),
        ("Encerradas", str(dashboard["atividades_encerradas"])),
        ("Envios totais", str(dashboard["n_envios_total"])),
    ]))
    flow.append(Spacer(1, 8))

    # 2. Distribuição (Foco + Completo lado-a-lado conceitualmente, mas
    # pra A4 vão empilhados)
    flow.append(Paragraph("Distribuição de notas", s["SectionH"]))
    dist = dashboard["distribuicao_notas"]
    flow.extend(_bloco_distribuicao_modo(s, dist["foco"], "Foco (0-200)"))
    flow.extend(_bloco_distribuicao_modo(s, dist["completo"], "Completo (0-1000)"))

    # 3. Top detectores
    flow.append(Paragraph("Detectores pedagógicos mais acionados", s["SectionH"]))
    flow.extend(_bloco_top_detectores(
        s, dashboard["top_detectores"], dashboard["outros_detectores"],
    ))

    # 4. Alunos em risco
    flow.append(Paragraph("Alunos em risco", s["SectionH"]))
    flow.extend(_bloco_alunos_risco(s, dashboard["alunos_em_risco"]))

    # 5. Evolução
    flow.append(Paragraph("Evolução temporal", s["SectionH"]))
    from redato_backend.utils.timezone import fmt_brt
    pontos_chart = [
        (fmt_brt(datetime.fromisoformat(p["data"]), "%d/%m"), p["nota_media"])
        for p in dashboard["evolucao_turma"]
    ]
    if pontos_chart:
        # ymax adaptativo: se máxima > 200, é completo
        y_max = 1000 if any(v > 200 for _, v in pontos_chart) else 200
        flow.append(LineChart(pontos_chart, y_max=y_max, y_label="Média da turma"))
    else:
        flow.append(Paragraph(
            "Histórico aparece após 3 missões com nota.", s["MutedSmall"]))

    doc.build(flow)
    return buf.getvalue()


# ──────────────────────────────────────────────────────────────────────
# PDF dashboard escola
# ──────────────────────────────────────────────────────────────────────

def gerar_pdf_dashboard_escola(
    escola_id: uuid.UUID, dashboard: Dict[str, Any],
    *, periodo_inicio: Optional[datetime] = None,
    periodo_fim: Optional[datetime] = None,
) -> bytes:
    s = _styles()
    buf = io.BytesIO()
    doc = _build_doc(
        buf, title=f"Dashboard escola — {dashboard['escola']['nome']}",
    )
    flow: List[Flowable] = []
    esc = dashboard["escola"]

    flow.append(Paragraph(esc["nome"], s["Kicker"]))
    flow.append(Paragraph("Dashboard da escola", s["DisplayTitle"]))
    flow.append(Paragraph(
        f"{esc['n_turmas']} turma(s) · {esc['n_alunos_ativos']} aluno(s) ativo(s)",
        s["MutedSmall"],
    ))
    if periodo_inicio or periodo_fim:
        from redato_backend.utils.timezone import fmt_brt
        ini = fmt_brt(periodo_inicio, "%d/%m/%Y") if periodo_inicio else "início"
        fim = fmt_brt(periodo_fim, "%d/%m/%Y") if periodo_fim else "agora"
        flow.append(Paragraph(f"Período: {ini} → {fim}", s["MutedSmall"]))
    flow.append(Spacer(1, 10))

    # Comparação entre turmas
    flow.append(Paragraph("Comparação entre turmas", s["SectionH"]))
    if len(dashboard["comparacao_turmas"]) < 2:
        flow.append(Paragraph(
            "Comparação aparece quando há ≥ 2 turmas com dados.",
            s["MutedSmall"]))
    else:
        data = [(c["turma_codigo"], c["media"])
                for c in dashboard["comparacao_turmas"]]
        flow.append(HBarChart(data, max_value=1000))
    flow.append(Spacer(1, 6))

    # Distribuição
    flow.append(Paragraph("Distribuição de notas (escola)", s["SectionH"]))
    dist = dashboard["distribuicao_notas_escola"]
    flow.extend(_bloco_distribuicao_modo(s, dist["foco"], "Foco (0-200)"))
    flow.extend(_bloco_distribuicao_modo(s, dist["completo"], "Completo (0-1000)"))

    # Top detectores
    flow.append(Paragraph("Detectores pedagógicos (escola)", s["SectionH"]))
    flow.extend(_bloco_top_detectores(
        s, dashboard["top_detectores_escola"],
        dashboard["outros_detectores_escola"],
    ))

    # Alunos em risco
    flow.append(Paragraph("Alunos em risco — escola", s["SectionH"]))
    flow.extend(_bloco_alunos_risco(s, dashboard["alunos_em_risco_escola"]))

    # Evolução
    flow.append(Paragraph("Evolução agregada", s["SectionH"]))
    from redato_backend.utils.timezone import fmt_brt
    pontos = [
        (fmt_brt(datetime.fromisoformat(p["data"]), "%d/%m"), p["nota_media"])
        for p in dashboard["evolucao_escola"]
    ]
    if pontos:
        y_max = 1000 if any(v > 200 for _, v in pontos) else 200
        flow.append(LineChart(pontos, y_max=y_max, y_label="Média"))
    else:
        flow.append(Paragraph(
            "Histórico aparece após 3 missões com nota.", s["MutedSmall"]))

    # Resumo de turmas
    flow.append(Paragraph("Turmas", s["SectionH"]))
    rows = [["Turma", "Série", "Professor", "Atividades", "Em risco", "Média"]]
    for t in dashboard["turmas_resumo"]:
        rows.append([
            t["codigo"], format_serie(t["serie"]), t["professor_nome"][:30],
            str(t["n_atividades"]), str(t["n_em_risco"]),
            str(t["media_geral"]) if t["media_geral"] is not None else "—",
        ])
    tabela = Table(rows, colWidths=[2 * cm, 1.5 * cm, 6 * cm,
                                     2.5 * cm, 2.5 * cm, 2.5 * cm])
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), MUTED),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, BORDER),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))
    flow.append(tabela)

    doc.build(flow)
    return buf.getvalue()


# ──────────────────────────────────────────────────────────────────────
# PDF evolução do aluno
# ──────────────────────────────────────────────────────────────────────

def gerar_pdf_evolucao_aluno(
    aluno_turma_id: uuid.UUID, evolucao: Dict[str, Any],
    *, turma_codigo: str, escola_nome: str,
) -> bytes:
    s = _styles()
    buf = io.BytesIO()
    doc = _build_doc(
        buf, title=f"Evolução {evolucao['aluno']['nome']}",
    )
    flow: List[Flowable] = []

    flow.append(Paragraph(
        f"{escola_nome} · Turma {turma_codigo}", s["Kicker"]
    ))
    flow.append(Paragraph(evolucao["aluno"]["nome"], s["DisplayTitle"]))
    flow.append(Paragraph(
        f"{evolucao['n_missoes_realizadas']} missão(ões) realizada(s) · "
        f"{len(evolucao['missoes_pendentes'])} pendente(s)",
        s["MutedSmall"],
    ))
    flow.append(Spacer(1, 10))

    # Chart
    flow.append(Paragraph("Evolução das notas", s["SectionH"]))
    pontos = evolucao["evolucao_chart"]
    if pontos:
        # yMax adaptativo: se todos os envios são Foco (modo começa com
        # foco_), usa 200; senão 1000
        envios = evolucao.get("envios", [])
        todos_foco = bool(envios) and all(
            e.get("modo", "").startswith("foco_") for e in envios
        )
        y_max = 200 if todos_foco else 1000
        from redato_backend.utils.timezone import fmt_brt
        chart_data = [
            (fmt_brt(datetime.fromisoformat(p["data"]), "%d/%m"), p["nota"])
            for p in pontos
        ]
        flow.append(LineChart(chart_data, y_max=y_max, y_label="Nota"))
    else:
        flow.append(Paragraph(
            "Aluno ainda não realizou missões.", s["MutedSmall"]))

    # Missões realizadas
    flow.append(Paragraph("Missões realizadas", s["SectionH"]))
    if not evolucao["envios"]:
        flow.append(Paragraph("Nenhum envio.", s["MutedSmall"]))
    else:
        from redato_backend.utils.timezone import fmt_brt
        rows = [["Data", "Missão", "Nota", "Faixa"]]
        for e in evolucao["envios"]:
            data_pt = fmt_brt(datetime.fromisoformat(e["data"]), "%d/%m/%Y")
            label = format_missao_label_humana(
                oficina_numero=e.get("oficina_numero"),
                titulo=e.get("missao_titulo"),
                modo_correcao=e.get("modo"),
            )
            rows.append([
                data_pt, label,
                str(e["nota"]) if e["nota"] is not None else "—",
                e["faixa"],
            ])
        tabela = Table(rows, colWidths=[2.5 * cm, 9 * cm,
                                         2 * cm, 3.5 * cm])
        tabela.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), MUTED),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, BORDER),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]))
        flow.append(tabela)

    # Missões pendentes
    if evolucao["missoes_pendentes"]:
        flow.append(Paragraph("Missões pendentes", s["SectionH"]))
        from redato_backend.utils.timezone import fmt_brt
        rows = [["Missão", "Prazo", "Status"]]
        for m in evolucao["missoes_pendentes"]:
            data_fim = fmt_brt(datetime.fromisoformat(m["data_fim"]), "%d/%m/%Y")
            label = format_missao_label_humana(
                oficina_numero=m.get("oficina_numero"),
                titulo=m.get("missao_titulo"),
                modo_correcao=m.get("modo_correcao"),
            )
            rows.append([label, data_fim, m["status"]])
        tabela = Table(rows, colWidths=[10 * cm, 3 * cm, 4 * cm])
        tabela.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), MUTED),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, BORDER),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]))
        flow.append(tabela)

    doc.build(flow)
    return buf.getvalue()
