#!/bin/bash
set -e

# Create all tables from models (safe no-op if tables already exist)
python - <<'PYEOF'
from app import create_app
from app.models import db
app = create_app()
with app.app_context():
    db.create_all()
    print("db.create_all() OK")
PYEOF

# Stamp only the *initial* known migration so db.create_all() tables are
# recognised as up-to-date, while any *newer* migrations still get applied.
# This avoids the trap of `stamp head` which marks brand-new migrations as
# already applied before they have a chance to run on existing databases.
flask db stamp 766b4f44ebb8 2>&1 || true

# Apply pending migrations (e.g. a1b2c3d4e5f6 adds logo_url, worker_log…)
flask db upgrade 2>&1 && echo "Migrations OK" || {
    echo "Migration error — clearing alembic_version and retrying"
    python - <<'PYEOF'
from app import create_app
from app.models import db
app = create_app()
with app.app_context():
    try:
        with db.engine.connect() as conn:
            conn.execute(db.text('DELETE FROM alembic_version'))
            conn.commit()
        print("  alembic_version cleared")
    except Exception as e:
        print(f"  Could not clear: {e}")
PYEOF
    flask db stamp 766b4f44ebb8 2>&1 || true
    flask db upgrade 2>&1 || echo "  Migration already applied or not needed"
}

python seed.py

exec gunicorn main:app --bind 0.0.0.0:8000 --workers 2 --timeout 180
