#!/bin/sh

if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for postgres..."

    while ! nc -z $SQL_HOST $SQL_PORT; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi

# mkdir /log
# # List of files to create if they don't exist
# files=("/log/debug.log" "/log/error.log" "/log/info.log")

# # Loop through the list and create each file if it doesn't exist
# for file in "${files[@]}"; do
#   if [[ ! -f "$file" ]]; then
#     touch "$file"
#     echo "Created $file"
#   else
#     echo "$file already exists"
#   fi
# done

python manage.py migrate
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --forwarded-allow-ips="18.168.29.188,172.26.14.23" \
--workers 4 --threads 4 --capture-output --access-logfile /logs/gunicorn-access.log --timeout 300

exec "$@"