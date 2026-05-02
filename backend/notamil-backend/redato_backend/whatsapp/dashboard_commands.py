"""Dispatcher de comandos do dashboard professor via WhatsApp (M10
PROMPT 2/2).

Substitui o `MSG_DASHBOARD_PLACEHOLDER` da PROMPT 1 (commit 160fb5c)
por 3 comandos estruturados + ajuda:

- `/turma <codigo>`: resumo da turma (alunos, atividades, médias C1-C5,
  top 3, alertas).
- `/aluno <nome>`: histórico do aluno (últimos 5 envios, tendência,
  pontos fortes/fracos).
- `/atividade <codigo>`: status (envios x cadastrados, distribuição
  de notas, médias, lista de pendentes).
- `/ajuda`: lista de comandos.

Todas as respostas filtram por `escola_id` do professor — LGPD: prof
não vê dados de outras escolas. Não-match retorna 404 amigável.

Reusa `_nota_total_de` de portal_api pra parse robusto do redato_output
(cobre formatos FT, Sonnet legacy, etc.).

Defensivo: qualquer exceção (DB indisponível, schema parcial, etc.)
captura e retorna mensagem amigável — bot não derruba o handler.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Parser de comando
# ──────────────────────────────────────────────────────────────────────
#
# Aceita variações: "/turma 1A", "turma 1A", "/Turma  1A" (case-
# insensitive, com ou sem barra inicial, espaços extras tolerados).

_COMANDO_RE = re.compile(
    r"^\s*/?(turma|aluno|atividade|ajuda|help)\s*(.*?)\s*$",
    re.IGNORECASE,
)


def parse_comando(text: Optional[str]) -> Optional[Tuple[str, str]]:
    """Extrai (comando_canonico, args) de uma mensagem do professor.

    Retorna None se não bate em nenhum comando — caller mostra ajuda.
    `comando_canonico` é lowercase ("turma" / "aluno" / "atividade" /
    "ajuda"). `args` é a string restante (pode ser vazia).
    """
    if not text:
        return None
    m = _COMANDO_RE.match(text)
    if m is None:
        return None
    cmd = m.group(1).lower()
    if cmd == "help":
        cmd = "ajuda"
    args = (m.group(2) or "").strip()
    return cmd, args


# ──────────────────────────────────────────────────────────────────────
# Faixas qualitativas (reuso simplificado do whatsapp/render.py)
# ──────────────────────────────────────────────────────────────────────

def _faixa_total_1000(total: Optional[int]) -> str:
    if total is None:
        return "—"
    if total >= 901: return "EXCELENTE"
    if total >= 801: return "BOM"
    if total >= 601: return "REGULAR"
    if total >= 401: return "EM DESENVOLVIMENTO"
    return "INSUFICIENTE"


# Buckets de distribuição (mesmos do dashboard portal — escala 0-1000
# com agrupamento mais largo pra não inflar mensagem WhatsApp).
def _bucket_completo(nota: int) -> str:
    if nota >= 800: return "800-1000"
    if nota >= 600: return "600-799"
    if nota >= 400: return "400-599"
    return "<400"


_BUCKETS_ORDEM = ("800-1000", "600-799", "400-599", "<400")


# ──────────────────────────────────────────────────────────────────────
# Parse de redato_output — reusa lógica de portal_api._nota_total_de
# ──────────────────────────────────────────────────────────────────────

def _parse_redato(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    """Decode JSON do `interactions.redato_output` (Text). Tolera
    string vazia, None, JSON inválido — retorna None."""
    if not raw:
        return None
    try:
        d = json.loads(raw)
    except (json.JSONDecodeError, ValueError, TypeError):
        return None
    return d if isinstance(d, dict) else None


def _nota_total_de(redato: Optional[Dict[str, Any]]) -> Optional[int]:
    """Extrai nota total de um redato_output. Cobre múltiplos formatos
    (cópia simplificada de portal_api._nota_total_de pra evitar import
    circular ou pesado)."""
    if not redato:
        return None
    modo = redato.get("modo")
    if isinstance(modo, str):
        if modo.startswith("foco_c"):
            n = modo[len("foco_"):]
            v = redato.get(f"nota_{n}_enem")
            if isinstance(v, (int, float)):
                return int(v)
        elif modo.startswith("completo"):
            v = redato.get("nota_total_enem")
            if isinstance(v, (int, float)):
                return int(v)
            v = redato.get("nota_total")
            if isinstance(v, (int, float)):
                return int(v)
    # Soma C1-C5 (formato FT BTBOS5VF — cN_audit.nota)
    soma = 0
    contadas = 0
    for k in ("c1_audit", "c2_audit", "c3_audit", "c4_audit", "c5_audit"):
        bloco = redato.get(k)
        if isinstance(bloco, dict):
            v = bloco.get("nota")
            if isinstance(v, (int, float)):
                soma += int(v)
                contadas += 1
    if contadas == 5:
        return soma
    # Fallback flat
    for key in ("nota_total", "total", "nota"):
        v = redato.get(key)
        if isinstance(v, (int, float)):
            return int(v)
    return None


def _notas_por_competencia(
    redato: Optional[Dict[str, Any]],
) -> Optional[Dict[str, int]]:
    """Extrai dict {c1, c2, c3, c4, c5} de um redato_output em formato
    OF14 (cN_audit.nota). Retorna None se não bate o padrão."""
    if not redato:
        return None
    out: Dict[str, int] = {}
    for k in ("c1_audit", "c2_audit", "c3_audit", "c4_audit", "c5_audit"):
        bloco = redato.get(k)
        if not isinstance(bloco, dict):
            return None
        v = bloco.get("nota")
        if not isinstance(v, (int, float)):
            return None
        out[k.replace("_audit", "")] = int(v)
    return out


def _redato_tem_erro(redato: Optional[Dict[str, Any]]) -> bool:
    """True se o redato_output contém erro de pipeline (correção
    falhou). Usa pra contar 'envios sem nota' nos resumos."""
    if not redato:
        return True
    if isinstance(redato.get("error"), str):
        return True
    return _nota_total_de(redato) is None


# ──────────────────────────────────────────────────────────────────────
# Sessão Postgres — encapsula try/except pra defensiva uniforme
# ──────────────────────────────────────────────────────────────────────

def _open_session() -> Optional[Session]:
    """Abre Session(get_engine()) ou retorna None se DB indisponível.
    Caller decide a mensagem de erro."""
    try:
        from redato_backend.portal.db import get_engine
        return Session(get_engine())
    except Exception as exc:  # noqa: BLE001
        logger.warning("dashboard_commands: DB indisponível (%s)", exc)
        return None


# ──────────────────────────────────────────────────────────────────────
# Comando /turma
# ──────────────────────────────────────────────────────────────────────

def cmd_turma(prof_id: uuid.UUID, escola_id: uuid.UUID, args: str) -> str:
    """Resumo da turma. `args` é o código (ex: "1A"). Filtra por
    escola_id pra LGPD — prof não vê dados de outras escolas."""
    from redato_backend.portal.models import (
        Atividade, AlunoTurma, Envio, Interaction, Missao, Turma,
    )
    from redato_backend.whatsapp import messages as MSG

    codigo = (args or "").strip().upper()
    if not codigo:
        return MSG.MSG_DASHBOARD_USO_TURMA

    sess = _open_session()
    if sess is None:
        return MSG.MSG_DASHBOARD_DB_INDISPONIVEL

    try:
        # 1. Turma na escola do prof
        turma = sess.scalar(
            select(Turma).where(
                func.upper(Turma.codigo) == codigo,
                Turma.escola_id == escola_id,
                Turma.deleted_at.is_(None),
            )
        )
        if turma is None:
            return MSG.MSG_TURMA_NAO_ENCONTRADA.format(codigo=codigo)

        # 2. Conta alunos ativos
        n_alunos = sess.scalar(
            select(func.count(AlunoTurma.id)).where(
                AlunoTurma.turma_id == turma.id,
                AlunoTurma.ativo.is_(True),
            )
        ) or 0

        # 3. Atividades ativas (now BETWEEN data_inicio E data_fim)
        agora = datetime.now(timezone.utc)
        atvs_ativas = sess.execute(
            select(Atividade, Missao).join(
                Missao, Missao.id == Atividade.missao_id,
            ).where(
                Atividade.turma_id == turma.id,
                Atividade.deleted_at.is_(None),
                Atividade.data_inicio <= agora,
                Atividade.data_fim >= agora,
            )
        ).all()
        codigos_ativos = sorted({m.codigo for _, m in atvs_ativas})

        # 4. Envios dos últimos 30 dias com redato_output
        cutoff = agora - timedelta(days=30)
        rows = sess.execute(
            select(Envio, Interaction, AlunoTurma)
            .join(Interaction, Interaction.id == Envio.interaction_id)
            .join(AlunoTurma, AlunoTurma.id == Envio.aluno_turma_id)
            .join(Atividade, Atividade.id == Envio.atividade_id)
            .where(
                Atividade.turma_id == turma.id,
                Envio.enviado_em >= cutoff,
            )
        ).all()

        # 5. Agrega: notas C1-C5 + total + erro
        soma_cn: Dict[str, List[int]] = {f"c{i}": [] for i in range(1, 6)}
        totais: List[Tuple[int, str]] = []  # (nota_total, aluno_nome)
        n_erro = 0
        ids_com_envio = set()
        for envio, inter, aluno in rows:
            ids_com_envio.add(aluno.id)
            redato = _parse_redato(inter.redato_output)
            if _redato_tem_erro(redato):
                n_erro += 1
                continue
            notas_cn = _notas_por_competencia(redato)
            if notas_cn:
                for k, v in notas_cn.items():
                    soma_cn[k].append(v)
            total = _nota_total_de(redato)
            if total is not None:
                totais.append((total, aluno.nome))

        # 6. Top 3 alunos por nota total (mais recente já vem pelo
        # filter; pra simplificar usamos a média do aluno se aparecer
        # várias vezes, mas mensagem WhatsApp pega só top 3 pela
        # melhor nota observada).
        melhor_por_aluno: Dict[str, int] = {}
        for nota, nome in totais:
            if nota > melhor_por_aluno.get(nome, -1):
                melhor_por_aluno[nome] = nota
        top3 = sorted(melhor_por_aluno.items(), key=lambda x: -x[1])[:3]

        # 7. Alunos sem envio na atividade ativa principal (OF14 se
        # houver, senão a 1ª ativa). Simplificação pra mensagem curta:
        # só mostra count.
        sem_envio = sess.scalar(
            select(func.count(AlunoTurma.id)).where(
                AlunoTurma.turma_id == turma.id,
                AlunoTurma.ativo.is_(True),
                ~AlunoTurma.id.in_(ids_com_envio),
            )
        ) or 0

        return _render_resumo_turma(
            turma=turma, n_alunos=n_alunos,
            codigos_ativos=codigos_ativos,
            soma_cn=soma_cn, top3=top3,
            n_erro=n_erro, n_sem_envio=sem_envio,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("cmd_turma falhou pra escola=%s codigo=%s",
                         escola_id, codigo)
        return MSG.MSG_DASHBOARD_ERRO_GENERICO
    finally:
        sess.close()


def _render_resumo_turma(
    *, turma, n_alunos: int, codigos_ativos: List[str],
    soma_cn: Dict[str, List[int]], top3: List[Tuple[str, int]],
    n_erro: int, n_sem_envio: int,
) -> str:
    """Render do resumo da turma. Cap ~1500 chars (cabe em 1 chunk
    Twilio). Linhas omitidas quando dados ausentes pra não poluir."""
    serie_label = (
        f" — {turma.serie}" if getattr(turma, "serie", None) else ""
    )
    parts: List[str] = []
    parts.append(f"📊 *Turma {turma.codigo}*{serie_label}")
    parts.append("")
    parts.append(f"Alunos cadastrados: *{n_alunos}*")
    parts.append(
        f"Atividades ativas: *{len(codigos_ativos)}*"
        + (f" ({', '.join(codigos_ativos)})" if codigos_ativos else "")
    )

    # Médias C1-C5 (só se houver dados)
    medias = {}
    for k, vals in soma_cn.items():
        if vals:
            medias[k] = round(sum(vals) / len(vals))
    if medias:
        media_total = sum(medias.values())
        parts.append("")
        parts.append("📈 *Médias últimos 30 dias:*")
        parts.append(
            " · ".join(f"{k.upper()} {v}" for k, v in medias.items())
        )
        parts.append(
            f"Geral: *{media_total}/1000* "
            f"({_faixa_total_1000(media_total)})"
        )

    if top3:
        parts.append("")
        parts.append("🏆 *Top 3:*")
        for i, (nome, nota) in enumerate(top3, 1):
            parts.append(f"{i}. {nome} — {nota}")

    alertas: List[str] = []
    if n_erro > 0:
        alertas.append(
            f"{n_erro} envio(s) com correção falha "
            "(use o portal pra reprocessar)"
        )
    if n_sem_envio > 0:
        alertas.append(
            f"{n_sem_envio} aluno(s) sem envio nos últimos 30 dias"
        )
    if alertas:
        parts.append("")
        parts.append("⚠️ *Atenção:*")
        for a in alertas:
            parts.append(f"- {a}")

    parts.append("")
    parts.append("_Pra mais: /aluno <nome> ou /atividade <codigo>_")
    return "\n".join(parts)


# ──────────────────────────────────────────────────────────────────────
# Comando /aluno
# ──────────────────────────────────────────────────────────────────────

def cmd_aluno(prof_id: uuid.UUID, escola_id: uuid.UUID, args: str) -> str:
    """Histórico do aluno por nome (busca fuzzy ILIKE %nome%).
    Múltiplos matches → lista pra refinar."""
    from redato_backend.portal.models import (
        Atividade, AlunoTurma, Envio, Interaction, Missao, Turma,
    )
    from redato_backend.whatsapp import messages as MSG

    nome = (args or "").strip()
    if not nome or len(nome) < 2:
        return MSG.MSG_DASHBOARD_USO_ALUNO

    sess = _open_session()
    if sess is None:
        return MSG.MSG_DASHBOARD_DB_INDISPONIVEL

    try:
        # Busca fuzzy: ILIKE %nome% nas turmas da escola do prof
        matches = sess.execute(
            select(AlunoTurma, Turma)
            .join(Turma, Turma.id == AlunoTurma.turma_id)
            .where(
                AlunoTurma.nome.ilike(f"%{nome}%"),
                AlunoTurma.ativo.is_(True),
                Turma.escola_id == escola_id,
                Turma.deleted_at.is_(None),
            )
            .order_by(AlunoTurma.nome)
            .limit(6)
        ).all()

        if not matches:
            return MSG.MSG_ALUNO_NAO_ENCONTRADO.format(nome=nome)

        if len(matches) > 1:
            # Múltiplos matches — pede pra refinar
            linhas = [
                f"{i+1}. {at.nome} — {t.codigo}"
                for i, (at, t) in enumerate(matches[:5])
            ]
            extra = ""
            if len(matches) > 5:
                extra = f"\n_(...e mais {len(matches) - 5})_"
            return MSG.MSG_ALUNO_MULTIPLOS_MATCHES.format(
                nome=nome,
                lista="\n".join(linhas) + extra,
            )

        aluno_at, turma = matches[0]

        # Últimos 5 envios
        envios = sess.execute(
            select(Envio, Interaction, Missao, Atividade)
            .join(Atividade, Atividade.id == Envio.atividade_id)
            .join(Missao, Missao.id == Atividade.missao_id)
            .join(Interaction, Interaction.id == Envio.interaction_id)
            .where(Envio.aluno_turma_id == aluno_at.id)
            .order_by(Envio.enviado_em.desc())
            .limit(5)
        ).all()

        if not envios:
            return (
                f"👤 *{aluno_at.nome}* — Turma {turma.codigo}\n\n"
                f"Ainda não enviou nenhuma redação."
            )

        return _render_historico_aluno(
            aluno=aluno_at, turma=turma, envios=envios,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("cmd_aluno falhou pra escola=%s nome=%s",
                         escola_id, nome)
        return MSG.MSG_DASHBOARD_ERRO_GENERICO
    finally:
        sess.close()


def _render_historico_aluno(*, aluno, turma, envios) -> str:
    """Render do histórico de aluno: 5 últimos envios + tendência +
    pontos fortes/fracos."""
    parts: List[str] = []
    parts.append(f"👤 *{aluno.nome}* — Turma {turma.codigo}")
    parts.append("")
    parts.append("*Últimos envios:*")

    notas_totais: List[int] = []
    soma_cn: Dict[str, List[int]] = {f"c{i}": [] for i in range(1, 6)}

    for i, (envio, inter, missao, atv) in enumerate(envios, 1):
        redato = _parse_redato(inter.redato_output)
        total = _nota_total_de(redato) if redato else None
        notas_cn = _notas_por_competencia(redato) if redato else None

        data_str = envio.enviado_em.strftime("%d/%m %H:%M")
        cabec = f"{i}. {data_str} — {missao.codigo}"
        parts.append("")
        parts.append(cabec)
        if total is not None:
            notas_totais.append(total)
            faixa = _faixa_total_1000(total)
            parts.append(f"   Nota: *{total}/1000* ({faixa})")
        elif _redato_tem_erro(redato):
            parts.append("   _Correção falhou — reprocessar no portal_")
        else:
            parts.append("   _Sem nota_")
        if notas_cn:
            for k, v in notas_cn.items():
                soma_cn[k].append(v)
            inline = " · ".join(
                f"{k.upper()} {v}" for k, v in notas_cn.items()
            )
            parts.append(f"   {inline}")

    # Tendência
    if len(notas_totais) >= 2:
        media_recente = sum(notas_totais[:2]) / 2
        media_antiga = sum(notas_totais[2:]) / max(1, len(notas_totais) - 2)
        if media_recente > media_antiga + 30:
            tendencia = "subindo 📈"
        elif media_recente < media_antiga - 30:
            tendencia = "caindo 📉"
        else:
            tendencia = "estável"
        parts.append("")
        parts.append(
            f"📊 Média: *{round(sum(notas_totais)/len(notas_totais))}/1000* "
            f"({tendencia})"
        )

    # Pontos fortes/fracos
    medias_cn = {
        k: round(sum(v) / len(v)) for k, v in soma_cn.items() if v
    }
    if len(medias_cn) >= 3:
        ordenadas = sorted(medias_cn.items(), key=lambda x: x[1])
        fracos = ", ".join(k.upper() for k, _ in ordenadas[:2])
        fortes = ", ".join(k.upper() for k, _ in ordenadas[-2:])
        parts.append(f"Pontos fortes: *{fortes}*")
        parts.append(f"Pontos fracos: *{fracos}*")

    parts.append("")
    parts.append("_Feedback completo no portal._")
    return "\n".join(parts)


# ──────────────────────────────────────────────────────────────────────
# Comando /atividade
# ──────────────────────────────────────────────────────────────────────

def cmd_atividade(
    prof_id: uuid.UUID, escola_id: uuid.UUID, args: str,
) -> str:
    """Status de atividade pelo código. Filtra por escola_id (LGPD)."""
    from redato_backend.portal.models import (
        Atividade, AlunoTurma, Envio, Interaction, Missao, Turma,
    )
    from redato_backend.whatsapp import messages as MSG

    codigo = (args or "").strip()
    if not codigo:
        return MSG.MSG_DASHBOARD_USO_ATIVIDADE
    codigo_upper = codigo.upper()

    sess = _open_session()
    if sess is None:
        return MSG.MSG_DASHBOARD_DB_INDISPONIVEL

    try:
        # Busca atividade(s): ILIKE no missao.codigo (aceita "OF14"
        # vs "RJ1·OF14·MF") na escola do prof. Pode haver múltiplas
        # se mesmo código em turmas diferentes — pede desambiguação.
        atvs = sess.execute(
            select(Atividade, Missao, Turma)
            .join(Missao, Missao.id == Atividade.missao_id)
            .join(Turma, Turma.id == Atividade.turma_id)
            .where(
                or_(
                    Missao.codigo.ilike(f"%{codigo_upper}%"),
                    func.upper(Missao.codigo) == codigo_upper,
                ),
                Turma.escola_id == escola_id,
                Atividade.deleted_at.is_(None),
                Turma.deleted_at.is_(None),
            )
            .order_by(Atividade.data_fim.desc())
            .limit(5)
        ).all()

        if not atvs:
            return MSG.MSG_ATIVIDADE_NAO_ENCONTRADA.format(codigo=codigo)

        if len(atvs) > 1:
            linhas = [
                f"{i+1}. {m.codigo} — Turma {t.codigo} "
                f"(prazo {a.data_fim.strftime('%d/%m')})"
                for i, (a, m, t) in enumerate(atvs)
            ]
            return MSG.MSG_ATIVIDADE_MULTIPLOS_MATCHES.format(
                codigo=codigo, lista="\n".join(linhas),
            )

        atv, missao, turma = atvs[0]

        # Total de alunos cadastrados na turma
        n_alunos = sess.scalar(
            select(func.count(AlunoTurma.id)).where(
                AlunoTurma.turma_id == turma.id,
                AlunoTurma.ativo.is_(True),
            )
        ) or 0

        # Envios (com texto redato_output pra calcular notas)
        rows = sess.execute(
            select(Envio, Interaction, AlunoTurma)
            .join(Interaction, Interaction.id == Envio.interaction_id)
            .join(AlunoTurma, AlunoTurma.id == Envio.aluno_turma_id)
            .where(Envio.atividade_id == atv.id)
        ).all()

        ids_com_envio: set = set()
        notas_totais: List[int] = []
        soma_cn: Dict[str, List[int]] = {f"c{i}": [] for i in range(1, 6)}
        n_erro = 0
        nomes_com_erro: List[str] = []
        for envio, inter, aluno in rows:
            ids_com_envio.add(aluno.id)
            redato = _parse_redato(inter.redato_output)
            if _redato_tem_erro(redato):
                n_erro += 1
                nomes_com_erro.append(aluno.nome)
                continue
            total = _nota_total_de(redato)
            if total is not None:
                notas_totais.append(total)
            notas_cn = _notas_por_competencia(redato)
            if notas_cn:
                for k, v in notas_cn.items():
                    soma_cn[k].append(v)

        # Pendentes (alunos da turma sem envio nessa atividade)
        pendentes = sess.execute(
            select(AlunoTurma.nome)
            .where(
                AlunoTurma.turma_id == turma.id,
                AlunoTurma.ativo.is_(True),
                ~AlunoTurma.id.in_(ids_com_envio),
            )
            .order_by(AlunoTurma.nome)
        ).scalars().all()

        return _render_status_atividade(
            atv=atv, missao=missao, turma=turma,
            n_alunos=n_alunos, n_envios=len(ids_com_envio),
            notas_totais=notas_totais, soma_cn=soma_cn,
            pendentes=list(pendentes),
            n_erro=n_erro, nomes_com_erro=nomes_com_erro,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("cmd_atividade falhou pra escola=%s codigo=%s",
                         escola_id, codigo)
        return MSG.MSG_DASHBOARD_ERRO_GENERICO
    finally:
        sess.close()


def _render_status_atividade(
    *, atv, missao, turma, n_alunos: int, n_envios: int,
    notas_totais: List[int], soma_cn: Dict[str, List[int]],
    pendentes: List[str], n_erro: int, nomes_com_erro: List[str],
) -> str:
    """Render do status da atividade. Trunca lista de pendentes pra
    máx 10 nomes; mostra contagem se ultrapassa."""
    parts: List[str] = []
    parts.append(f"📝 *{missao.codigo}* — {missao.titulo}")
    parts.append(f"Turma {turma.codigo}")
    prazo = atv.data_fim.strftime("%d/%m %H:%M")
    parts.append(f"Prazo: até *{prazo}*")
    parts.append("")
    pct = round(100 * n_envios / n_alunos) if n_alunos else 0
    parts.append(
        f"Envios: *{n_envios} de {n_alunos}* alunos ({pct}%)"
    )

    # Distribuição de notas
    if notas_totais:
        buckets: Dict[str, int] = {b: 0 for b in _BUCKETS_ORDEM}
        for n in notas_totais:
            buckets[_bucket_completo(n)] += 1
        parts.append("")
        parts.append("*Distribuição:*")
        for b in _BUCKETS_ORDEM:
            if buckets[b] > 0:
                parts.append(f"  {b}: {buckets[b]}")

    # Médias C1-C5
    medias = {
        k: round(sum(v) / len(v)) for k, v in soma_cn.items() if v
    }
    if medias:
        parts.append("")
        parts.append("*Médias:*")
        parts.append(
            " · ".join(f"{k.upper()} {v}" for k, v in medias.items())
        )

    # Pendentes
    if pendentes:
        parts.append("")
        parts.append(f"❌ *Não enviaram ({len(pendentes)}):*")
        if len(pendentes) <= 10:
            parts.append(", ".join(pendentes))
        else:
            mostrar = ", ".join(pendentes[:10])
            extra = len(pendentes) - 10
            parts.append(f"{mostrar}, ...e mais {extra}")

    # Erros
    if n_erro > 0:
        parts.append("")
        parts.append(f"⚠️ *Envios com problema ({n_erro}):*")
        if len(nomes_com_erro) <= 5:
            for nome in nomes_com_erro:
                parts.append(f"  {nome}")
        else:
            for nome in nomes_com_erro[:5]:
                parts.append(f"  {nome}")
            parts.append(f"  ...e mais {len(nomes_com_erro) - 5}")
        parts.append("_(use o portal pra reprocessar)_")

    return "\n".join(parts)


# ──────────────────────────────────────────────────────────────────────
# Comando /ajuda
# ──────────────────────────────────────────────────────────────────────

def cmd_ajuda(prof_id: uuid.UUID, escola_id: uuid.UUID) -> str:
    from redato_backend.whatsapp import messages as MSG
    return MSG.MSG_DASHBOARD_AJUDA


# ──────────────────────────────────────────────────────────────────────
# Dispatcher (entry point chamado pelo bot)
# ──────────────────────────────────────────────────────────────────────

def dispatch(
    prof_id: uuid.UUID,
    escola_id: uuid.UUID,
    text: Optional[str],
) -> str:
    """Parsa o texto, roteia pro handler e retorna a string da resposta.
    Caller (bot.py) embrulha em OutboundMessage.

    Tipa entrada cuidadosamente: prof_id + escola_id são UUIDs (já
    extraídos do ProfessorVinculo) — nada de string aqui.

    Retorna sempre uma string (mensagem amigável). Erros internos
    geram MSG_DASHBOARD_ERRO_GENERICO em vez de exception — bot.py
    não precisa de try/except adicional.
    """
    from redato_backend.whatsapp import messages as MSG

    parsed = parse_comando(text)
    if parsed is None:
        # Texto sem comando reconhecido → mostra ajuda
        return MSG.MSG_DASHBOARD_AJUDA
    cmd, args = parsed

    if cmd == "ajuda":
        return cmd_ajuda(prof_id, escola_id)
    if cmd == "turma":
        return cmd_turma(prof_id, escola_id, args)
    if cmd == "aluno":
        return cmd_aluno(prof_id, escola_id, args)
    if cmd == "atividade":
        return cmd_atividade(prof_id, escola_id, args)

    # Não deveria chegar aqui (parse_comando filtra), mas defesa.
    return MSG.MSG_DASHBOARD_AJUDA
