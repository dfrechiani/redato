#!/usr/bin/env python3
"""Re-deriva notas dos 80 resultados Opus + flat usando os audits raw
existentes + caps novos em dev_offline.py. Sem chamadas API.

Output: novo JSONL com schema idêntico mas redato_final atualizado.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("REDATO_DEV_OFFLINE", "1")
os.environ.setdefault("REDATO_DEV_PERSIST", "0")

from redato_backend.dev_offline import (  # noqa: E402
    _derive_c1_nota,
    _derive_c2_nota,
    _derive_c3_nota,
    _derive_c4_nota,
    _derive_c5_nota,
)


def re_derive(audit: dict) -> dict | None:
    """Roda derivação Python em cada cN_audit, retorna {c1..c5,total}.
    None se audit vazio (sem cN_audit)."""
    if not isinstance(audit, dict) or len(audit) == 0:
        return None
    derivers = {"c1": _derive_c1_nota, "c2": _derive_c2_nota,
                "c3": _derive_c3_nota, "c4": _derive_c4_nota,
                "c5": _derive_c5_nota}
    out = {}
    has_any = False
    for k, fn in derivers.items():
        ca = audit.get(f"{k}_audit") or {}
        if not isinstance(ca, dict) or not ca:
            out[k] = 0
            continue
        try:
            out[k] = int(fn(ca))
            has_any = True
        except Exception:
            out[k] = 0
    if not has_any:
        return None
    out["total"] = sum(out[k] for k in ("c1", "c2", "c3", "c4", "c5"))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    n_total = n_changed = n_unchanged = n_empty = 0
    diffs = []

    with args.input.open(encoding="utf-8") as fin, args.output.open("w", encoding="utf-8") as fout:
        for line in fin:
            if not line.strip():
                continue
            r = json.loads(line)
            n_total += 1
            audit = r.get("redato_audit") or {}
            old_final = r.get("redato_final") or {}
            new_final = re_derive(audit)
            if new_final is None:
                n_empty += 1
                fout.write(json.dumps(r, ensure_ascii=False) + "\n")
                continue
            if new_final == old_final:
                n_unchanged += 1
            else:
                n_changed += 1
                diffs.append({
                    "id": r.get("id"),
                    "old": old_final,
                    "new": new_final,
                    "delta_total": new_final["total"] - old_final.get("total", 0),
                })
            r["redato_final"] = new_final
            r["redato_derivacao_pre_caps"] = old_final  # preserva pra auditoria
            fout.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Re-derivação aplicada em {args.input}")
    print(f"  Total: {n_total}")
    print(f"  Mudaram: {n_changed}")
    print(f"  Iguais: {n_unchanged}")
    print(f"  Audit vazio (não re-derivado): {n_empty}")
    print(f"  Output: {args.output}")
    print()
    if diffs:
        print(f"Mudanças (top 20 por |delta|):")
        diffs.sort(key=lambda d: -abs(d["delta_total"]))
        for d in diffs[:20]:
            print(f"  {d['id']:<48}  Δ_total={d['delta_total']:+d}  "
                  f"old={d['old']['total']} → new={d['new']['total']}")


if __name__ == "__main__":
    main()
