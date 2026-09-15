"""
Re-compress every uploaded image in MEDIA_ROOT with Pillow (Phase 10).

- JPEGs: resized to MAX_DIMENSION, quality 82, progressive, EXIF orientation applied
- PNGs: re-saved optimised (converted to JPEG only with --png-to-jpg, which
  rewrites referencing records — not done by default)

Idempotent: already-small images are left alone. Run after seeding or a big upload:
    python manage.py optimize_images [--max-dimension 1400] [--quality 82] [--dry-run]
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from PIL import Image, ImageOps

JPEG_EXT = {'.jpg', '.jpeg'}
PNG_EXT = {'.png'}


class Command(BaseCommand):
    help = 'Compress and resize uploaded images in MEDIA_ROOT.'

    def add_arguments(self, parser):
        parser.add_argument('--max-dimension', type=int, default=1400)
        parser.add_argument('--quality', type=int, default=82)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        max_dim = options['max_dimension']
        quality = options['quality']
        dry = options['dry_run']

        root = Path(settings.MEDIA_ROOT)
        if not root.exists():
            self.stdout.write('No media directory — nothing to do.')
            return

        saved_total = 0
        touched = 0
        for path in sorted(root.rglob('*')):
            if not path.is_file() or path.suffix.lower() not in JPEG_EXT | PNG_EXT:
                continue
            before = path.stat().st_size
            try:
                with Image.open(path) as img:
                    img = ImageOps.exif_transpose(img)
                    changed = False
                    if max(img.size) > max_dim:
                        img.thumbnail((max_dim, max_dim), Image.LANCZOS)
                        changed = True

                    if path.suffix.lower() in JPEG_EXT:
                        if img.mode in ('RGBA', 'P', 'LA'):
                            img = img.convert('RGB')
                        buf_kwargs = dict(format='JPEG', quality=quality,
                                          optimize=True, progressive=True)
                    else:
                        buf_kwargs = dict(format='PNG', optimize=True)

                    if not changed and before < 150_000:
                        continue  # already lean

                    if dry:
                        self.stdout.write(f'[dry-run] would optimize {path} ({before} bytes)')
                        continue

                    import io
                    buf = io.BytesIO()
                    img.save(buf, **buf_kwargs)
                    data = buf.getvalue()
                    if len(data) < before:
                        path.write_bytes(data)
                        saved = before - len(data)
                        saved_total += saved
                        touched += 1
                        self.stdout.write(
                            f'{path.relative_to(root)}: {before:,} → {len(data):,} '
                            f'(−{saved * 100 // before}%)')
            except Exception as exc:  # unreadable / truncated files
                self.stderr.write(f'skipping {path}: {exc}')

        self.stdout.write(self.style.SUCCESS(
            f'\n✔ Optimized {touched} image(s), saved {saved_total / 1024:.1f} KB.'
            + (' (dry run — nothing written)' if dry else '')))
