#!/usr/bin/env bash
# Backup manual do Postgres do portal (M8+).
#
# Railway tem snapshot automático no plano pago, mas:
# - Snapshots ficam só no Railway (vendor lock-in).
# - Restore exige UI manual; não dá pra automatizar.
# - Snapshot diário tem janela de até 24h — perde até 1 dia se cair.
#
# Esse script roda `pg_dump` contra a `DATABASE_URL` apontada e salva
# em `data/portal/backups/{ano}/{mes}/redato_<timestamp>.dump`. Em
# produção, agendar via cron externo apontando pra `DATABASE_URL` do
# Railway (read-only replica preferível, se houver).
#
# Uso:
#   bash scripts/backup_postgres.sh                  # commit em data/
#   bash scripts/backup_postgres.sh --to s3://bucket  # upload S3
#   bash scripts/backup_postgres.sh --restore <file>  # restore (perigoso)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
BACKUPS_DIR="$BACKEND_DIR/data/portal/backups"

# Carrega .env se existir
if [[ -f "$BACKEND_DIR/.env" ]]; then
    set -a; source "$BACKEND_DIR/.env"; set +a
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "ERRO: DATABASE_URL não setada (no env ou .env)." >&2
    exit 1
fi

# ──────────────────────────────────────────────────────────────────────
# Subcommands
# ──────────────────────────────────────────────────────────────────────

cmd_backup() {
    local ts ano mes out_dir out_file
    ts="$(date -u +%Y%m%dT%H%M%SZ)"
    ano="$(date -u +%Y)"
    mes="$(date -u +%m)"
    out_dir="$BACKUPS_DIR/$ano/$mes"
    out_file="$out_dir/redato_${ts}.dump"

    mkdir -p "$out_dir"
    echo "▶ Dumping → $out_file"
    pg_dump --format=custom --no-owner --no-privileges \
            --dbname="$DATABASE_URL" \
            --file="$out_file"
    local size
    size="$(du -h "$out_file" | cut -f1)"
    echo "✓ OK — $size"

    # Limita histórico local: mantém últimos 30 dumps
    local count
    count="$(find "$BACKUPS_DIR" -name "redato_*.dump" 2>/dev/null | wc -l | tr -d ' ')"
    if (( count > 30 )); then
        echo "▶ Limpando dumps antigos (mantém 30 mais recentes)…"
        find "$BACKUPS_DIR" -name "redato_*.dump" -print0 \
            | xargs -0 ls -t \
            | tail -n +31 \
            | xargs rm -f
    fi
    echo "$out_file"
}

cmd_restore() {
    local dump_file="$1"
    if [[ ! -f "$dump_file" ]]; then
        echo "ERRO: arquivo $dump_file não existe" >&2
        exit 1
    fi
    echo ""
    echo "⚠️  PERIGO: vai sobrescrever DATABASE_URL=$DATABASE_URL"
    echo "    com o conteúdo de $dump_file"
    echo ""
    read -p "Digite 'RESTORE' pra confirmar: " confirm
    [[ "$confirm" == "RESTORE" ]] || { echo "Abortado."; exit 1; }

    echo "▶ Aplicando dump…"
    pg_restore --clean --if-exists --no-owner --no-privileges \
               --dbname="$DATABASE_URL" \
               "$dump_file"
    echo "✓ Restore OK. Confirme via /admin/health/full."
}

cmd_help() {
    cat <<'EOF'
Uso:
  scripts/backup_postgres.sh                       Faz backup
  scripts/backup_postgres.sh --restore <file>      Restaura backup
  scripts/backup_postgres.sh --help                Esta ajuda

Política de retenção: mantém 30 dumps mais recentes em
data/portal/backups/. Pra retenção maior, copie pra S3/GCS ou
configure cron com nome único.
EOF
}

# ──────────────────────────────────────────────────────────────────────

case "${1:-backup}" in
    backup|"") cmd_backup ;;
    --restore) shift; cmd_restore "$1" ;;
    --help|-h) cmd_help ;;
    *) echo "ERRO: comando desconhecido: $1" >&2; cmd_help; exit 2 ;;
esac
