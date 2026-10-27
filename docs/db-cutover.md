# Database cutover: Lightsail managed DB → `pgvector/pgvector:pg16` container

Use this runbook to move the prod (or staging) database off the separate Lightsail database and into the `mc-prod-db` (or `mc-staging-db`) service defined in `docker-compose.prod.yml` (or `docker-compose.staging.yml`). Do staging first.

The commands below use prod names. For staging, use `docker-compose.staging.yml`, `mc-staging-db`, `.env.staging` and `.env.staging.db`.

```bash
dc="docker compose -f docker-compose.prod.yml"
```

## 0. Before the maintenance window

1. **Check headroom on the instance.** Postgres will share it with gunicorn, nginx-proxy and acme-companion.

   ```bash
   free -h
   df -h /var/lib/docker
   ```

   You need room for the database plus its dump, and a few hundred MB of free RAM. If there is not enough, stay on the managed DB.

2. **Check the deploy script.** `~/.scripts/docker-deploy.sh` must bring up every service in `docker-compose.prod.yml`, for example `docker compose -f docker-compose.prod.yml up -d --build`. If it starts only named services, add `mc-prod-db`, or rely on `depends_on`, which starts it with `djangogunicorn`.

3. **Check the source DB version.** Connect to the Lightsail DB and run:

   ```sql
   SELECT version();
   ```

   If it is **newer than PostgreSQL 16**, stop. A dump from a newer server does not reliably restore into PG16.

4. **Create `app/.env.prod.db`** from `app/.env.db.example`, filling in `POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB`. Use the same values that `.env.prod` will use for `SQL_USER`, `SQL_PASSWORD` and `SQL_DATABASE`. This file is gitignored.

## 1. Stop writes

```bash
$dc stop djangogunicorn
```

Also stop any celery worker that writes to the DB.

## 2. Start the new database

```bash
$dc up -d mc-prod-db
docker inspect -f '{{.State.Health.Status}}' "$($dc ps -q mc-prod-db)"   # wait for "healthy"
```

## 3. Dump the Lightsail DB using the PG16 client

```bash
$dc exec mc-prod-db sh -c \
  'PGPASSWORD="<lightsail-password>" pg_dump -h <lightsail-endpoint> -p 5432 -U <lightsail-user> -d <lightsail-db> -Fc -f /tmp/lightsail.dump'
```

## 4. Restore into the container

```bash
$dc exec mc-prod-db sh -c \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges /tmp/lightsail.dump'
```

`--no-owner --no-privileges` drops the owners and grants that belong to the managed DB's own roles.

## 5. Compare row counts

Run this against **both** the Lightsail DB and `mc-prod-db`. The results must match.

```sql
SELECT 'movies_movie', count(*) FROM movies_movie
UNION ALL SELECT 'accounts_customuser', count(*) FROM accounts_customuser
UNION ALL SELECT 'lists_list', count(*) FROM lists_list
UNION ALL SELECT 'lists_item', count(*) FROM lists_item;
```

Optionally, confirm pgvector is available. Phase 2 enables it, not this runbook.

```sql
SELECT name, default_version FROM pg_available_extensions WHERE name = 'vector';
```

## 6. Point the app at the container and deploy

In `app/.env.prod`, set:

```
SQL_HOST=mc-prod-db
SQL_PORT=5432
```

Then run the normal deploy (`sh ~/.scripts/docker-deploy.sh`) or `$dc up -d --build`. Check that `djangogunicorn` starts after `mc-prod-db` is healthy, that its logs show migrations with nothing to apply, and that the API responds.

## 7. Rollback window

Leave the Lightsail DB running but unused for a short window, such as a few days.

**Rollback:** set `SQL_HOST` and `SQL_PORT` in `app/.env.prod` back to the Lightsail endpoint, check out the previous `docker-compose.prod.yml`, and redeploy. **Any writes made after cutover are lost** unless you copy them back by hand, so keep the window short.

When the window closes, take a final snapshot of the Lightsail DB and delete it.

## Backups

The managed DB's automatic backups no longer apply. Back up manually (or from cron) with:

```bash
$dc exec -T mc-prod-db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  > ~/backups/mc_prod_$(date +%F).dump
```

Copy the backups off the instance, for example to S3. Scheduled backups are not set up yet.
