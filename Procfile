# Heroku/Railway-style process declaration.
# Render ignores this file — render.yaml's startCommand wins — but keep the two in
# sync. Schema changes run during the build (./build.sh), not at process start.
web: gunicorn quickbite.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 60
