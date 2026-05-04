"""Script standalone: gera mapeamento_descritores_bncc.json (Fase 5A.2).

Roda UMA VEZ (não em prod). Daniel decide quando re-rodar (após
revisão pedagógica ou quando catálogo BNCC ganhar versão nova).

Uso:
    cd backend/notamil-backend
    OPENAI_API_KEY=sk-... python -m redato_backend.diagnostico.scripts.gerar_mapeamento_bncc

Saída:
    docs/redato/v3/diagnostico/mapeamento_descritores_bncc.json

Custo estimado: ~$0.40 (40 descritores × ~$0.01).
Latência estimada: ~3 min (~5s/descritor).

Sem OPENAI_API_KEY, o script sai com código 2 e instrução clara —
diferente do `gerar_mapeamento_livros.py` que tem fallback heurístico
(BNCC NÃO tem fallback heurístico fiel, então melhor falhar barulhento
do que produzir mapeamento sem qualidade).
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Configuração de paths
# ──────────────────────────────────────────────────────────────────────

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_REPO_ROOT = _BACKEND_ROOT.parent.parent

OUTPUT_PATH = (
    _REPO_ROOT / "docs/redato/v3/diagnostico/mapeamento_descritores_bncc.json"
)


# ──────────────────────────────────────────────────────────────────────
# Pipeline
# ──────────────────────────────────────────────────────────────────────

def gerar_mapeamento_completo(
    *, output_path: Path = OUTPUT_PATH, verbose: bool = True,
) -> Dict[str, Any]:
    """Executa pipeline completo: 40 descritores → 40 mapeamentos
    BNCC → JSON.

    Returns:
        Dict serializado (mesmo conteúdo do JSON gravado).

    Raises:
        Não levanta — falhas individuais ficam marcadas no payload.
        Falha catastrófica (sem API key) sai com código 2.
    """
    from redato_backend.diagnostico import load_descritores
    from redato_backend.diagnostico.mapeador_bncc import (
        mapear_descritor_para_bncc,
    )

    if not os.environ.get("OPENAI_API_KEY"):
        print(
            "ERRO: OPENAI_API_KEY não setada no ambiente.",
            file=sys.stderr,
        )
        print(
            "Pra gerar o mapeamento BNCC:\n"
            "  export OPENAI_API_KEY=sk-...\n"
            "  python -m redato_backend.diagnostico.scripts.gerar_mapeamento_bncc\n"
            "\nCusto estimado: ~$0.40 (40 descritores × ~$0.01).\n"
            "Latência estimada: ~3 min.\n",
            file=sys.stderr,
        )
        sys.exit(2)

    descritores = load_descritores()
    if verbose:
        print(f"Descritores carregados: {len(descritores)}")
        print()

    mapeamentos: List[Dict[str, Any]] = []
    falhas: List[str] = []
    custo_total = 0.0
    latencia_total_ms = 0
    started_global = time.time()

    for i, d in enumerate(descritores, start=1):
        t0 = time.time()
        m = mapear_descritor_para_bncc(d)
        elapsed = time.time() - t0
        if verbose:
            print(f"  [{i:2d}/{len(descritores)}] {d.id} … {elapsed:.1f}s")
        if m is None:
            falhas.append(d.id)
            mapeamentos.append({
                "descritor_id": d.id,
                "descritor_nome": d.nome,
                "descritor_competencia": d.competencia,
                "habilidades_bncc": [],
                "mapeamento_falhou": True,
            })
            continue
        out = m.to_dict()
        out["mapeamento_falhou"] = False
        mapeamentos.append(out)
        custo_total += m.custo_estimado_usd
        latencia_total_ms += m.latencia_ms

    elapsed_total = time.time() - started_global

    # Estatísticas
    todas_habilidades: set = set()
    total_atribuicoes = 0
    for m in mapeamentos:
        for h in m.get("habilidades_bncc", []) or []:
            cod = h.get("codigo")
            if cod:
                todas_habilidades.add(cod)
                total_atribuicoes += 1

    payload = {
        "versao": "1.0",
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "modelo_usado": (
            os.environ.get("REDATO_DIAGNOSTICO_MODELO")
            or "gpt-4.1-2025-04-14"
        ),
        "status": "em_revisao",
        "descricao": (
            "Mapeamento descritor → habilidades BNCC EM-LP gerado por "
            "LLM (GPT-4.1). AVISO: rascunho não revisado por "
            "especialista — Daniel revisa em sessão futura "
            "(Fase 5A.2.review)."
        ),
        "estatisticas": {
            "total_descritores": len(mapeamentos),
            "mapeamentos_ok": sum(
                1 for m in mapeamentos if not m.get("mapeamento_falhou", False)
            ),
            "mapeamentos_falhos": len(falhas),
            "total_atribuicoes": total_atribuicoes,
            "habilidades_unicas": len(todas_habilidades),
            "custo_total_usd": round(custo_total, 4),
            "latencia_total_min": round(latencia_total_ms / 60_000, 2),
            "elapsed_global_min": round(elapsed_total / 60, 2),
        },
        "mapeamentos": mapeamentos,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if verbose:
        print()
        print("=" * 60)
        print("Pipeline BNCC concluído.")
        print(f"  Descritores processados: {len(mapeamentos)}")
        print(
            f"  Mapeamentos OK: "
            f"{payload['estatisticas']['mapeamentos_ok']}"
        )
        print(
            f"  Falhas: {len(falhas)}"
            f"{' — ' + ', '.join(falhas) if falhas else ''}"
        )
        print(
            f"  Habilidades BNCC distintas: "
            f"{payload['estatisticas']['habilidades_unicas']} de 54"
        )
        print(
            f"  Custo total: $"
            f"{payload['estatisticas']['custo_total_usd']}"
        )
        print(
            f"  Latência total: "
            f"{payload['estatisticas']['latencia_total_min']} min "
            f"(real: {payload['estatisticas']['elapsed_global_min']} min)"
        )
        print(f"  Saída: {output_path}")
        print("=" * 60)

    return payload


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    gerar_mapeamento_completo()


if __name__ == "__main__":
    main()
