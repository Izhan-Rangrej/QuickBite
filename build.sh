#!/usr/bin/env bash
# Render build script — installs deps and prepares static assets.
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt gunicorn==23.0.0

python manage.py minify_static     # build static/dist/*.{css,js}
python manage.py collectstatic --noinput
python manage.py migrate --noinput
