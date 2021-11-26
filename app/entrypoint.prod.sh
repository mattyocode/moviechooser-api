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
python manage.py migrate
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --forwarded-allow-ips="18.168.29.188,172.26.14.23" \
--workers 4 --threads 4 --capture-output --access-logfile /logs/gunicorn-access.log --timeout 300

exec "$@"