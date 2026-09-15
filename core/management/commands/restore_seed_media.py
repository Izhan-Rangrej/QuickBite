"""Re-copy bundled seed images into MEDIA_ROOT whenever the files are missing.

Why this exists
---------------
Render's filesystem is **ephemeral**: everything outside a mounted disk is reset
to the build output on every deploy, and free instances also restart frequently.
MEDIA_ROOT (``media/``) is git-ignored, so after a deploy the database still says
``image = dishes/margherita.jpg`` while the file is gone → every dish and
restaurant photo renders as a broken image.

``seed_data`` can't fix that: it skips images for rows that already have one.
This command works the other way round — it walks the *files* the database
references and restores any that are missing from the git-tracked copies in
``static/images/seed/`` (falling back to the un-suffixed name when Django's
storage added a random suffix on upload).

Usage::

    python manage.py restore_seed_media            # copy what's missing
    python manage.py restore_seed_media --report   # just count, change nothing
    python manage.py restore_seed_media --dry-run  # print what would be copied

It never fails the build: with an empty database (or no tables yet) it does
nothing, since real deployments should keep uploads on a disk or object storage.
"""

import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

SEED_DIR = Path(settings.BASE_DIR) / 'static' / 'images' / 'seed'

# (model label, image field) pairs whose files live under MEDIA_ROOT.
IMAGE_FIELDS = [
    ('core.Category', 'image'),
    ('core.Restaurant', 'image'),
    ('core.Dish', 'image'),
]

# Order snapshots keep their own copy of the dish path, so old receipts show art too.
SNAPSHOT_FIELDS = [
    ('orders.OrderItem', 'dish_image'),
]


def _candidate_names(rel_path):
    """The stored name plus its un-suffixed form (``x_a1b2c3d.jpg`` → ``x.jpg``)."""
    name = Path(rel_path).name
    yield name
    stem, dot, ext = name.rpartition('.')
    if '_' in stem:
        head, _, tail = stem.rpartition('_')
        if head and len(tail) == 7 and tail.isalnum():
            yield f'{head}{dot}{ext}'


class Command(BaseCommand):
    help = 'Restore missing seed images into MEDIA_ROOT from static/images/seed/.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Report what would be copied without writing files')
        parser.add_argument('--report', action='store_true',
                            help='Only count missing files; copy nothing')

    def _paths_from(self, model_label, field):
        """Relative media paths recorded for one model/field (quiet on an unmigrated DB)."""
        from django.apps import apps
        from django.db import OperationalError, ProgrammingError

        try:
            model = apps.get_model(model_label)
            rows = list(model.objects.exclude(**{field: ''}).values_list(field, flat=True))
        except LookupError:
            return
        except (OperationalError, ProgrammingError) as exc:   # tables not created yet
            self.stdout.write(self.style.WARNING(f'  skipping {model_label}: {str(exc)[:120]}'))
            return
        for value in rows:
            if value:
                yield str(value)

    def handle(self, *args, **options):
        dry_run, report_only = options['dry_run'], options['report']
        media_root = Path(settings.MEDIA_ROOT)

        if not SEED_DIR.is_dir():
            self.stdout.write(self.style.WARNING(f'No seed image directory at {SEED_DIR}; nothing to do.'))
            return

        wanted = set()
        for label, field in IMAGE_FIELDS + SNAPSHOT_FIELDS:
            wanted.update(self._paths_from(label, field))   # restore to the stored path
        wanted = sorted(wanted)

        missing = [rel for rel in wanted if not (media_root / rel).is_file()]
        self.stdout.write(f'Media files referenced by the database: {len(wanted)}; missing: {len(missing)}')

        restored, unavailable = 0, 0
        for rel in missing:
            for name in _candidate_names(rel):
                src = SEED_DIR / name
                if src.is_file():
                    dest = media_root / rel
                    if not dry_run and not report_only:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(src, dest)
                    restored += 1
                    self.stdout.write(f'  restored {rel}  (from static/images/seed/{name})')
                    break
            else:
                unavailable += 1
                self.stdout.write(self.style.WARNING(f'  no bundled copy for {rel} — needs a disk or object storage'))

        verb = 'Would restore' if dry_run else ('Missing' if report_only else 'Restored')
        self.stdout.write(self.style.SUCCESS(
            f'{verb} {restored} file(s); {unavailable} unavailable; '
            f'{len(wanted) - len(missing)} already present.'
        ))
        if not wanted:
            self.stdout.write(self.style.NOTICE(
                'Nothing referenced yet — run `python manage.py seed_data` first.'
            ))
