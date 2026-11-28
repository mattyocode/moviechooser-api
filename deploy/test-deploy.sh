#!/bin/sh
# Runs deploy.sh against a throwaway copy of the production stack and checks
# that it deploys, keeps the old api on a failed migration, and rolls back an
# api that never becomes healthy.
#
#   sh deploy/test-deploy.sh [runtime image]   # default: moviechooser-api:runtime
#
# Images are pushed to a local registry so deploy.sh can pull them by digest,
# as it does from GHCR. cloudflared is replaced by a sleeping container (it
# needs a real tunnel token) and the frontend by plain nginx.
set -eu

cd "$(dirname "$0")/.."

runtime=${1:-moviechooser-api:runtime}
run_id="deploy-test-$$"
port=${REGISTRY_PORT:-5005}
registry="localhost:$port"
work=$(mktemp -d)
project="mcdeploytest$$"

cleanup() {
  status=$?
  if [ "$status" -ne 0 ] && [ -f "$work/.env" ]; then
    echo "--- compose ps ---" >&2
    (cd "$work" && docker compose ps -a >&2) || true
    echo "--- api logs ---" >&2
    (cd "$work" && docker compose logs --tail 30 api >&2) || true
  fi
  (cd "$work" && docker compose down -v --remove-orphans >/dev/null 2>&1) || true
  docker rm -f "$run_id-registry" >/dev/null 2>&1 || true
  docker image ls --format '{{.Repository}}:{{.Tag}}' | grep "^$registry/" |
    xargs -r docker rmi -f >/dev/null 2>&1 || true
  docker image ls --format '{{.Repository}}:{{.Tag}}' | grep "^$run_id-" |
    xargs -r docker rmi -f >/dev/null 2>&1 || true
  rm -rf "$work"
  exit "$status"
}
trap cleanup EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}
pass() { echo "ok - $*"; }

docker image inspect "$runtime" >/dev/null 2>&1 || fail "no image $runtime; build the runtime target first"

docker run -d --name "$run_id-registry" -p "127.0.0.1:$port:5000" registry:2.8.3 >/dev/null
i=0
until curl -fs "http://$registry/v2/" >/dev/null 2>&1; do
  i=$((i + 1))
  [ "$i" -lt 30 ] || fail "local registry didn't start"
  sleep 1
done

# Builds an image from a Dockerfile on stdin, pushes it, prints name@digest.
push() {
  name=$1
  docker build -q -t "$run_id-$name" - >/dev/null
  docker tag "$run_id-$name" "$registry/$name:test"
  docker push -q "$registry/$name:test" >/dev/null
  docker image inspect -f '{{range .RepoDigests}}{{println .}}{{end}}' "$registry/$name:test" |
    grep "^$registry/$name@sha256:"
}

api_good=$(printf 'FROM %s\n' "$runtime" | push api-good)
# Migrations fail; everything else is the real image.
api_badmigrate=$(
  push api-badmigrate <<EOF
FROM $runtime
USER root
RUN echo 'import sys; sys.exit("migrate broken")' > /app/manage.py
USER app
EOF
)
# Migrates fine, but gunicorn never starts, so the health check never passes.
api_unhealthy=$(printf 'FROM %s\nENTRYPOINT ["sleep", "infinity"]\n' "$runtime" | push api-unhealthy)
frontend=$(printf 'FROM nginxinc/nginx-unprivileged:stable-alpine\n' | push frontend)

cp docker-compose.prod.yml deploy/deploy.sh "$work/"
cat >"$work/docker-compose.test.yml" <<'EOF'
services:
  cloudflared:
    image: alpine:latest
    command: ["sleep", "infinity"]
EOF
cat >"$work/.env" <<EOF
COMPOSE_FILE=docker-compose.prod.yml:docker-compose.test.yml
COMPOSE_PROJECT_NAME=$project
EOF
cat >"$work/.env.prod" <<'EOF'
SECRET_KEY=deploy-test-secret-key-0123456789-abcdefghijklmnopqrstuvwxyz
DJANGO_ALLOWED_HOSTS=moviechooser.co.uk localhost
SQL_ENGINE=django.db.backends.postgresql
SQL_DATABASE=mc
SQL_USER=mc
SQL_PASSWORD=pw
SQL_HOST=db
SQL_PORT=5432
EOF
cat >"$work/.env.prod.db" <<'EOF'
POSTGRES_USER=mc
POSTGRES_PASSWORD=pw
POSTGRES_DB=mc
EOF
: >"$work/.env.tunnel"

deploy() { (cd "$work" && DEPLOY_WAIT_TIMEOUT=${WAIT:-180} DEPLOY_LOCK_TIMEOUT=${DEPLOY_LOCK_TIMEOUT:-60} sh ./deploy.sh "$@"); }
env_value() { sed -n "s/^$1=//p" "$work/.env"; }
running_image() { (cd "$work" && docker inspect -f '{{.Config.Image}}' "$(docker compose ps -q "$1")"); }
health() { (cd "$work" && docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -q "$1")"); }

# Rejects a tag: a tag can move between pull and up.
if deploy api "$registry/api-good:test" >/dev/null 2>&1; then
  fail "deploy.sh accepted an image without a digest"
fi
pass "rejects an image that isn't pinned by digest"

deploy api "$api_good" || fail "first api deploy failed"
[ "$(env_value API_IMAGE)" = "$api_good" ] || fail "API_IMAGE not recorded in .env"
for s in api celery-worker celery-beat; do
  [ "$(running_image "$s")" = "$api_good" ] || fail "$s runs $(running_image "$s")"
done
[ "$(health api)" = healthy ] || fail "api is $(health api)"
(cd "$work" && docker compose exec -T db psql -U mc -d mc -tAc "select to_regclass('django_cache')") |
  grep -q django_cache || fail "createcachetable didn't run"
(cd "$work" && docker compose exec -T db psql -U mc -d mc -tAc "select count(*) from django_migrations") |
  grep -qv '^0$' || fail "migrations didn't run"
pass "deploys api: migrates, creates the cache table, api healthy, worker and beat on the new image"

if deploy api "$api_badmigrate"; then fail "deploy succeeded with a failing migration"; fi
[ "$(env_value API_IMAGE)" = "$api_good" ] || fail "API_IMAGE changed after a failed migration"
[ "$(running_image api)" = "$api_good" ] || fail "api was replaced after a failed migration"
[ "$(health api)" = healthy ] || fail "api is $(health api) after a failed migration"
pass "failed migration: deploy fails, running api untouched"

if WAIT=45 deploy api "$api_unhealthy"; then fail "deploy succeeded with an api that never gets healthy"; fi
[ "$(env_value API_IMAGE)" = "$api_good" ] || fail "API_IMAGE not rolled back"
[ "$(running_image api)" = "$api_good" ] || fail "api not rolled back: runs $(running_image api)"
[ "$(health api)" = healthy ] || fail "api is $(health api) after rollback"
pass "unhealthy api: deploy fails and rolls back to the previous image"

# Another deploy holds the lock: wait, then give up without touching anything.
(cd "$work" && flock .deploy.lock sleep 8) &
holder=$!
sleep 1
if DEPLOY_LOCK_TIMEOUT=2 deploy frontend "$frontend" 2>"$work/lock.err"; then
  fail "deploy ran while another held the lock"
fi
grep -q "another deploy" "$work/lock.err" || fail "unexpected lock error: $(cat "$work/lock.err")"
[ -z "$(env_value FRONTEND_IMAGE)" ] || fail "FRONTEND_IMAGE set by a deploy that never got the lock"
wait "$holder"
pass "waits for another deploy's lock, and gives up cleanly"

deploy frontend "$frontend" || fail "frontend deploy failed"
[ "$(env_value FRONTEND_IMAGE)" = "$frontend" ] || fail "FRONTEND_IMAGE not recorded in .env"
[ "$(env_value API_IMAGE)" = "$api_good" ] || fail "frontend deploy changed API_IMAGE"
[ "$(running_image frontend)" = "$frontend" ] || fail "frontend runs $(running_image frontend)"
[ "$(running_image api)" = "$api_good" ] || fail "frontend deploy changed the api"
pass "deploys frontend without touching the api"

echo "All deploy checks passed."
