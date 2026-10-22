#!/usr/bin/env bash
# Update only the existing human-digital backend. Never provision the VPS or
# change Nginx, firewall, other containers, or the existing .env.
set -Eeuo pipefail

fail() { echo "ERROR: $*" >&2; exit 1; }
note() { echo "==> $*"; }

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

command -v git >/dev/null || fail "git is required"
command -v docker >/dev/null || fail "Docker Compose is required"
command -v curl >/dev/null || fail "curl is required"
docker compose version >/dev/null || fail "Docker Compose plugin is unavailable"

[[ -d .git ]] || fail "Run from the existing Git checkout at /opt/human-digital"
[[ -f .env ]] || fail "Missing .env; deployment will not create or replace credentials"
[[ "$(git rev-parse --abbrev-ref HEAD)" == main ]] || fail "Expected branch main"
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || fail "Tracked files changed locally; resolve before deploying"
[[ "$(git remote get-url origin)" =~ ^(https://github\.com/|git@github\.com:)MiERP/human-digital(\.git)?$ ]] || fail "Unexpected Git origin"
docker compose config --quiet || fail "Compose configuration is invalid"

container_id="$(docker compose ps -q backend)"
[[ -n "$container_id" ]] || fail "Existing backend container not found; refusing first-time provisioning"
[[ "$(docker inspect -f '{{.State.Running}}' "$container_id")" == true ]] || fail "Existing backend is not running"
mount_type="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/app/data"}}{{.Type}}{{end}}{{end}}' "$container_id")"
[[ -n "$mount_type" ]] || fail "Existing backend has no persistent /app/data mount"

binding="$(docker compose port backend 8000)"
port="${binding##*:}"
[[ "$port" =~ ^[0-9]+$ ]] || fail "Cannot determine backend host port"
health_url="http://127.0.0.1:${port}/health"
curl -fsS --max-time 5 "$health_url" | grep -q '"status":"online"' || fail "Existing backend health check failed"

note "Checking GitHub main (no files changed yet)"
git fetch origin main
[[ "$(git rev-parse HEAD)" == "$(git rev-parse FETCH_HEAD)" ]] || fail "Checkout is not current. Run: git pull --ff-only origin main; then rerun this script"
deployed_commit="$(git rev-parse HEAD)"
previous_commit="${PREVIOUS_COMMIT:-}"
if [[ -n "$previous_commit" ]]; then
    git merge-base --is-ancestor "$previous_commit" "$deployed_commit" || fail "PREVIOUS_COMMIT is not an ancestor of deployed commit"
fi

backup_root="${BACKUP_ROOT:-/opt/backups/human-digital}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="$backup_root/$stamp"
install -d -m 700 "$backup_dir/data"
note "Backing up persistent data to $backup_dir"
docker cp "$container_id:/app/data/." "$backup_dir/data/"

# SQLite uses WAL mode. Replace the raw DB copy with an online backup.
db_tmp="/tmp/human-digital-predeploy-$stamp.db"
if docker exec "$container_id" test -f /app/data/child_memory.db; then
    docker exec "$container_id" python -c \
        'import sqlite3,sys; src=sqlite3.connect("/app/data/child_memory.db"); dst=sqlite3.connect(sys.argv[1]); src.backup(dst); dst.close(); src.close()' \
        "$db_tmp"
    docker cp "$container_id:$db_tmp" "$backup_dir/data/child_memory.db"
    rm -f "$backup_dir/data/child_memory.db-wal" "$backup_dir/data/child_memory.db-shm"
fi
printf '%s\n' "$(docker inspect -f '{{.Image}}' "$container_id")" > "$backup_dir/previous-image-id.txt"
if [[ -n "$previous_commit" ]]; then
    printf '%s\n' "$previous_commit" > "$backup_dir/previous-commit.txt"
fi

note "Rebuilding only the human-digital backend"
if ! docker compose up -d --no-deps --build backend; then
    fail "Backend update failed. Data backup: $backup_dir"
fi

note "Waiting for backend health"
healthy=false
for attempt in {1..30}; do
    if curl -fsS --max-time 5 "$health_url" | grep -q '"status":"online"' \
        && curl -fsS --max-time 5 "http://127.0.0.1:${port}/api/companions" >/dev/null; then
        healthy=true
        break
    fi
    sleep 2
done
[[ "$healthy" == true ]] || fail "Backend failed verification. Data backup: $backup_dir"

note "Backend deployed and healthy. havsAI, Nginx, firewall, .env, and other containers were not changed."
note "Backup: $backup_dir; deployed commit: $deployed_commit; previous commit: ${previous_commit:-not supplied}"
