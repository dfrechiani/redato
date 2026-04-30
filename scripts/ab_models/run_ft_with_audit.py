"""Experimento isolado: testar se o GPT-FT BTBOS5VF gera audit
estruturado (formato OF14) sem re-treino, apenas com prompt enriquecido.

Contexto:
  A/B 30/abr (REPORT_AB_20260430_105858.md) mostrou FT vencedor em
  ±40 (21.5%), mas treino focou em SÓ notas — não retorna audit
  detalhado por competência. Antes de gastar $50-150 em re-treino,
  testar se prompt enriquecido já consegue.

Schema simplificado pedido ao FT (subset viável do OF14):
    {
      "c1_audit": {"nota": int, "feedback_text": str, "evidencias": [{"trecho": str, "comentario": str}]},
      "c2_audit": {...},
      ...
      "c5_audit": {...}
    }

NÃO pede o schema completo OF14 (12 campos por cN — desvios listados,
contagens, threshold_check, etc.) porque seria irrealista sem treino.
Esse subset é o mínimo pra renderizar útil no frontend.

Uso:
    cd /Users/danielfrechiani/Desktop/redato_hash
    export OPENAI_API_KEY=sk-...
    python scripts/ab_models/run_ft_with_audit.py
    python scripts/ab_models/run_ft_with_audit.py --skip-smoke
    python scripts/ab_models/run_ft_with_audit.py --resume <ts>
    python scripts/ab_models/run_ft_with_audit.py --report-only <ts>

Saída:
    scripts/ab_models/results/eval_ft_with_audit_<TS>.jsonl
    scripts/ab_models/results/REPORT_FT_AUDIT_<TS>.md

results/ está no .gitignore — só este script entra em commit.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Set, Tuple


REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend" / "notamil-backend"
EVAL_PATH = (
    BACKEND / "scripts" / "validation" / "data" / "eval_gold_v1.jsonl"
)
RESULTS_DIR = Path(__file__).resolve().parent / "results"

FT_MODEL = "ft:gpt-4.1-2025-04-14:redato:redato-enem:BTBOS5VF"
MODELO_LABEL = f"{FT_MODEL} (audit-enriched)"

SMOKE_N = 5
MAX_WORKERS = 5
MAX_TOKENS = 6000  # mais que o run_ab.py (4000) pq audit consome mais

# Pricing FT do gpt-4.1 (mesma tabela do grade_ft.py)
PRECO_INPUT_USD_POR_MTOK = 5.0
PRECO_OUTPUT_USD_POR_MTOK = 20.0

# Baseline conhecido do A/B 30/abr (FT só notas) — citado no relatório
BASELINE_FT_PCT_40 = 21.5
BASELINE_FT_CUSTO_RED = 0.025
BASELINE_FT_LATENCIA_S = 3.2


# ──────────────────────────────────────────────────────────────────────
# Bootstrap
# ──────────────────────────────────────────────────────────────────────

def _bootstrap_backend() -> None:
    """Coloca backend/ no sys.path pra importar _SYSTEM_PROMPT_BASE."""
    s = str(BACKEND)
    if s not in sys.path:
        sys.path.insert(0, s)


# ──────────────────────────────────────────────────────────────────────
# Prompt enriquecido — pede audit estruturado no schema simplificado
# ──────────────────────────────────────────────────────────────────────

USER_MSG_TEMPLATE = """TEMA: {tema}

REDAÇÃO DO ALUNO:
\"\"\"
{texto}
\"\"\"

Avalie a redação acima pelas 5 competências ENEM. Retorne EXCLUSIVAMENTE \
um JSON com esta estrutura (sem texto antes/depois, sem markdown fence):

{{
  "c1_audit": {{
    "nota": <0|40|80|120|160|200>,
    "feedback_text": "<2-3 parágrafos explicando a nota; mencione pontos \
fortes E pontos a melhorar; tom construtivo, voz de professor>",
    "evidencias": [
      {{"trecho": "<citação literal do texto>", "comentario": "<por que \
esse trecho é problema ou acerto>"}}
    ]
  }},
  "c2_audit": {{...mesmo formato...}},
  "c3_audit": {{...mesmo formato...}},
  "c4_audit": {{...mesmo formato...}},
  "c5_audit": {{...mesmo formato...}}
}}

Diretrizes:
- "nota" precisa ser exatamente um dos valores: 0, 40, 80, 120, 160 ou 200
- "feedback_text" tem 2-3 parágrafos (não 1 frase). Português natural, \
sem jargão acadêmico. Aluno deve entender.
- "evidencias" tem 1-3 itens por competência. Use trechos LITERAIS do \
texto (copy/paste de partes da redação).
- NÃO retorne nenhum texto fora do JSON. NÃO use markdown ```json fence.
"""


# ──────────────────────────────────────────────────────────────────────
# Parser — JSON balanceado + validação semântica
# ──────────────────────────────────────────────────────────────────────

ParseStatus = str  # "ok" | "partial" | "failed"

# Regex pra "C1: 160" / "Comp 1: 160" — fallback pra extrair só notas
# se o JSON falhar mas o FT ainda assim emitiu padrão reconhecível.
_REGEX_NOTA_COMP = re.compile(
    r"(?:C(?:omp\w*)?\s*)?([1-5])\s*[:=\-–]\s*(\d{1,3})",
    re.IGNORECASE,
)

CAMPOS_OBRIGATORIOS = ("nota", "feedback_text", "evidencias")
COMPETENCIAS = ("c1_audit", "c2_audit", "c3_audit", "c4_audit", "c5_audit")


def parse_audit_response(
    raw: str,
) -> Tuple[Optional[Dict[str, Any]], ParseStatus, List[str]]:
    """Tenta parsear a resposta do FT como JSON estruturado de audit.

    Returns:
        (audit_dict, parse_status, missing_fields)
        - audit_dict: dict com c1_audit..c5_audit (mesmo se partial),
          ou None se parse_status=failed.
        - parse_status: "ok" | "partial" | "failed"
        - missing_fields: ["c1_audit", "c2_audit.feedback_text", ...]
          listando o que falta ou tá inválido. Vazio se ok.
    """
    if not raw or not raw.strip():
        return None, "failed", ["resposta_vazia"]

    audit = _try_balanced_json(raw)
    if audit is None:
        return None, "failed", ["json_não_parseou"]

    # Validação semântica
    missing: List[str] = []
    for c in COMPETENCIAS:
        if c not in audit:
            missing.append(c)
            continue
        block = audit[c]
        if not isinstance(block, dict):
            missing.append(f"{c}:tipo_inválido")
            continue
        for campo in CAMPOS_OBRIGATORIOS:
            if campo not in block:
                missing.append(f"{c}.{campo}")
                continue
            v = block[campo]
            # Validação de tipo + conteúdo mínimo
            if campo == "nota":
                if not isinstance(v, (int, float)):
                    missing.append(f"{c}.nota:tipo")
                elif int(v) not in (0, 40, 80, 120, 160, 200):
                    missing.append(f"{c}.nota:fora_da_escala_{v}")
            elif campo == "feedback_text":
                if not isinstance(v, str) or not v.strip():
                    missing.append(f"{c}.feedback_text:vazio")
            elif campo == "evidencias":
                if not isinstance(v, list):
                    missing.append(f"{c}.evidencias:tipo")
                # Lista vazia é aceitável (FT pode não achar evidências)

    if not missing:
        return audit, "ok", []
    # Se temos audit dict + ao menos as 5 cN_audit chaves presentes,
    # mesmo que campos internos faltem → "partial"
    if all(c in audit and isinstance(audit[c], dict) for c in COMPETENCIAS):
        return audit, "partial", missing
    return audit, "partial", missing


def _try_balanced_json(raw: str) -> Optional[Dict[str, Any]]:
    """Tenta parsear JSON do texto bruto. Estratégias:
      1. Texto inteiro como JSON.
      2. Maior bloco `{...}` balanceado (cobre nested).
      3. Strip de fences markdown ```json ... ```.
    """
    candidates: List[str] = []

    stripped = raw.strip()
    # Strip markdown fences caso o FT ignore a instrução
    fence_match = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        stripped, re.DOTALL,
    )
    if fence_match:
        candidates.append(fence_match.group(1))

    if stripped.startswith("{"):
        candidates.append(stripped)

    # Maior bloco {...} balanceado
    stack = 0
    start = -1
    for i, ch in enumerate(raw):
        if ch == "{":
            if stack == 0:
                start = i
            stack += 1
        elif ch == "}":
            if stack > 0:
                stack -= 1
                if stack == 0 and start >= 0:
                    candidates.append(raw[start:i + 1])
                    start = -1

    seen: Set[str] = set()
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        try:
            data = json.loads(cand)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict):
            return data
    return None


def extract_notas(
    audit: Optional[Dict[str, Any]],
    raw: str,
) -> Optional[Dict[str, int]]:
    """Extrai notas C1-C5 + total.

    Estratégias na ordem:
      1. audit[cN_audit].nota se audit dict válido.
      2. Regex `C<n>: <nota>` no raw (fallback se parser estrutural
         falhou mas o FT ainda emitiu padrão de notas).

    Retorna None se nenhuma extraiu 5 notas.
    """
    if audit is not None:
        notas: Dict[str, int] = {}
        for n in range(1, 6):
            block = audit.get(f"c{n}_audit") or {}
            v = block.get("nota") if isinstance(block, dict) else None
            if isinstance(v, (int, float)):
                notas[f"c{n}"] = int(v)
        if len(notas) == 5:
            notas["total"] = sum(notas[f"c{n}"] for n in range(1, 6))
            return notas

    # Fallback regex
    matches = _REGEX_NOTA_COMP.findall(raw or "")
    notas_regex: Dict[str, int] = {}
    for comp_num, nota_str in matches:
        try:
            nota = int(nota_str)
        except ValueError:
            continue
        if 0 <= nota <= 200:
            notas_regex[f"c{comp_num}"] = nota
    if len(notas_regex) == 5:
        notas_regex["total"] = sum(notas_regex[f"c{n}"] for n in range(1, 6))
        return notas_regex

    return None


# ──────────────────────────────────────────────────────────────────────
# Chamada FT
# ──────────────────────────────────────────────────────────────────────

def grade_with_audit(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Avalia 1 redação chamando FT com prompt enriquecido."""
    _bootstrap_backend()
    from openai import OpenAI
    from redato_backend.dev_offline import _SYSTEM_PROMPT_BASE

    rid = rec["id"]
    tema = (rec.get("tema") or {}).get("titulo") or "Tema livre"
    content = (rec.get("redacao") or {}).get("texto_original") or ""

    user_msg = USER_MSG_TEMPLATE.format(tema=tema, texto=content)
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    start = time.time()
    try:
        response = client.chat.completions.create(
            model=FT_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT_BASE},
                {"role": "user", "content": user_msg},
            ],
            temperature=0,
            max_tokens=MAX_TOKENS,
        )
    except Exception as exc:  # noqa: BLE001
        return _erro(rec, elapsed=time.time() - start, exc=exc)

    elapsed_ms = int((time.time() - start) * 1000)
    if not response.choices:
        return _erro(
            rec, elapsed=elapsed_ms / 1000,
            exc=RuntimeError("FT retornou sem choices"),
        )

    raw_text = response.choices[0].message.content or ""
    audit, parse_status, missing = parse_audit_response(raw_text)
    notas = extract_notas(audit, raw_text)

    # Custo via usage real
    usage = response.usage
    in_t = usage.prompt_tokens if usage else 0
    out_t = usage.completion_tokens if usage else 0
    custo = (
        (in_t / 1_000_000) * PRECO_INPUT_USD_POR_MTOK
        + (out_t / 1_000_000) * PRECO_OUTPUT_USD_POR_MTOK
    )

    if notas is None:
        return _erro(
            rec, elapsed=elapsed_ms / 1000,
            exc=RuntimeError(
                f"Nem audit nem regex extraíram 5 notas. "
                f"parse_status={parse_status}, missing={missing[:3]}"
            ),
            raw_output=raw_text,
            audit_parsed=audit,
            parse_status=parse_status,
            missing_fields=missing,
            cost=custo, latency=elapsed_ms,
        )

    return _saida(
        rec, notas=notas, raw=raw_text,
        audit_parsed=audit, parse_status=parse_status,
        missing_fields=missing,
        elapsed_ms=elapsed_ms, cost=custo,
    )


# ──────────────────────────────────────────────────────────────────────
# Schema de saída
# ──────────────────────────────────────────────────────────────────────

def _gabarito(rec: Dict[str, Any]) -> Dict[str, Optional[int]]:
    gab = rec.get("notas_competencia") or {}
    return {
        "total": rec.get("nota_global"),
        "c1": gab.get("c1"), "c2": gab.get("c2"),
        "c3": gab.get("c3"), "c4": gab.get("c4"),
        "c5": gab.get("c5"),
    }


def _saida(
    rec: Dict[str, Any], *,
    notas: Dict[str, int], raw: str,
    audit_parsed: Optional[Dict[str, Any]],
    parse_status: ParseStatus,
    missing_fields: List[str],
    elapsed_ms: int, cost: float,
) -> Dict[str, Any]:
    tema = (rec.get("tema") or {}).get("titulo") or "Tema livre"
    return {
        "id": rec["id"],
        "fonte": rec.get("fonte"),
        "tema": tema,
        "gabarito": _gabarito(rec),
        "modelo": MODELO_LABEL,
        "notas_geradas": notas,
        "audit_completo": raw,
        "audit_parsed": audit_parsed,
        "parse_status": parse_status,
        "missing_fields": missing_fields,
        "latency_ms": elapsed_ms,
        "cost_usd": round(cost, 6),
        "error": None,
    }


def _erro(
    rec: Dict[str, Any], *,
    elapsed: float, exc: Exception,
    raw_output: Optional[str] = None,
    audit_parsed: Optional[Dict[str, Any]] = None,
    parse_status: ParseStatus = "failed",
    missing_fields: Optional[List[str]] = None,
    cost: float = 0.0, latency: int = 0,
) -> Dict[str, Any]:
    tema = (rec.get("tema") or {}).get("titulo") or "Tema livre"
    return {
        "id": rec["id"],
        "fonte": rec.get("fonte"),
        "tema": tema,
        "gabarito": _gabarito(rec),
        "modelo": MODELO_LABEL,
        "notas_geradas": {
            "c1": 0, "c2": 0, "c3": 0,
            "c4": 0, "c5": 0, "total": 0,
        },
        "audit_completo": raw_output,
        "audit_parsed": audit_parsed,
        "parse_status": parse_status,
        "missing_fields": missing_fields or [],
        "latency_ms": latency or int(elapsed * 1000),
        "cost_usd": round(cost, 6) if cost else 0.0,
        "error": f"{type(exc).__name__}: {exc}"[:300],
    }


# ──────────────────────────────────────────────────────────────────────
# Loop de execução com idempotência + paralelismo
# ──────────────────────────────────────────────────────────────────────

def _carregar_gold() -> List[Dict[str, Any]]:
    if not EVAL_PATH.exists():
        raise SystemExit(
            f"[erro] eval_gold_v1.jsonl não encontrado em:\n  {EVAL_PATH}"
        )
    out: List[Dict[str, Any]] = []
    with EVAL_PATH.open(encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            out.append(json.loads(ln))
    if not out:
        raise SystemExit("[erro] eval_gold_v1.jsonl vazio")
    return out


def _ids_processados(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    ids: Set[str] = set()
    with path.open(encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
                if r.get("id"):
                    ids.add(r["id"])
            except json.JSONDecodeError:
                continue
    return ids


def _append(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _rodar(
    records: List[Dict[str, Any]], out_path: Path, *, label: str,
) -> Dict[str, Any]:
    print(f"\n[{label}] iniciando — {len(records)} redações")
    print(f"  saída: {out_path.relative_to(REPO)}")

    ja = _ids_processados(out_path)
    pendentes = [r for r in records if r["id"] not in ja]
    if ja:
        print(f"  idempotência: {len(ja)} já feitos, {len(pendentes)} pendentes")
    if not pendentes:
        print("  nada a fazer.")
        return {"ok": len(ja), "erro": 0, "custo": 0.0, "tempo": 0.0}

    inicio = time.time()
    n_ok = n_erro = 0
    custo_total = 0.0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(grade_with_audit, r): r for r in pendentes}
        n_proc = 0
        for fut in as_completed(futs):
            n_proc += 1
            try:
                resultado = fut.result()
            except Exception as exc:  # noqa: BLE001
                resultado = _erro(
                    futs[fut], elapsed=0, exc=exc,
                )
            _append(out_path, resultado)
            if resultado.get("error"):
                n_erro += 1
            else:
                n_ok += 1
            custo_total += float(resultado.get("cost_usd") or 0)

            if n_proc % 10 == 0 or n_proc == len(pendentes):
                pct = 100 * n_proc / len(pendentes)
                tempo = time.time() - inicio
                print(
                    f"  [{n_proc:3d}/{len(pendentes)}] {pct:5.1f}%  "
                    f"ok={n_ok} erro={n_erro}  "
                    f"custo=${custo_total:.3f}  t={tempo:.0f}s"
                )

    tempo_total = time.time() - inicio
    print(
        f"[{label}] FIM em {tempo_total:.0f}s — ok={n_ok}, erro={n_erro}, "
        f"custo=${custo_total:.3f}"
    )
    return {
        "ok": n_ok + len(ja), "erro": n_erro,
        "custo": custo_total, "tempo": tempo_total,
    }


# ──────────────────────────────────────────────────────────────────────
# Análise + relatório
# ──────────────────────────────────────────────────────────────────────

def _faixa(total: Optional[int]) -> str:
    if total is None:
        return "?"
    if total <= 400:
        return "≤400"
    if total <= 599:
        return "401-599"
    if total <= 799:
        return "600-799"
    if total <= 999:
        return "800-999"
    return "1000"


def _calc_metricas(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    n_ok = n_erro_pipe = 0
    n_40 = n_60 = n_80 = 0
    mae_vals: List[float] = []
    me_vals: List[float] = []
    lat_vals: List[float] = []
    custo_total = 0.0
    parse_counts = {"ok": 0, "partial": 0, "failed": 0}
    for r in records:
        if r.get("error"):
            n_erro_pipe += 1
            ps = r.get("parse_status") or "failed"
            if ps in parse_counts:
                parse_counts[ps] += 1
            else:
                parse_counts["failed"] += 1
            continue
        ps = r.get("parse_status") or "failed"
        if ps in parse_counts:
            parse_counts[ps] += 1
        gold = (r.get("gabarito") or {}).get("total")
        pred = (r.get("notas_geradas") or {}).get("total", 0)
        if gold is None:
            continue
        n_ok += 1
        diff = pred - gold
        ad = abs(diff)
        if ad <= 40: n_40 += 1
        if ad <= 60: n_60 += 1
        if ad <= 80: n_80 += 1
        mae_vals.append(ad)
        me_vals.append(diff)
        lat_vals.append(r.get("latency_ms") or 0)
        custo_total += float(r.get("cost_usd") or 0)
    pct = lambda n: (100 * n / n_ok) if n_ok else 0.0
    n_total_parse = sum(parse_counts.values())
    parse_pct = (
        {k: (100 * v / n_total_parse) if n_total_parse else 0.0
         for k, v in parse_counts.items()}
    )
    return {
        "n_total": len(records),
        "n_ok": n_ok,
        "n_erro_pipeline": n_erro_pipe,
        "pct_40": pct(n_40),
        "pct_60": pct(n_60),
        "pct_80": pct(n_80),
        "mae": mean(mae_vals) if mae_vals else 0.0,
        "me": mean(me_vals) if me_vals else 0.0,
        "latency_med_seg": (mean(lat_vals) / 1000) if lat_vals else 0.0,
        "custo_total": custo_total,
        "custo_por_redacao": (custo_total / n_ok) if n_ok else 0.0,
        "parse_counts": parse_counts,
        "parse_pct": parse_pct,
    }


def _amostras_qualitativas(
    records: List[Dict[str, Any]], k_alta: int = 3, k_baixa: int = 2,
) -> List[Dict[str, Any]]:
    """Pega k_alta exemplos de redação 1000 e k_baixa de ≤400 com
    parse_status=ok pra leitura humana. Se não tiver `ok` suficientes,
    completa com `partial`."""
    altas = []
    baixas = []
    for r in records:
        if r.get("error"):
            continue
        gold = (r.get("gabarito") or {}).get("total")
        if gold is None:
            continue
        ps = r.get("parse_status")
        if gold == 1000 and ps in ("ok", "partial"):
            altas.append((r, ps == "ok"))
        elif gold <= 400 and ps in ("ok", "partial"):
            baixas.append((r, ps == "ok"))
    # Prioriza ok; depois partial
    altas.sort(key=lambda x: -int(x[1]))
    baixas.sort(key=lambda x: -int(x[1]))
    return [r for r, _ in altas[:k_alta]] + [r for r, _ in baixas[:k_baixa]]


def _gerar_relatorio(
    timestamp: str, records: List[Dict[str, Any]],
) -> str:
    m = _calc_metricas(records)
    amostras = _amostras_qualitativas(records)

    # Decisão sugerida (cenários A/B/C do briefing)
    pct_40 = m["pct_40"]
    parse_ok_pct = m["parse_pct"]["ok"]
    if pct_40 >= 18.0 and parse_ok_pct >= 90.0:
        cenario = "A"
        decisao = (
            "**Cenário A — MIGRAR PRO FT COM PROMPT NOVO (sem re-treino).** "
            "Notas ≥18% ±40 mantém a vantagem do baseline e parse ≥90% mostra "
            "que o FT consegue gerar JSON estruturado confiável."
        )
    elif pct_40 < 18.0 and parse_ok_pct >= 50.0:
        cenario = "B"
        decisao = (
            "**Cenário B — RE-TREINO faz sentido pra recuperar precisão.** "
            "Notas caíram <18% ±40 (vencedor A/B perdeu vantagem com prompt novo), "
            "mas parser conseguiu estruturar audit em ≥50% — re-treino com dataset "
            "ampliado (audit + notas) deve recuperar precisão sem perder estrutura."
        )
    else:
        cenario = "C"
        decisao = (
            "**Cenário C — RE-TREINO necessário (FT não tem capacity sem treino).** "
            "Parser conseguiu <50% ou notas regrediram severamente. Prompt enriquecido "
            "não é suficiente — modelo precisa de exemplos de audit no treino."
        )

    lines: List[str] = []
    lines.append(f"# REPORT FT-with-audit — {timestamp}")
    lines.append("")
    lines.append(
        f"Experimento isolado: GPT-FT BTBOS5VF com prompt enriquecido pedindo "
        f"audit estruturado (subset OF14: nota + feedback_text + evidencias). "
        f"Roda nas mesmas 200 redações do A/B 30/abr."
    )
    lines.append("")
    lines.append("## TL;DR")
    lines.append("")
    lines.append(f"- **Notas:** ±40 = **{pct_40:.1f}%** (baseline FT só notas: {BASELINE_FT_PCT_40}%)")
    lines.append(f"- **Audit estrutural:** **{parse_ok_pct:.1f}%** parse_status=ok")
    lines.append(f"- **Custo total:** **${m['custo_total']:.2f}**")
    lines.append(f"- **Latência média:** **{m['latency_med_seg']:.1f}s**")
    lines.append(f"- **Cenário:** {cenario}")
    lines.append("")
    lines.append(decisao)
    lines.append("")

    # ── Tabela 1 ───────────────────────────────────────────────────
    lines.append("## Tabela 1 — Comparativo notas FT só vs FT com audit")
    lines.append("")
    lines.append("Baseline (FT só notas) vem do A/B 30/abr — `REPORT_AB_20260430_105858.md`.")
    lines.append("")
    lines.append("| Métrica | FT só notas (baseline) | FT com audit-prompt | Δ |")
    lines.append("|---|---|---|---|")
    delta_40 = pct_40 - BASELINE_FT_PCT_40
    lines.append(
        f"| ±40% | {BASELINE_FT_PCT_40}% | {pct_40:.1f}% | {delta_40:+.1f}pp |"
    )
    lines.append(f"| ±60% | — | {m['pct_60']:.1f}% | — |")
    lines.append(f"| ±80% | — | {m['pct_80']:.1f}% | — |")
    lines.append(f"| MAE | — | {m['mae']:.0f} | — |")
    lines.append(f"| ME | — | {m['me']:+.0f} | — |")
    delta_custo = m["custo_por_redacao"] - BASELINE_FT_CUSTO_RED
    lines.append(
        f"| Custo/redação | ${BASELINE_FT_CUSTO_RED:.4f} | "
        f"${m['custo_por_redacao']:.4f} | ${delta_custo:+.4f} |"
    )
    delta_lat = m["latency_med_seg"] - BASELINE_FT_LATENCIA_S
    lines.append(
        f"| Latência média | {BASELINE_FT_LATENCIA_S}s | "
        f"{m['latency_med_seg']:.1f}s | {delta_lat:+.1f}s |"
    )
    lines.append("")

    # ── Tabela 2 ───────────────────────────────────────────────────
    lines.append("## Tabela 2 — Qualidade do parsing")
    lines.append("")
    lines.append("Distribuição de `parse_status` em 200 redações.")
    lines.append("")
    lines.append("| parse_status | count | % | Significado |")
    lines.append("|---|---|---|---|")
    lines.append(
        f"| ok | {m['parse_counts']['ok']} | {m['parse_pct']['ok']:.1f}% | "
        f"JSON válido + 5 cN_audit completos com nota+feedback+evidencias |"
    )
    lines.append(
        f"| partial | {m['parse_counts']['partial']} | {m['parse_pct']['partial']:.1f}% | "
        f"JSON válido mas faltam campos ou tipos errados |"
    )
    lines.append(
        f"| failed | {m['parse_counts']['failed']} | {m['parse_pct']['failed']:.1f}% | "
        f"JSON não parseou — só notas extraídas via regex (ou erro total) |"
    )
    lines.append("")

    # ── Tabela 3: amostras qualitativas ────────────────────────────
    lines.append("## Tabela 3 — 5 amostras de audit pra leitura humana")
    lines.append("")
    lines.append(
        "Daniel lê e julga subjetivamente: o audit é útil pro aluno? "
        "O feedback_text faz sentido? As evidências são citações reais?"
    )
    lines.append("")
    if not amostras:
        lines.append(
            "_Nenhuma amostra com parse_status='ok' ou 'partial' encontrada._ "
            "Provavelmente cenário C — FT não consegue audit estruturado sem treino."
        )
        lines.append("")
    else:
        for idx, r in enumerate(amostras, 1):
            gold = (r.get("gabarito") or {}).get("total")
            pred = (r.get("notas_geradas") or {}).get("total")
            ps = r.get("parse_status")
            audit = r.get("audit_parsed") or {}
            lines.append(f"### Amostra {idx} — `{r['id']}`")
            lines.append("")
            lines.append(
                f"**Faixa:** {_faixa(gold)} · **Gabarito total:** {gold} · "
                f"**Predito:** {pred} · **parse_status:** `{ps}`"
            )
            lines.append("")
            for c in COMPETENCIAS:
                bloco = audit.get(c) if isinstance(audit, dict) else None
                if not isinstance(bloco, dict):
                    lines.append(f"- **{c.upper()}**: _ausente no parse_")
                    continue
                nota = bloco.get("nota", "?")
                fb = (bloco.get("feedback_text") or "").strip()
                evs = bloco.get("evidencias") or []
                lines.append(f"#### {c.upper()} — nota {nota}")
                lines.append("")
                if fb:
                    # Quebra em parágrafos preservando legibilidade
                    lines.append(f"> {fb}")
                else:
                    lines.append("> _feedback_text vazio_")
                lines.append("")
                if evs:
                    lines.append("**Evidências:**")
                    for ev in evs[:3]:  # limita a 3 pra não inchar
                        if not isinstance(ev, dict):
                            continue
                        trecho = (ev.get("trecho") or "")[:200]
                        coment = (ev.get("comentario") or "")[:300]
                        lines.append(f"- _\"{trecho}\"_ — {coment}")
                    lines.append("")
            lines.append("---")
            lines.append("")

    # ── Decisão sugerida + critérios ───────────────────────────────
    lines.append("## Decisão sugerida")
    lines.append("")
    lines.append("Critérios (do briefing 30/abr):")
    lines.append("")
    lines.append("- **Cenário A** (MIGRAR sem re-treino): ±40 ≥ 18% E parse_ok ≥ 90% E amostras úteis")
    lines.append("- **Cenário B** (RE-TREINO faz sentido): ±40 < 18% MAS parse_ok ≥ 50%")
    lines.append("- **Cenário C** (RE-TREINO necessário): parse_ok < 50% OU audit superficial")
    lines.append("")
    lines.append(f"**Resultado mecânico: Cenário {cenario}**")
    lines.append("")
    lines.append(decisao)
    lines.append("")
    lines.append(
        "_Atenção: critérios A/B/C são heurísticos. A leitura qualitativa das "
        "5 amostras (Tabela 3) tem peso igual ou maior — se o feedback_text "
        "for genérico ou as evidências forem inventadas, mesmo parse_ok=100% "
        "vira Cenário C._"
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"_Gerado por `scripts/ab_models/run_ft_with_audit.py` — timestamp `{timestamp}`._")
    lines.append("")
    return "\n".join(lines)


def gerar_relatorio_de_ts(timestamp: str) -> Path:
    """Lê o jsonl do timestamp e escreve REPORT_FT_AUDIT_<TS>.md."""
    in_path = RESULTS_DIR / f"eval_ft_with_audit_{timestamp}.jsonl"
    if not in_path.exists():
        raise SystemExit(f"[erro] não encontrado: {in_path}")
    records: List[Dict[str, Any]] = []
    with in_path.open(encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                records.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    md = _gerar_relatorio(timestamp, records)
    out_path = RESULTS_DIR / f"REPORT_FT_AUDIT_{timestamp}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    return out_path


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────

def _validar_env() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit(
            "[erro] OPENAI_API_KEY não setada — necessária pra chamar o FT."
        )
    try:
        import openai  # noqa: F401
    except ImportError:
        raise SystemExit(
            "[erro] openai SDK não instalado. `pip install openai>=1.50`."
        )


def _confirmar(custo_estim: float, tempo_min: int) -> None:
    print()
    print("=" * 60)
    print("ESTIMATIVA")
    print("=" * 60)
    print(f"  200 redações × ~${BASELINE_FT_CUSTO_RED:.4f}/redação ≈ ${custo_estim:.2f}")
    print(f"  Tempo estimado: ~{tempo_min} min (FT é rápido, ~3-5s por chamada)")
    print(f"  Saída: scripts/ab_models/results/eval_ft_with_audit_<TS>.jsonl")
    print(f"  Modelo: {FT_MODEL}")
    print("=" * 60)
    resp = input("Continuar? [y/N] ").strip().lower()
    if resp != "y":
        raise SystemExit("[abortado] usuário não confirmou")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Experimento: FT com prompt audit-enriched"
    )
    parser.add_argument("--skip-smoke", action="store_true",
                        help="Pula smoke de 5 redações")
    parser.add_argument("--resume", type=str, default=None,
                        help="Timestamp existente pra retomar (ex: 20260430_153022)")
    parser.add_argument("--report-only", type=str, default=None,
                        help="Pula execução; só gera relatório do timestamp informado")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Pula prompt de confirmação")
    args = parser.parse_args()

    if args.report_only:
        out = gerar_relatorio_de_ts(args.report_only)
        print(f"[report] ✓ {out.relative_to(REPO)}")
        return 0

    _validar_env()
    timestamp = args.resume or datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"eval_ft_with_audit_{timestamp}.jsonl"

    print(f"[setup] timestamp = {timestamp}")
    if args.resume:
        print(f"[setup] modo --resume — reusando arquivo existente")
    print(f"[setup] carregando {EVAL_PATH.name}...")
    records = _carregar_gold()
    print(f"        ✓ {len(records)} redações carregadas")

    # ~$5 total (200 × $0.025) — confere com briefing
    custo_estim = len(records) * BASELINE_FT_CUSTO_RED
    if not args.yes:
        _confirmar(custo_estim, tempo_min=5)

    # Smoke 5 antes do full
    if not args.skip_smoke:
        print()
        print("=" * 60)
        print(f"SMOKE TEST — {SMOKE_N} redações")
        print("=" * 60)
        smoke_path = RESULTS_DIR / f"smoke_ft_with_audit_{timestamp}.jsonl"
        smoke_stats = _rodar(
            records[:SMOKE_N], smoke_path, label="smoke FT-audit",
        )
        if smoke_stats["erro"] >= SMOKE_N:
            raise SystemExit(
                f"[erro] smoke: {smoke_stats['erro']}/{SMOKE_N} falharam. "
                "Investigar antes do full."
            )
        # Smoke: também checa parse_status pra alertar cedo
        smoke_records = []
        with smoke_path.open(encoding="utf-8") as f:
            for ln in f:
                if ln.strip():
                    smoke_records.append(json.loads(ln))
        ps_ok = sum(1 for r in smoke_records if r.get("parse_status") == "ok")
        ps_failed = sum(1 for r in smoke_records if r.get("parse_status") == "failed")
        print(
            f"  [smoke parse] ok={ps_ok}/{SMOKE_N}  failed={ps_failed}/{SMOKE_N}"
        )
        if ps_failed == SMOKE_N:
            print(
                "  ⚠ AVISO: 100% do smoke retornou parse_status=failed. "
                "FT pode estar ignorando completamente o pedido de JSON. "
                "Considere abortar e revisar o prompt."
            )
        print()
        print("=" * 60)
        print("SMOKE OK. Iniciando run completo (200 redações).")
        print("=" * 60)

    # Run completo
    stats = _rodar(records, out_path, label="full FT-audit")

    # Relatório final
    print()
    print("=" * 60)
    print("GERANDO RELATÓRIO")
    print("=" * 60)
    out_md = gerar_relatorio_de_ts(timestamp)
    print(f"  ✓ {out_md.relative_to(REPO)}")
    print()
    print(f"Resumo: ok={stats['ok']}/{len(records)}  erro={stats['erro']}  "
          f"custo=${stats['custo']:.2f}  tempo={stats['tempo']:.0f}s")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
