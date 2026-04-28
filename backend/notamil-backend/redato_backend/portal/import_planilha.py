#!/usr/bin/env python3
"""CLI de importação da planilha SEDUC (M2).

Modos:
- dry-run (default): lê, valida, simula sync, NÃO commita. Imprime relatório.
- commit (--commit): persiste no Postgres se sem erros (ou se forçado).

Uso:
    # Dry-run
    python -m redato_backend.portal.import_planilha planilha.xlsx

    # Commit
    python -m redato_backend.portal.import_planilha planilha.xlsx --commit

    # Permite commit mesmo com erros (perigoso)
    python -m redato_backend.portal.import_planilha planilha.xlsx --commit --no-rollback-on-error

    # Ano letivo customizado
    python -m redato_backend.portal.import_planilha planilha.xlsx --ano 2027

Spec: docs/redato/v3/REPORT_caminho2_realuse.md (seção 5.2 onboarding).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Bootstrap pra rodar como script
_BACKEND = Path(__file__).resolve().parents[2]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# Carrega .env
_env_path = _BACKEND / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        if "=" in _line and not _line.strip().startswith("#"):
            _k, _v = _line.split("=", 1)
            _k, _v = _k.strip(), _v.strip()
            if not os.environ.get(_k):
                os.environ[_k] = _v

from redato_backend.portal.db import get_engine  # noqa: E402
from redato_backend.portal.importer import run_import  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402


def _slug(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", s).strip("_") or "noname"


def _save_report(report_dict: dict, file_path: Path) -> Path:
    """Salva o JSON do relatório em data/portal/imports/."""
    out_dir = _BACKEND / "data" / "portal" / "imports"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    # Tenta extrair escola_codigo do arquivo pra nome do JSON
    escola_codigo = "all"
    if report_dict.get("erros") == [] and report_dict.get("linhas_lidas", 0) > 0:
        escola_codigo = "import"  # placeholder; CLI só sabe arquivo
    name = f"{ts}_{_slug(file_path.stem)}.json"
    out_path = out_dir / name
    out_path.write_text(
        json.dumps(report_dict, ensure_ascii=False, indent=2,
                   default=str),
        encoding="utf-8",
    )
    return out_path


def _print_summary(report_dict: dict) -> None:
    """Print humano-legível do relatório."""
    print(f"\n{'='*70}")
    print(f"Modo: {report_dict['modo']}")
    print(f"Arquivo: {report_dict['arquivo']}")
    print(f"Linhas lidas: {report_dict['linhas_lidas']}")
    print()
    print(f"  Escolas         novas: {report_dict['escolas_novas']:>4}  "
          f"atualizadas: {report_dict['escolas_atualizadas']:>4}")
    print(f"  Coordenadores   novos: {report_dict['coordenadores_novos']:>4}  "
          f"atualizados: {report_dict['coordenadores_atualizados']:>4}")
    print(f"  Professores     novos: {report_dict['professores_novos']:>4}  "
          f"atualizados: {report_dict['professores_atualizados']:>4}")
    print(f"  Turmas          novas: {report_dict['turmas_novas']:>4}  "
          f"atualizadas: {report_dict['turmas_atualizadas']:>4}")
    print()
    n_warn = len(report_dict.get("warnings") or [])
    n_erro = len(report_dict.get("erros") or [])
    print(f"Warnings: {n_warn}")
    print(f"Erros   : {n_erro}")
    if n_erro:
        print("\nPrimeiros 10 erros:")
        for issue in (report_dict.get("erros") or [])[:10]:
            line = issue.get("line")
            field = issue.get("field") or ""
            code = issue.get("code")
            msg = issue.get("message")
            print(f"  L{line}/{field} [{code}]: {msg}")
    if n_warn:
        print("\nWarnings:")
        for issue in (report_dict.get("warnings") or [])[:5]:
            print(f"  [{issue.get('code')}] {issue.get('message')}")


def main():
    parser = argparse.ArgumentParser(
        description="Importa planilha SEDUC (XLSX ou CSV) pro Postgres do portal."
    )
    parser.add_argument("file", help="caminho .xlsx ou .csv")
    parser.add_argument("--commit", action="store_true",
                        help="Persiste no DB. Default é dry-run.")
    parser.add_argument("--no-rollback-on-error", action="store_true",
                        help="Mesmo com erros, comita o que conseguiu. "
                             "Default: rollback se algum erro.")
    parser.add_argument("--ano", type=int, default=None,
                        help="Ano letivo (default: ano corrente UTC)")
    parser.add_argument("--json-only", action="store_true",
                        help="Imprime só o JSON do relatório, sem summary humano.")
    args = parser.parse_args()

    file_path = Path(args.file).resolve()
    if not file_path.exists():
        print(f"ERRO: arquivo não encontrado: {file_path}")
        sys.exit(1)

    if not os.getenv("DATABASE_URL"):
        print("ERRO: DATABASE_URL não configurada. Veja .env.example.")
        sys.exit(1)

    modo = "commit" if args.commit else "dry-run"
    rollback_on_error = not args.no_rollback_on_error

    engine = get_engine()
    with Session(engine) as session:
        report = run_import(
            session, file_path, modo=modo,
            ano_letivo=args.ano,
            rollback_on_error=rollback_on_error,
        )

    report_dict = report.to_dict()
    out_path = _save_report(report_dict, file_path)

    if args.json_only:
        print(json.dumps(report_dict, ensure_ascii=False, default=str))
    else:
        _print_summary(report_dict)
        print(f"\nRelatório salvo em: {out_path}")
        if modo == "dry-run":
            n_erro = len(report_dict.get("erros") or [])
            if n_erro == 0:
                print("\n→ Tudo limpo. Pra persistir, rode com --commit.")
            else:
                print("\n→ Corrija os erros antes de --commit.")

    sys.exit(0 if not report_dict.get("erros") else 2)


if __name__ == "__main__":
    main()
