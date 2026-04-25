#!/bin/bash
set -e

flask db upgrade
python seed.py

exec gunicorn main:app --bind 0.0.0.0:8000 --workers 2 --timeout 180
