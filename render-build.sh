#!/usr/bin/env bash
# render-build.sh - Render build script
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
