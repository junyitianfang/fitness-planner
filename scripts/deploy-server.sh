#!/usr/bin/env bash
set -euo pipefail
# Run on the existing Instabox. Arguments are uploaded archives and public HTTPS origin.
release_archive=${1:?release archive required}
seed_archive=${2:?seed archive required}
origin=${3:?HTTPS origin required}
case "$origin" in https://*) ;; *) echo 'An HTTPS origin is required.' >&2; exit 2;; esac
root=/data/home/fitness-planner
release="$root/releases/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$release" "$root/data" "$root/backups"
tar -xzf "$release_archive" -C "$release"

if [ ! -f "$root/data/fitness.sqlite" ]; then
    tar -xzf "$seed_archive" -C "$root/data"
fi
sudo chown -R 10001:10001 "$root/data"
cat > "$release/.env" <<EOF
FITNESS_HOST_DATA_DIR=$root/data
FITNESS_PORT=8010
FITNESS_ORIGIN=$origin
FITNESS_SECURE_COOKIE=true
EOF
cd "$release"
docker compose config --quiet
docker compose build

# Only this application's existing service is affected when updating.
if [ -L "$root/current" ]; then
    previous=$(readlink -f "$root/current")
    (cd "$previous" && docker compose stop fitness)
    sudo tar -czf "$root/backups/data-$(date -u +%Y%m%dT%H%M%SZ).tar.gz" -C "$root/data" .
fi
docker compose up -d --wait --wait-timeout 120
ln -sfn "$release" "$root/current"
docker compose ps
printf '\nProject: %s\nData: %s\nOrigin: %s\n' "$root/current" "$root/data" "$origin"
