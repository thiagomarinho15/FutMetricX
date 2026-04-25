#!/bin/bash
set -e

if [ ! -f "migrations/env.py" ]; then
    flask db init
    flask db migrate -m "initial"
fi

flask db upgrade
python seed.py

exec gunicorn main:app --bind 0.0.0.0:8000 --workers 2 --timeout 180
