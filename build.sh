#!/usr/bin/env bash
# Render build script (buildCommand in render.yaml).
#
# Everything here runs on Render's *build* container, and its output directory
# (/opt/render/project/src) is exactly what gets deployed — which is why the
# media restore below belongs here rather than in a run-time hook.
#
# Note: Render's `preDeployCommand` is paid-only, and its filesystem changes are
# discarded, so migrations stay in the build (safe: they're additive + idempotent).
set -o errexit
set -o pipefail

python --version
pip install --upgrade pip
pip install -r requirements.txt

# Fail the build early with a readable message instead of at request time.
python manage.py check

python manage.py minify_static          # build static/dist/*.{css,js}
python manage.py collectstatic --noinput

# Neon is reachable from the build container, so schema + sample content are ready
# before the app starts serving.
python manage.py migrate --noinput

if [ "${QUICKBITE_SEED_ON_BUILD:-False}" = "True" ]; then
  echo "[build] seeding sample data (set QUICKBITE_SEED_ON_BUILD=False to skip)"
  python manage.py seed_data || echo "[build] seed_data skipped/failed — continuing"
fi

# media/ is git-ignored and Render's disk is ephemeral, so re-materialise the
# bundled photos the database points at. Never fatal.
python manage.py restore_seed_media || echo "[build] restore_seed_media skipped — continuing"

echo "[build] done"
