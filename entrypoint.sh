#!/bin/bash
set -e

if [ ! -f "migrations/env.py" ]; then
    rm -rf migrations
    flask db init
    flask db migrate -m "initial"
fi

# Try normal upgrade; on revision mismatch (container rebuilt), purge and re-stamp
flask db upgrade 2>/dev/null || {
    echo "Migration mismatch — purging stale revision and stamping head"
    flask db stamp --purge head
}

python seed.py

exec gunicorn main:app --bind 0.0.0.0:8000 --workers 2 --timeout 180
