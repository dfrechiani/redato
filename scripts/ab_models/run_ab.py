"""Orquestrador A/B 3-vias — Claude prod vs tuned vs GPT-FT.

Roda os 3 adaptadores no eval_gold_v1.jsonl (200 redações AES-ENEM
com gabarito INEP) e escreve 3 jsonl em `scripts/ab_models/results/`.

Fluxo:
  1. Valida env vars (ANTHROPIC_API_KEY + OPENAI_API_KEY) e existência
     do eval_gold_v1.jsonl.
  2. Carrega 200 records.
  3. Mostra cost estimate + tempo estimado e pede confirmação `y`.
  4. Smoke test: 5 redações × 3 modelos pra detectar bugs cedo (~$1).
  5. Roda os 3 modelos em sequência. Dentro de cada modelo, paralelismo
     ThreadPoolExecutor max_workers=5.
  6. Saída idempotente: cada call lê arquivo existente e pula IDs já
     processados (permite retomar interrupções sem refazer).

Uso:
    cd /Users/danielfrechiani/Desktop/redato_hash
    python scripts/ab_models/run_ab.py
    python scripts/ab_models/run_ab.py --skip-smoke   # pular smoke
    python scripts/ab_models/run_ab.py --only prod    # rodar só 1 modelo
    python scripts/ab_models/run_ab.py --resume <ts>  # retoma com timestamp

`results/` está no .gitignore — só os scripts entram em commit.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set


REPO = Path(__file__).resolve().parents[2]
EVAL_PATH = (
    REPO / "backend" / "notamil-backend"
    / "scripts" / "validation" / "data" / "eval_gold_v1.jsonl"
)
RESULTS_DIR = Path(__file__).resolve().parent / "results"
SMOKE_N = 5
MAX_WORKERS = 5


# ──────────────────────────────────────────────────────────────────────
# Setup de env vars (compartilhado por prod + tuned)
# ──────────────────────────────────────────────────────────────────────

def _setup_redato_env() -> None:
    """Configura env vars que `_claude_grade_essay` precisa pra
    rodar fora do servidor: dev-offline ON, persist OFF, ensemble ON
    (default prod), self-critique OFF (default prod)."""
    os.environ.setdefault("REDATO_DEV_OFFLINE", "1")
    os.environ.setdefault("REDATO_DEV_PERSIST", "0")
    os.environ.setdefault("REDATO_ENSEMBLE", "1")
    os.environ.setdefault("REDATO_SELF_CRITIQUE", "0")


# ──────────────────────────────────────────────────────────────────────
# IO — leitura do gold + saída idempotente
# ──────────────────────────────────────────────────────────────────────

def _carregar_gold() -> List[Dict[str, Any]]:
    """Lê eval_gold_v1.jsonl, valida schema mínimo, retorna lista."""
    if not EVAL_PATH.exists():
        raise SystemExit(
            f"[erro] eval_gold_v1.jsonl não encontrado em:\n  {EVAL_PATH}\n"
            f"Necessário pra rodar A/B."
        )
    out: List[Dict[str, Any]] = []
    with EVAL_PATH.open(encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            r = json.loads(ln)
            # Validação mínima — campos críticos
            for required in ("id", "redacao", "notas_competencia", "nota_global"):
                if required not in r:
                    raise SystemExit(
                        f"[erro] schema inválido em {r.get('id', '???')}: "
                        f"falta `{required}`"
                    )
            if "texto_original" not in (r.get("redacao") or {}):
                raise SystemExit(
                    f"[erro] schema inválido em {r['id']}: "
                    f"`redacao.texto_original` faltando"
                )
            out.append(r)
    if not out:
        raise SystemExit("[erro] eval_gold_v1.jsonl vazio")
    return out


def _ids_ja_processados(path: Path) -> Set[str]:
    """Lê arquivo de saída (se existir) e retorna set de IDs já
    processados — usado pra idempotência."""
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
                # Linha corrompida — ignora, será reprocessado
                continue
    return ids


def _append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    """Append atômico (1 linha por call). Cria parent dir se preciso."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ──────────────────────────────────────────────────────────────────────
# Runner — executa N redações em paralelo (max_workers=5) num modelo
# ──────────────────────────────────────────────────────────────────────

def _rodar_modelo(
    nome: str,
    grader: Callable[[Dict[str, Any]], Dict[str, Any]],
    records: List[Dict[str, Any]],
    out_path: Path,
    *, label: str = "",
) -> Dict[str, Any]:
    """Roda `grader(rec)` em paralelo (ThreadPoolExecutor) sobre
    `records`, escrevendo cada resultado em `out_path` (append-only).

    Retorna stats agregadas pra log final.
    """
    print(f"\n[{label or nome}] iniciando — {len(records)} redações")
    print(f"  saída: {out_path.relative_to(REPO)}")

    ja_feitos = _ids_ja_processados(out_path)
    pendentes = [r for r in records if r["id"] not in ja_feitos]
    if ja_feitos:
        print(
            f"  idempotência: {len(ja_feitos)} já processadas, "
            f"{len(pendentes)} pendentes"
        )
    if not pendentes:
        print(f"  nada a fazer — todos os IDs já processados.")
        return {
            "modelo": nome, "total": len(records),
            "ok": len(ja_feitos), "erro": 0,
            "custo": 0.0, "tempo_seg": 0.0,
        }

    inicio = time.time()
    n_ok = 0
    n_erro = 0
    custo_total = 0.0
    n_processados = 0

    # Lock implícito no append (escrita serial — cada thread chama
    # _append_jsonl de forma independente; mesmo flush=line-buffered
    # do append "a" é seguro pra append em jsonl sob pressão moderada).
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(grader, rec): rec for rec in pendentes}
        for fut in as_completed(futs):
            rec_in = futs[fut]
            n_processados += 1
            try:
                resultado = fut.result()
            except Exception as exc:  # noqa: BLE001
                # Defensivo — grader já retorna _erro normalmente,
                # mas se algo escapar do try interno, captura aqui.
                resultado = {
                    "id": rec_in["id"],
                    "fonte": rec_in.get("fonte"),
                    "modelo": nome,
                    "notas_geradas": {
                        "c1": 0, "c2": 0, "c3": 0,
                        "c4": 0, "c5": 0, "total": 0,
                    },
                    "raw_output": None,
                    "latency_ms": 0,
                    "cost_usd": 0.0,
                    "error": f"{type(exc).__name__}: {exc}"[:300],
                }

            _append_jsonl(out_path, resultado)
            if resultado.get("error"):
                n_erro += 1
            else:
                n_ok += 1
            custo_total += float(resultado.get("cost_usd") or 0.0)

            # Progresso a cada 10
            if n_processados % 10 == 0 or n_processados == len(pendentes):
                pct = 100 * n_processados / len(pendentes)
                tempo = time.time() - inicio
                print(
                    f"  [{n_processados:3d}/{len(pendentes)}] "
                    f"{pct:5.1f}%  "
                    f"ok={n_ok} erro={n_erro}  "
                    f"custo=${custo_total:.3f}  "
                    f"t={tempo:.0f}s"
                )

    tempo_total = time.time() - inicio
    print(
        f"[{label or nome}] FIM em {tempo_total:.0f}s — "
        f"ok={n_ok}, erro={n_erro}, custo=${custo_total:.3f}"
    )
    return {
        "modelo": nome,
        "total": len(records),
        "ok": n_ok + len(ja_feitos),
        "erro": n_erro,
        "custo": custo_total,
        "tempo_seg": tempo_total,
    }


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────

def _validar_env(modelos: Iterable[str]) -> None:
    """Confere env vars exigidas. Falha cedo se faltar alguma."""
    if any(m in modelos for m in ("prod", "tuned")):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit(
                "[erro] ANTHROPIC_API_KEY não setada — necessária pra "
                "rodar prod e/ou tuned."
            )
    if "ft" in modelos:
        if not os.environ.get("OPENAI_API_KEY"):
            raise SystemExit(
                "[erro] OPENAI_API_KEY não setada — necessária pra rodar ft."
            )


def _pedir_confirmacao(custo_estim: float, tempo_min: int) -> None:
    """Mostra cost estimate + tempo e bloqueia até `y`."""
    print()
    print("=" * 60)
    print("ESTIMATIVA DE EXECUÇÃO")
    print("=" * 60)
    print(f"  Custo aproximado:  ~${custo_estim:.2f} USD")
    print(f"  Tempo aproximado:  ~{tempo_min} min")
    print(f"  Saída:             scripts/ab_models/results/")
    print(f"  Eval set:          {EVAL_PATH.name} (200 redações)")
    print("=" * 60)
    resp = input("Continuar? [y/N] ").strip().lower()
    if resp != "y":
        raise SystemExit("[abortado] usuário não confirmou")


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _resolver_paths(timestamp: str) -> Dict[str, Path]:
    return {
        "prod":  RESULTS_DIR / f"eval_prod_{timestamp}.jsonl",
        "tuned": RESULTS_DIR / f"eval_tuned_{timestamp}.jsonl",
        "ft":    RESULTS_DIR / f"eval_ft_{timestamp}.jsonl",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="A/B 3-vias: Claude prod vs Claude tuned vs GPT-FT"
    )
    parser.add_argument(
        "--only",
        choices=["prod", "tuned", "ft"],
        help="Rodar apenas 1 modelo (default: rodar os 3)",
    )
    parser.add_argument(
        "--skip-smoke",
        action="store_true",
        help="Pula smoke test de 5 redações (não recomendado em primeira run)",
    )
    parser.add_argument(
        "--resume",
        type=str,
        help="Timestamp existente pra retomar (ex: 20260429_143022). "
        "Reusa arquivos de saída e pula IDs já processados.",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Pula prompt de confirmação (uso CI/scripts).",
    )
    args = parser.parse_args()

    # Setup env
    _setup_redato_env()
    modelos = [args.only] if args.only else ["prod", "tuned", "ft"]
    _validar_env(modelos)

    # Imports lazy (depois de _setup_redato_env)
    sys.path.insert(0, str(Path(__file__).parent))
    from grade_claude import grade_prod, grade_tuned  # type: ignore
    from grade_ft import grade_ft  # type: ignore

    GRADERS: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
        "prod":  grade_prod,
        "tuned": grade_tuned,
        "ft":    grade_ft,
    }
    LABELS = {
        "prod":  "Claude prod (Sonnet 4.6 + v2)",
        "tuned": "Claude tuned (Opus 4.7 + fewshot INEP)",
        "ft":    "GPT-FT BTBOS5VF",
    }

    # Carrega gold + define timestamp/paths
    print(f"[setup] carregando {EVAL_PATH.name}...")
    records = _carregar_gold()
    print(f"        ✓ {len(records)} redações carregadas")

    timestamp = args.resume or _timestamp()
    paths = _resolver_paths(timestamp)
    if args.resume:
        print(f"[setup] modo --resume — reusando timestamp {timestamp}")

    # Estimativa de custo (200 redações × 3 modelos):
    #   prod  Sonnet 4.6:    ~200 × $0.012 ≈ $2.40
    #   tuned Opus 4.7:      ~200 × $0.075 ≈ $15.00
    #   ft    gpt-4.1-FT:    ~200 × $0.008 ≈ $1.60
    #   total                              ≈ $19.00
    custos_por_modelo = {"prod": 2.40, "tuned": 15.00, "ft": 1.60}
    custo_total = sum(custos_por_modelo[m] for m in modelos)
    tempos_por_modelo = {"prod": 12, "tuned": 18, "ft": 8}  # minutos
    tempo_total = sum(tempos_por_modelo[m] for m in modelos)
    if not args.yes:
        _pedir_confirmacao(custo_total, tempo_total)

    # ── Smoke test ───────────────────────────────────────────────
    if not args.skip_smoke:
        print()
        print("=" * 60)
        print(f"SMOKE TEST — {SMOKE_N} redações × {len(modelos)} modelos")
        print("=" * 60)
        smoke_records = records[:SMOKE_N]
        for m in modelos:
            smoke_path = (
                RESULTS_DIR / f"smoke_{m}_{timestamp}.jsonl"
            )
            stats = _rodar_modelo(
                nome=m, grader=GRADERS[m], records=smoke_records,
                out_path=smoke_path,
                label=f"smoke {LABELS[m]}",
            )
            if stats["erro"] >= SMOKE_N:
                # Todos falharam → bug grosso, abortar antes do full
                raise SystemExit(
                    f"[erro] smoke {m}: {stats['erro']}/{SMOKE_N} "
                    f"falharam. Investigar antes do full."
                )
        print()
        print("=" * 60)
        print("SMOKE OK. Iniciando run completo (200 redações × modelos).")
        print("=" * 60)

    # ── Run completo ─────────────────────────────────────────────
    todas_stats: List[Dict[str, Any]] = []
    for m in modelos:
        stats = _rodar_modelo(
            nome=m, grader=GRADERS[m], records=records,
            out_path=paths[m],
            label=LABELS[m],
        )
        todas_stats.append(stats)

    # ── Resumo final ─────────────────────────────────────────────
    print()
    print("=" * 60)
    print("RESUMO FINAL")
    print("=" * 60)
    custo_real = 0.0
    tempo_real = 0.0
    for s in todas_stats:
        print(
            f"  {s['modelo']:6s}  "
            f"ok={s['ok']:3d}/{s['total']:3d}  "
            f"erro={s['erro']:3d}  "
            f"custo=${s['custo']:.3f}  "
            f"tempo={s['tempo_seg']:.0f}s"
        )
        custo_real += s["custo"]
        tempo_real += s["tempo_seg"]
    print(f"  TOTAL: custo=${custo_real:.3f} · tempo={tempo_real:.0f}s")
    print()
    print(f"Próximo passo:")
    print(f"  python scripts/ab_models/analyze.py --timestamp {timestamp}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
