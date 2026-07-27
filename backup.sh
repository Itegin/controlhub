#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

R='\033[0;31m'; G='\033[0;32m'; N='\033[0m'
fail() { echo -e "${R}✗ $1${N}" >&2; exit 1; }
ok()   { echo -e "${G}✓ $1${N}"; }

DB_PATH="data/controlhub.db"
BACKUP_DIR="data/backups"
KEEP=14

[ -f "$DB_PATH" ] || fail "$DB_PATH not found -- run this from the repo root on the host where the backend actually runs."

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y-%m-%d-%H%M%S)
DEST="$BACKUP_DIR/controlhub-$TIMESTAMP.db"

# .backup (not cp): the live db runs in WAL mode (see CLAUDE.md), so a
# plain file copy can grab it mid-write, mid-checkpoint, or miss data
# still sitting in the -wal file. sqlite3's .backup command uses the
# SQLite Online Backup API instead, which produces a consistent snapshot
# even while the backend is actively reading/writing.
sqlite3 "$DB_PATH" ".backup '$DEST'" || fail "sqlite3 .backup failed"

ok "Backed up to $DEST"

# Keep only the last KEEP backups. LC_ALL=C for a locale-independent sort
# (same fix already applied to the code-freshness check elsewhere in this
# repo) -- filenames are zero-padded YYYY-MM-DD-HHMMSS, so lexicographic
# sort order is chronological order.
mapfile -t BACKUPS < <(find "$BACKUP_DIR" -maxdepth 1 -name 'controlhub-*.db' | LC_ALL=C sort)
COUNT=${#BACKUPS[@]}
if [ "$COUNT" -gt "$KEEP" ]; then
    TO_DELETE=$((COUNT - KEEP))
    for i in $(seq 0 $((TO_DELETE - 1))); do
        rm -f -- "${BACKUPS[$i]}"
    done
    ok "Removed $TO_DELETE old backup(s), kept last $KEEP"
fi

# Not installed automatically -- add this yourself via `crontab -e` to run
# daily at 3am (adjust the path if the repo lives somewhere else on the
# host); backup.sh resolves its own directory via `cd "$(dirname "$0")"`
# above, so invoking it by absolute path from cron works with no extra cd:
#
#   0 3 * * * /path/to/controlhub/backup.sh >> /path/to/controlhub/data/backups/backup.log 2>&1
