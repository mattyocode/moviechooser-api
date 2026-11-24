#!/bin/sh
# Boot the runtime image the way the server will: migrate, then start it with
# its own entrypoint (gunicorn as `app`) and wait for the compose health check
# to pass. Also fails if a worker couldn't load the embedding model.
#
# Usage: sh .github/scripts/smoke-runtime.sh <image>
# Needs SECRET_KEY and SQL_* in the environment, and Postgres on localhost.
# SMOKE_NETWORK (default: host) picks the docker network, e.g.
# container:<postgres container> when port 8000 is taken on the host.
set -eu

image="$1"
name=runtime_smoke
network="${SMOKE_NETWORK:-host}"
trap 'docker rm -f "$name" >/dev/null 2>&1 || true' EXIT
# The compose health check sends this Host header, so allow it here too.
hosts="moviechooser.co.uk localhost 127.0.0.1"

run() {
  docker run --network "$network" -e SECRET_KEY -e DJANGO_ALLOWED_HOSTS="$hosts" \
    -e SQL_ENGINE -e SQL_DATABASE -e SQL_USER -e SQL_PASSWORD -e SQL_HOST -e SQL_PORT \
    "$@"
}

echo "== migrate and createcachetable"
run --rm --entrypoint python "$image" manage.py migrate --noinput
run --rm --entrypoint python "$image" manage.py createcachetable

echo "== start with the image's entrypoint"
run -d --name "$name" "$image"

uid=$(docker exec "$name" id -u)
echo "Container UID: $uid"
[ "$uid" != "0" ] || { echo "Container runs as root"; exit 1; }

# Same command as the api healthcheck in docker-compose.prod.yml.
check='import urllib.request as u; u.urlopen(u.Request("http://127.0.0.1:8000/api/health/", headers={"Host": "moviechooser.co.uk"}), timeout=5)'
i=0
until docker exec "$name" python -c "$check" 2>/dev/null; do
  i=$((i + 1))
  if [ "$i" -ge 45 ] || [ "$(docker inspect -f '{{.State.Running}}' "$name")" != "true" ]; then
    echo "Health check never passed"
    docker logs "$name"
    exit 1
  fi
  sleep 2
done
echo "Health check passed"

# Workers log the model load in post_worker_init; give both a moment.
i=0
until [ "$(docker logs "$name" 2>&1 | grep -c 'Embedding model loaded')" -ge 2 ]; do
  i=$((i + 1))
  if [ "$i" -ge 30 ] || docker logs "$name" 2>&1 | grep -q 'Embedding model failed to load'; then
    echo "Embedding model didn't load in every worker"
    docker logs "$name"
    exit 1
  fi
  sleep 2
done
echo "Embedding model loaded in every worker"

docker logs "$name" 2>&1 | tail -n 20
