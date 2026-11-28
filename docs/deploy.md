# Deploying to the Hetzner server

The whole stack runs on one Hetzner Cloud VM (Ubuntu 24.04, amd64) with Docker Compose, from `/srv/moviechooser`. Traffic arrives through a Cloudflare Tunnel: `cloudflared` → `frontend` (nginx) → `api` (gunicorn). No container publishes a port.

## How a deploy works

Each repo deploys itself when CI passes on `main`:

- **moviechooser-api**: after pushing the runtime image, the `deploy` job joins the tailnet as `tag:ci`. It copies `docker-compose.prod.yml` and `deploy/deploy.sh` to `/srv/moviechooser`, then runs `deploy.sh api <image>@sha256:<digest>` over Tailscale SSH.
- **react-moviechooser**: the same, with `deploy.sh frontend <image>@sha256:<digest>`. It doesn't copy anything, so it uses the compose file and script the last api deploy left on the server.

`deploy.sh`:

1. Takes a lock, so an api deploy and a frontend deploy never run at the same time.
2. Pulls the image by digest.
3. For api only: starts `db` and `redis`, then runs `migrate` and `createcachetable` in one-off containers using the **new** image. If either fails, the deploy stops there and the running containers are left as they were.
4. Records the image in `.env` (`API_IMAGE` or `FRONTEND_IMAGE`), so `docker compose` commands you run by hand use the deployed images rather than `:main`.
5. Runs `docker compose up -d --wait` for its services: api, celery-worker and celery-beat, or frontend and cloudflared.
6. If they don't become healthy, it puts the previous image back in `.env`, brings that back up, and fails.

A CI run whose commit is no longer `main`'s tip (a re-run of an old run) doesn't move `:main` and doesn't deploy.

During an api deploy, gunicorn restarts. Expect a few seconds of 502s while the new workers load the embedding model.

`deploy/test-deploy.sh` checks all of this against a throwaway stack. CI runs it on every branch.

## One-time setup

### Tailscale

In the tailnet policy file, give CI SSH access to the server and nothing else:

```jsonc
"tagOwners": {
  "tag:ci":   ["autogroup:admin"],
  "tag:prod": ["autogroup:admin"],
},
"grants": [
  { "src": ["tag:ci"], "dst": ["tag:prod"], "ip": ["tcp:22"] },
],
"ssh": [
  // "accept", not "check": CI can't do the browser re-authentication that "check" needs.
  { "action": "accept", "src": ["tag:ci"], "dst": ["tag:prod"], "users": ["deploy"] },
],
```

Create an OAuth client (Settings → OAuth clients) with the **Auth Keys: write** scope and the tag `tag:ci`. CI's nodes are ephemeral and are removed when the job ends.

### The server

```bash
# Docker Engine + compose plugin: https://docs.docker.com/engine/install/ubuntu/
sudo useradd --create-home --shell /bin/bash --groups docker deploy
sudo install -d -o deploy -g deploy -m 750 /srv/moviechooser

curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --ssh --advertise-tags=tag:prod --hostname=moviechooser
```

As `deploy`, create the files that stay on the server (`chmod 600` the env files):

| file | contents |
|---|---|
| `.env` | `COMPOSE_FILE=docker-compose.prod.yml` and `COMPOSE_PROJECT_NAME=moviechooser`. `deploy.sh` adds `API_IMAGE` and `FRONTEND_IMAGE`. |
| `.env.prod` | Django settings; see `app/.env.example`. `DJANGO_ALLOWED_HOSTS` must include `moviechooser.co.uk`, because the api health check sends that Host header. `SQL_HOST=db`. |
| `.env.prod.db` | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`; see `app/.env.db.example`. |
| `.env.tunnel` | `TUNNEL_TOKEN=<token>` from Cloudflare Zero Trust → Networks → Tunnels. Point the tunnel's public hostname at `http://frontend:8080`. |

The api image on GHCR is public. If the frontend package is private, run `docker login ghcr.io` once as `deploy` with a token that has `read:packages`.

### GitHub secrets

Set these in **both** repos, either as repo secrets or in a `production` environment:

| secret | value |
|---|---|
| `TS_OAUTH_CLIENT_ID`, `TS_OAUTH_SECRET` | the OAuth client above |
| `DEPLOY_HOST` | the server's tailnet name, e.g. `moviechooser` |
| `DEPLOY_USER` | `deploy` |

### First deploy

1. Do the setup above.
2. Merge the api deploy change. The api deploy copies the compose file and script to the server, migrates the empty database, and starts api, worker and beat.
3. Merge the frontend's deploy change. That starts frontend and cloudflared, and the site is live.
4. Load the data. The database starts empty; restore a dump, or run the import and `fetch_plots`, `build_plot_embeddings`, `map_tmdb_ids` and `check_posters` by hand (see the README).

## Rolling back

Deploy an earlier digest by hand on the server:

```bash
cd /srv/moviechooser
# Find the digest for a commit: docker buildx imagetools inspect ghcr.io/mattyocode/mattyocode/moviechooser-api:sha-<7 chars>
sh deploy.sh api ghcr.io/mattyocode/mattyocode/moviechooser-api@sha256:<digest>
```

**Migrations aren't reversed.** An automatic or manual rollback runs the old code against the new schema, which works for additive migrations (new tables or nullable columns) but not for renames or drops. Write migrations that the previous release can live with, or reverse them by hand first with `manage.py migrate <app> <migration>`.

## Useful commands

```bash
cd /srv/moviechooser
docker compose ps
docker compose logs -f --tail 100 api
docker compose exec api python manage.py <command>
grep _IMAGE .env          # what's deployed
```
