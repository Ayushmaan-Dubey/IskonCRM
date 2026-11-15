"""One-time import of EVERYTHING currently in the two Google response sheets.

  python backfill_sheets.py            # preview only: counts, writes nothing
  python backfill_sheets.py --apply    # actually import

Uses the same database as the app (DATABASE_URL, or the local SQLite file). People already
in the database, or rows marked "Added to temple CRM" in the sheet, are skipped. Afterwards
the weekly sync only ever takes responses submitted after this run.
"""
import json
import sys

try:
    from dotenv import load_dotenv
    load_dotenv('.env')
except ImportError:
    pass

from website import create_app, sheet_sync

apply_changes = '--apply' in sys.argv
app = create_app()
with app.app_context():
    summary = sheet_sync.sync_all(backfill=True, apply=apply_changes)
print(('IMPORTED' if apply_changes else 'PREVIEW (nothing written)') + ':')
print(json.dumps(summary, indent=2))
