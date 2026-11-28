#!/bin/sh
# Deploys one image to the production stack. Runs on the server, from the
# directory that holds docker-compose.prod.yml, .env and the env files
# (/srv/moviechooser). CI calls it after pushing an image; it also works by hand,
# for example to roll back to an earlier digest.
#
#   deploy.sh api      ghcr.io/mattyocode/mattyocode/moviechooser-api@sha256:<digest>
#   deploy.sh frontend ghcr.io/mattyocode/react-moviechooser@sha256:<digest>
#
# For api it runs `migrate` and `createcachetable` with the new image first, so a
# failed migration leaves the running containers alone. The image is recorded in
# .env (API_IMAGE / FRONTEND_IMAGE), so `docker compose` commands run by hand use
# the same images. If the new containers don't become healthy, it puts the
# previous image back.
#
# DEPLOY_WAIT_TIMEOUT (seconds, default 240) caps the wait for healthy containers;
# DEPLOY_LOCK_TIMEOUT (seconds, default 900) caps the wait for another deploy.
set -eu

cd "$(dirname "$0")"

die() {
  echo "deploy: $*" >&2
  exit 1
}

[ $# -eq 2 ] || die "usage: deploy.sh api|frontend <image>@sha256:<digest>"
target=$1
image=$2

case $target in
  api)
    var=API_IMAGE
    # db and redis start with them as dependencies.
    services="api celery-worker celery-beat"
    ;;
  frontend)
    var=FRONTEND_IMAGE
    services="frontend cloudflared"
    ;;
  *) die "unknown target '$target' (want api or frontend)" ;;
esac

# A tag can move under us between pull and up; a digest can't.
case $image in
  *@sha256:*) ;;
  *) die "image must be pinned by digest (<image>@sha256:...), got '$image'" ;;
esac

[ -f .env ] || die "no .env in $(pwd)"
[ -f docker-compose.prod.yml ] || die "no docker-compose.prod.yml in $(pwd)"

wait_timeout=${DEPLOY_WAIT_TIMEOUT:-240}

# The api and frontend repos deploy independently; run one at a time.
exec 9>.deploy.lock
flock -w "${DEPLOY_LOCK_TIMEOUT:-900}" 9 || die "timed out waiting for another deploy to finish"

get_var() {
  sed -n "s/^$1=//p" .env | tail -n 1
}

# Rewrite .env in place (cat >, not mv), so its owner and mode stay as set up.
set_var() {
  awk -v key="$1" -v value="$2" '
    BEGIN { done = 0 }
    index($0, key "=") == 1 { if (!done) print key "=" value; done = 1; next }
    { print }
    END { if (!done) print key "=" value }
  ' .env >.env.tmp
  cat .env.tmp >.env
  rm -f .env.tmp
}

previous=$(get_var "$var")
echo "deploy: $target $image (previous: ${previous:-none})"

docker pull -q "$image"

if [ "$target" = api ]; then
  echo "deploy: migrating with the new image"
  docker compose up -d --wait db redis
  # Shell env overrides .env, so only these one-off containers use the new image.
  API_IMAGE=$image docker compose run --rm --no-deps -T --entrypoint python api \
    manage.py migrate --noinput
  API_IMAGE=$image docker compose run --rm --no-deps -T --entrypoint python api \
    manage.py createcachetable
fi

set_var "$var" "$image"
# shellcheck disable=SC2086 # $services is a list of service names
if docker compose up -d --wait --wait-timeout "$wait_timeout" $services; then
  echo "deploy: $target is up on $image"
  # Unused images older than a week. Earlier digests can still be pulled from GHCR.
  docker image prune -af --filter until=168h >/dev/null || true
  exit 0
fi

echo "deploy: $target didn't become healthy on $image" >&2
# shellcheck disable=SC2086
docker compose ps $services >&2 || true
if [ -z "$previous" ]; then
  die "no previous $var to roll back to; left as is for debugging"
fi
echo "deploy: rolling back to $previous" >&2
set_var "$var" "$previous"
# shellcheck disable=SC2086
docker compose up -d --wait --wait-timeout "$wait_timeout" $services ||
  echo "deploy: the previous image isn't healthy either" >&2
die "deploy failed; rolled back to $previous"
