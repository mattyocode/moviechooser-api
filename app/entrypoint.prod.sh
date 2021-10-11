#!/bin/sh

if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for postgres..."

    while ! nc -z $SQL_HOST $SQL_PORT; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi

mkdir /logs
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --forwarded-allow-ips="18.168.29.188,172.26.14.23" \
--workers 3 --capture-output --access-logfile /logs/gunicorn-access.log

exec "$@"