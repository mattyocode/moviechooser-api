#!/bin/sh
set -e
exec gunicorn -c config/gunicorn.py config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --forwarded-allow-ips="*" \
  --workers 2 --threads 8 --timeout 300 \
  --access-logfile - --error-logfile - --capture-output
