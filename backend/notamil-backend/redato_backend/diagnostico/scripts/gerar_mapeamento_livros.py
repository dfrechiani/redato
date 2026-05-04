"""Script standalone: gera mapeamento_livro_descritores.json (Fase 5A.1).

Roda UMA VEZ (não em prod) — Daniel decide quando re-rodar (após
revisão pedagógica ou quando livro mudar).

Uso:
    cd backend/notamil-backend
    OPENAI_API_KEY=sk-... python -m redato_backend.diagnostico.scripts.gerar_mapeamento_livros

Saída:
    docs/redato/v3/diagnostico/mapeamento_livro_descritores.json

Comportamento:
- Sem OPENAI_API_KEY: imprime erro e sai com código 2 (não gera
  placeholder — falha barulhenta evita JSON inválido em prod).
- Com OPENAI_API_KEY: parseia 3 livros, mapeia cada oficina via
  GPT-4.1, persiste JSON. Imprime progresso e custo total.
- Falhas em oficinas individuais NÃO param o pipeline — script
  imprime warning e continua. JSON final marca essas oficinas
  com "mapeamento_falhou: true".

NÃO escreve no banco. NÃO chama em runtime. JSON é estático.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Configuração de paths
# ──────────────────────────────────────────────────────────────────────

# Paths esperados dos livros (canônicos quando existem em
# docs/redato/v3/livros/, fallback pra raiz pra 1S que ainda não
# foi versionado naquele dir).
_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_REPO_ROOT = _BACKEND_ROOT.parent.parent  # redato_hash/

LIVROS = [
    {
        "serie": "1S",
        "paths": [
            _REPO_ROOT / "docs/redato/v3/livros/LIVRO_ATO_1S_PROF.html",
            _REPO_ROOT / "LIVRO_1S_PROF_v3_COMPLETO-checkpoints.html",
        ],
    },
    {
        "serie": "2S",
        "paths": [
            _REPO_ROOT / "docs/redato/v3/livros/LIVRO_ATO_2S_PROF.html",
            _REPO_ROOT / "LIVRO_ATO_2S_PROF.html",
        ],
    },
    {
        "serie": "3S",
        "paths": [
            _REPO_ROOT / "docs/redato/v3/livros/LIVRO_ATO_3S_PROF.html",
            _REPO_ROOT / "LIVRO_ATO_3S_v8_PROF (1).html",
        ],
    },
]

OUTPUT_PATH = (
    _REPO_ROOT / "docs/redato/v3/diagnostico/mapeamento_livro_descritores.json"
)


# ──────────────────────────────────────────────────────────────────────
# Resolução de paths
# ──────────────────────────────────────────────────────────────────────

def _resolver_path_livro(paths: List[Path]) -> Optional[Path]:
    """Retorna primeiro path existente da lista (preferência: canônico
    em docs/v3/livros/, fallback: raiz)."""
    for p in paths:
        if p.exists():
            return p
    return None


# ──────────────────────────────────────────────────────────────────────
# Pipeline
# ──────────────────────────────────────────────────────────────────────

def _formatar_progresso(i: int, total: int, codigo: str, tempo_s: float) -> str:
    return f"  [{i:2d}/{total}] {codigo} … {tempo_s:.1f}s"


def gerar_mapeamento_completo(
    *, output_path: Path = OUTPUT_PATH, verbose: bool = True,
    heuristic: bool = False,
) -> Dict[str, Any]:
    """Executa pipeline completo: 3 livros → 42 mapeamentos → JSON.

    Args:
        output_path: onde gravar o JSON (default canônico).
        verbose: imprime progresso por oficina.
        heuristic: se True, usa `mapeador_heuristico` em vez de LLM.
            Output marca `gerador='heuristico-v1'`. Útil pra
            bootstrap antes de rodar o pipeline LLM real, ou pra
            ambientes sem OPENAI_API_KEY.

    Returns:
        Dict serializado (mesmo conteúdo do JSON gravado).

    Raises:
        Não levanta — falhas individuais ficam marcadas no payload.
        Falha catastrófica (sem API key em modo LLM, módulo broken)
        sai do processo com código 2.
    """
    from redato_backend.diagnostico.parser_livros import (
        extrair_oficinas_do_livro,
    )
    from redato_backend.diagnostico import load_descritores

    if heuristic:
        from redato_backend.diagnostico.mapeador_heuristico import (
            mapear_oficina_heuristico as _mapear,
        )

        def mapear(of, descritores_yaml=None):
            return _mapear(of, descritores_yaml=descritores_yaml)
    else:
        from redato_backend.diagnostico.mapeador import (
            mapear_oficina_para_descritores as _mapear,
        )

        def mapear(of, descritores_yaml=None):
            return _mapear(of, descritores_yaml=descritores_yaml)

        # Validação cedo: precisa de chave em modo LLM
        if not os.environ.get("OPENAI_API_KEY"):
            print(
                "ERRO: OPENAI_API_KEY não setada no ambiente.",
                file=sys.stderr,
            )
            print(
                "Opções:\n"
                "  1. export OPENAI_API_KEY=sk-... (modo LLM, $0.85)\n"
                "  2. python -m ... --heuristic (modo baseline, $0)\n",
                file=sys.stderr,
            )
            sys.exit(2)

    # Carrega descritores 1x (cache module-level)
    descritores = load_descritores()
    if verbose:
        print(f"Descritores carregados: {len(descritores)}")
        print()

    # Parseia os 3 livros
    todas_oficinas: List[Any] = []
    for livro_cfg in LIVROS:
        path = _resolver_path_livro(livro_cfg["paths"])
        if path is None:
            print(
                f"AVISO: livro {livro_cfg['serie']} não encontrado em "
                f"nenhum dos paths esperados — pulando",
                file=sys.stderr,
            )
            continue
        if verbose:
            print(f"Parseando {livro_cfg['serie']} ({path.name}) …")
        ofs = extrair_oficinas_do_livro(str(path), livro_cfg["serie"])
        if verbose:
            print(
                f"  → {len(ofs)} oficinas extraídas "
                f"({sum(1 for o in ofs if o.tem_redato_avaliavel)} avaliáveis)"
            )
        todas_oficinas.extend(ofs)
    if verbose:
        print(f"\nTotal: {len(todas_oficinas)} oficinas pra mapear\n")

    # Pra cada oficina, chama mapeador
    mapeamentos: List[Dict[str, Any]] = []
    falhas: List[str] = []
    custo_total = 0.0
    latencia_total_ms = 0
    started_global = time.time()

    for i, of in enumerate(todas_oficinas, start=1):
        t0 = time.time()
        m = mapear(of, descritores_yaml=descritores)
        elapsed = time.time() - t0
        if verbose:
            print(_formatar_progresso(
                i, len(todas_oficinas), of.codigo, elapsed,
            ))
        if m is None:
            falhas.append(of.codigo)
            mapeamentos.append({
                "codigo": of.codigo,
                "serie": of.serie,
                "oficina_numero": of.oficina_numero,
                "titulo": of.titulo,
                "tem_redato_avaliavel": of.tem_redato_avaliavel,
                "mapeamento_falhou": True,
                "descritores_trabalhados": [],
                "competencias_principais": [],
                "tipo_atividade": None,
            })
            continue
        d = m.to_dict()
        d["mapeamento_falhou"] = False
        mapeamentos.append(d)
        custo_total += m.custo_estimado_usd
        latencia_total_ms += m.latencia_ms

    elapsed_total = time.time() - started_global

    # Constrói payload final
    if heuristic:
        descricao = (
            "Mapeamento BASELINE gerado por heurística (keyword match), "
            "SEM LLM. Cobre todas as oficinas mas perde nuance. "
            "Re-rodar com OPENAI_API_KEY pra upgradear pra LLM. "
            "Status 'em_revisao' até Daniel revisar e/ou substituir "
            "pelo output LLM."
        )
        modelo_label = "heuristico-v1"
    else:
        descricao = (
            "Mapeamento automático livro→descritores gerado por LLM "
            "(GPT-4.1). AVISO: rascunho não revisado por especialista "
            "— Daniel revisa em sessão futura (Fase 5A.1.review)."
        )
        modelo_label = (
            os.environ.get("REDATO_DIAGNOSTICO_MODELO")
            or "gpt-4.1-2025-04-14"
        )
    payload = {
        "versao": "1.0",
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "gerador": "heuristico" if heuristic else "llm",
        "modelo_usado": modelo_label,
        "status": "em_revisao",
        "descricao": descricao,
        "estatisticas": {
            "total_oficinas": len(mapeamentos),
            "mapeamentos_ok": sum(
                1 for m in mapeamentos if not m.get("mapeamento_falhou", False)
            ),
            "mapeamentos_falhos": len(falhas),
            "total_descritores_atribuidos": sum(
                len(m.get("descritores_trabalhados", []))
                for m in mapeamentos
            ),
            "custo_total_usd": round(custo_total, 4),
            "latencia_total_min": round(latencia_total_ms / 60_000, 2),
            "elapsed_global_min": round(elapsed_total / 60, 2),
        },
        "oficinas": mapeamentos,
    }

    # Persiste
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if verbose:
        print()
        print("=" * 60)
        print("Pipeline concluído.")
        print(f"  Total oficinas: {len(mapeamentos)}")
        print(
            f"  Mapeamentos OK: "
            f"{payload['estatisticas']['mapeamentos_ok']}"
        )
        print(f"  Falhas: {len(falhas)}{' — ' + ', '.join(falhas) if falhas else ''}")
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
    import argparse
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="Gera mapeamento_livro_descritores.json (Fase 5A.1)",
    )
    parser.add_argument(
        "--heuristic", action="store_true",
        help=(
            "Usa heurística baseline (keyword match) em vez de LLM. "
            "Útil quando OPENAI_API_KEY não disponível ou pra "
            "bootstrap rápido. Output marca gerador='heuristico-v1'."
        ),
    )
    args = parser.parse_args()
    gerar_mapeamento_completo(heuristic=args.heuristic)


if __name__ == "__main__":
    main()
