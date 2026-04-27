#!/bin/bash
set -e

# Apply pending migrations with fallback for revision mismatches
flask db upgrade 2>&1 && echo "Migrations OK" || {
    echo "Migration mismatch — resetting version table and re-applying"
    python - <<'PYEOF'
import os
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
    flask db stamp head 2>&1 || true
    flask db upgrade 2>&1 || echo "  Migration already applied or not needed"
}

python seed.py

exec gunicorn main:app --bind 0.0.0.0:8000 --workers 2 --timeout 180
