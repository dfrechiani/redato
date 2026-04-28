#!/usr/bin/env bash
# Sincroniza docs/redato/MEMORY/ (autoritativo, no repo) →
# ~/.claude/projects/-Users-danielfrechiani-Desktop-redato-hash/memory/
# (caminho que o auto-memory do Claude Code carrega em sessões futuras).
#
# Direção é sempre repo → local. Edições devem ser feitas no repo; rodar
# este script depois pra propagar pro auto-load.
#
# Uso:
#   bash scripts/sync_memory.sh

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO_DIR/docs/redato/MEMORY"
DST="$HOME/.claude/projects/-Users-danielfrechiani-Desktop-redato-hash/memory"

if [[ ! -d "$SRC" ]]; then
  echo "ERRO: $SRC não existe." >&2
  exit 1
fi

mkdir -p "$DST"

shopt -s nullglob
synced=0
for path in "$SRC"/*.md; do
  fname=$(basename "$path")
  cp -p "$path" "$DST/$fname"
  echo "  ✓ $fname"
  synced=$((synced + 1))
done

if [[ $synced -eq 0 ]]; then
  echo "Aviso: nenhum .md em $SRC."
else
  echo "Sync OK: $synced arquivo(s) → $DST"
fi
