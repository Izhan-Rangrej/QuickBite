"""
Build minified copies of the project's CSS/JS into static/dist/ (Phase 10).

In production `{% static_min %}` serves `static/dist/css/style.css` etc.;
in DEBUG the readable originals are used. Run before `collectstatic` in
deployment (the Render build command already chains it):

    python manage.py minify_static
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

import rcssmin
import rjsmin


class Command(BaseCommand):
    help = 'Minify project CSS/JS into static/dist/ (rcssmin / rjsmin).'

    def handle(self, *args, **options):
        src_root = Path(settings.BASE_DIR) / 'static'
        dst_root = src_root / 'dist'

        count = 0
        for path in sorted(src_root.rglob('*')):
            if not path.is_file() or dst_root in path.parents:
                continue
            rel = path.relative_to(src_root)
            if '.min.' in path.name:  # chart.umd.min.js etc. — already minified
                continue

            if path.suffix == '.css':
                out = rcssmin.cssmin(path.read_text(), keep_bang_comments=False)
            elif path.suffix == '.js':
                out = rjsmin.jsmin(path.read_text(), keep_bang_comments=False)
            else:
                continue

            dst = dst_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(out)
            before, after = path.stat().st_size, dst.stat().st_size
            self.stdout.write(f'{rel}: {before:,} → {after:,} bytes')
            count += 1

        self.stdout.write(self.style.SUCCESS(f'\n✔ Minified {count} file(s) into {dst_root}.'))
