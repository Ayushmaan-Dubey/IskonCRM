"""Weekly import of NEW Google Form responses into the database.

Two published Google Sheets (form responses) are read as CSV:
  * "Sponsors"                         -> Sponsorship rows (+ a Person tagged "donator")
  * "Interested in Bhakti Sangha"      -> GuestIntake rows (+ a Person tagged "visitor")

Only rows submitted since the previous sync are imported, and never anything older than
seven days. Every sheet keeps a watermark in the database. It is created the first time the
app starts with this code, so nothing already in a sheet at that point is ever imported.

A scheduler (GitHub Actions, see .github/workflows/weekly-sheet-sync.yml) calls
POST /internal/sync-sheets with a bearer token, Sundays at 11 PM Central.
"""
import csv
import hashlib
import hmac
import io
import json
import os
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from . import db
from .audit import log_event
from .models import GuestIntake, Person, Sponsorship, User
from .utils import format_phone

# The Google Forms store timestamps in the spreadsheet's time zone; this is the temple's.
SHEET_TZ = ZoneInfo('America/Chicago')
MAX_LOOKBACK = timedelta(days=7)
MDY_FORMATS = ('%m/%d/%Y %H:%M:%S', '%m/%d/%Y %H:%M', '%m/%d/%Y')
DMY_FORMATS = ('%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M', '%d/%m/%Y')


class SheetSyncState(db.Model):
    """Per-sheet watermark: only responses submitted after this moment (UTC) are imported."""
    sheet_key = db.Column(db.String(50), primary_key=True)
    watermark = db.Column(db.DateTime, nullable=False)  # naive UTC
    last_run_at = db.Column(db.DateTime, nullable=True)
    last_result = db.Column(db.Text, nullable=True)


class SheetSyncedRow(db.Model):
    """Fingerprints of imported rows, so a retried run can never insert the same row twice."""
    id = db.Column(db.Integer, primary_key=True)
    sheet_key = db.Column(db.String(50), nullable=False, index=True)
    row_hash = db.Column(db.String(64), nullable=False, unique=True)
    imported_at = db.Column(db.DateTime, default=func.now(), nullable=False)


# ── Reading the sheets ───────────────────────────────────────────────────────

def _fetch_rows(sheet_id, gid):
    url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}'
    request_ = urllib.request.Request(url, headers={'User-Agent': 'temple-crm-sheet-sync'})
    with urllib.request.urlopen(request_, timeout=30) as resp:
        content_type = resp.headers.get('Content-Type', '')
        body = resp.read().decode('utf-8-sig')
    if 'csv' not in content_type:
        raise RuntimeError('sheet is not readable: set sharing to "Anyone with the link can view"')
    return list(csv.DictReader(io.StringIO(body)))


def _parse_timestamp(text, dayfirst=False):
    """Sheet timestamp -> naive UTC datetime, or None if it can't be read."""
    text = (text or '').strip()
    for fmt in (DMY_FORMATS if dayfirst else MDY_FORMATS):
        try:
            local = datetime.strptime(text, fmt).replace(tzinfo=SHEET_TZ)
            return local.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            continue
    return None


def _raw_timestamp(row):
    """The submission time as written in the sheet. Some sheets have lost the 'Timestamp'
    header (the Bhakti Sangha one calls it 'x'), so fall back to the first column."""
    value = _pick(row, 'timestamp')
    if value:
        return value
    first = next(iter(row.values()), '')
    return (first or '').strip()


def _pick(row, *keywords, exclude=()):
    """Value of the first column whose header contains any keyword (case-insensitive)."""
    for header, value in row.items():
        name = (header or '').strip().lower()
        if any(k in name for k in keywords) and not any(x in name for x in exclude):
            return (value or '').strip()
    return ''


def _parse_date(text):
    for fmt in ('%m/%d/%Y', '%m/%d/%y'):
        try:
            return datetime.strptime((text or '').strip(), fmt).date()
        except ValueError:
            continue
    return None


def _row_hash(sheet_key, row):
    raw = '|'.join([sheet_key, _raw_timestamp(row), _pick(row, 'full name', 'name'), _pick(row, 'email'),
                    _pick(row, 'contact', 'phone', 'mobile', 'whatsapp')])
    return hashlib.sha256(raw.lower().encode()).hexdigest()


def _import_user_id():
    """Imported newcomers need an owner; use the earliest super admin (else any admin)."""
    user = User.query.filter_by(role='super_admin').order_by(User.id).first() \
        or User.query.filter_by(role='admins').order_by(User.id).first()
    if user is None:
        raise RuntimeError('no admin user exists to attribute imported records to')
    return user.id


# ── Skipping people who are already in the database ──────────────────────────

def _duplicate_reason(key, row):
    """Why this row should NOT be imported, or None if it should."""
    if key == 'bhakti_sangha':
        if _pick(row, 'added to temple crm'):
            return 'marked_added_in_sheet'
        phone = format_phone(_pick(row, 'contact', 'phone', 'mobile', 'whatsapp'))
        if phone and GuestIntake.query.filter_by(phone_number=phone).first():
            return 'already_in_database'
    elif key == 'sponsors':
        email = _pick(row, 'email').lower()
        date = _parse_date(_pick(row, 'sponsoring date'))
        amount = re.search(r'\d[\d,]*(?:\.\d+)?', _pick(row, 'amount'))
        amount = amount.group(0).replace(',', '') if amount else None
        if email:
            for existing in Sponsorship.query.filter(func.lower(Sponsorship.sponsor_email) == email,
                                                     Sponsorship.sponsorship_date == date,
                                                     Sponsorship.donation_amount == amount):
                return 'already_in_database'
    return None


# ── Row -> database record ───────────────────────────────────────────────────

def _import_sponsor(row, submitted_utc):
    from .views import _find_or_create_person

    name = _pick(row, 'full name', 'name')
    if not name:
        return None
    email = _pick(row, 'email') or None
    phone = format_phone(_pick(row, 'contact', 'phone')) or None
    amount_text = _pick(row, 'amount')
    amount = re.search(r'\d[\d,]*(?:\.\d+)?', amount_text)
    payment_option = _pick(row, 'payment options')
    payment_details = _pick(row, 'payment details', exclude=('upload',))
    upload = _pick(row, 'upload')
    submitted_local = submitted_utc.replace(tzinfo=timezone.utc).astimezone(SHEET_TZ)

    notes = [f'Imported from the Sponsorship Google Form (submitted {submitted_local:%m/%d/%Y %I:%M %p}).']
    if _pick(row, 'sponsorship details'):
        notes.append(f"Details: {_pick(row, 'sponsorship details')}")
    if amount_text and (not amount or amount.group(0) != amount_text.strip()):
        notes.append(f'Amount as entered: {amount_text}')
    if payment_option:
        notes.append(f'Payment option: {payment_option}')
    if payment_details:
        notes.append(f'Payment details: {payment_details}')
    if upload:
        notes.append(f'Payment file: {upload}')

    record = Sponsorship(
        sponsor_legal_name=name[:200],
        sponsor_phone_number=phone,
        sponsor_email=email,
        sponsorship_date=_parse_date(_pick(row, 'sponsoring date')),
        donation_amount=amount.group(0).replace(',', '') if amount else None,
        payment_methods=(payment_option.split(':')[0].strip()[:200] or None),
        notes='\n'.join(notes),
        not_yet_paid=False,
        source='sheet',
        created_at=submitted_utc.replace(tzinfo=timezone.utc),
    )
    db.session.add(record)
    db.session.flush()
    person = _find_or_create_person(name, email, phone)
    person.add_tag('donator')
    record.person_id = person.id
    return record


def _import_bhakti(row, submitted_utc):
    from .views import AREA_OPTIONS, _create_guest_intake_record

    name = _pick(row, 'full name', 'name')
    if not name:
        return None
    email = _pick(row, 'email') or None
    phone = format_phone(_pick(row, 'contact', 'phone', 'mobile', 'whatsapp')) or None
    lives = _pick(row, 'where do you live')
    interested = _pick(row, 'interested in')
    submitted_local = submitted_utc.replace(tzinfo=timezone.utc).astimezone(SHEET_TZ)

    notes = [f'Imported from the "Interested in Bhakti Sangha" form ({submitted_local:%m/%d/%Y %I:%M %p}).']
    if interested:
        notes.append(f'Interested in: {interested}')

    record = _create_guest_intake_record(
        name[:200], phone, email, '\n'.join(notes), False, '', [], '',
        [lives] if lives in AREA_OPTIONS else [], '' if lives in AREA_OPTIONS else lives[:200],
        'seva' in interested.lower(), False, _import_user_id(),
    )
    record.created_at = submitted_utc.replace(tzinfo=timezone.utc)
    return record


SHEETS = {
    'sponsors': {
        'label': 'Sponsors',
        'sheet_id': os.environ.get('SPONSORS_SHEET_ID', '17cdqF4OsRv2laZ3EQRvv6cqSXp9kQoqp62XklpztJ4Y'),
        'gid': os.environ.get('SPONSORS_SHEET_GID', '906065027'),
        'dayfirst': False,   # 11/1/2026 = November 1
        'handler': _import_sponsor,
    },
    'bhakti_sangha': {
        'label': 'Interested in Bhakti Sangha',
        'sheet_id': os.environ.get('BHAKTI_SHEET_ID', '1NcmiI87tY16grE6hnxoIJCJWPxFjjJjZf0AXEM3LX6U'),
        'gid': os.environ.get('BHAKTI_SHEET_GID', '143134962'),
        'dayfirst': True,    # 13/11/2026 = November 13 (this sheet is day-first)
        'handler': _import_bhakti,
    },
}


# ── Sync logic ───────────────────────────────────────────────────────────────

def ensure_baseline(now=None):
    """Called at app start: a sheet with no watermark gets one set to *now*, so rows already
    in the sheet are never imported, only responses submitted from here on."""
    now = now or datetime.utcnow()
    for key in SHEETS:
        if db.session.get(SheetSyncState, key) is None:
            db.session.add(SheetSyncState(sheet_key=key, watermark=now))
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


def _sync_one(key, cfg, now, backfill=False, apply=True):
    """Import one sheet. Weekly mode takes rows newer than the watermark (max 7 days back);
    backfill mode takes every row once. apply=False only counts, and writes nothing."""
    state = db.session.get(SheetSyncState, key)
    if state is None and not backfill:
        db.session.add(SheetSyncState(sheet_key=key, watermark=now))
        db.session.commit()
        return {'baseline_set': True, 'imported': 0}

    window_start = datetime.min if backfill else max(state.watermark, now - MAX_LOOKBACK)
    counts = {'imported': 0, 'already_imported': 0, 'outside_window': 0,
              'skipped_incomplete': 0, 'no_timestamp': 0, 'already_in_database': 0,
              'marked_added_in_sheet': 0}
    for row in _fetch_rows(cfg['sheet_id'], cfg['gid']):
        submitted = _parse_timestamp(_raw_timestamp(row), cfg['dayfirst'])
        if submitted is None:
            counts['no_timestamp'] += 1
            continue
        if submitted <= window_start or submitted > now:
            counts['outside_window'] += 1
            continue
        fingerprint = _row_hash(key, row)
        if SheetSyncedRow.query.filter_by(row_hash=fingerprint).first():
            counts['already_imported'] += 1
            continue
        reason = _duplicate_reason(key, row)
        if reason:
            counts[reason] += 1
            if apply:  # remember it, so no later run ever reconsiders this row
                db.session.add(SheetSyncedRow(sheet_key=key, row_hash=fingerprint))
            continue
        if not (_pick(row, 'full name', 'name')):
            counts['skipped_incomplete'] += 1
            continue
        if apply:
            cfg['handler'](row, submitted)
            db.session.add(SheetSyncedRow(sheet_key=key, row_hash=fingerprint))
        counts['imported'] += 1

    if not apply:
        db.session.rollback()
        return counts
    if state is None:
        state = SheetSyncState(sheet_key=key, watermark=now)
        db.session.add(state)
    state.watermark = now          # advance only when everything above succeeded
    state.last_run_at = now
    state.last_result = json.dumps(counts)
    db.session.commit()
    return counts


def sync_all(now=None, backfill=False, apply=True):
    now = now or datetime.utcnow()
    summary = {}
    for key, cfg in SHEETS.items():
        try:
            summary[key] = _sync_one(key, cfg, now, backfill=backfill, apply=apply)
        except Exception as exc:  # one bad sheet must not block the other
            db.session.rollback()
            summary[key] = {'error': f'{type(exc).__name__}: {str(exc)[:200]}'}
    return summary


def in_sunday_night_window(now_utc):
    """Sunday 11 PM - Monday 1 AM Central. Lets the scheduler fire at two UTC times
    (covering daylight saving) while the sync still effectively happens once."""
    local = now_utc.replace(tzinfo=timezone.utc).astimezone(SHEET_TZ)
    return (local.weekday() == 6 and local.hour >= 23) or (local.weekday() == 0 and local.hour < 1)


# ── HTTP trigger for the scheduler ───────────────────────────────────────────

sheet_sync = Blueprint('sheet_sync', __name__)


@sheet_sync.route('/internal/sync-sheets', methods=['POST'])
def run_sync():
    expected = os.environ.get('SYNC_TOKEN', '')
    supplied = request.headers.get('Authorization', '').removeprefix('Bearer ').strip()
    if not expected:
        return jsonify(error='Sheet sync is not configured.'), 503
    if not hmac.compare_digest(expected.encode(), supplied.encode()):
        return jsonify(error='Unauthorized.'), 401

    now = datetime.utcnow()
    if request.args.get('scheduled') == '1' and not in_sunday_night_window(now):
        return jsonify(skipped='Outside the Sunday 11 PM Central window.')

    # One-time catch-up: ?backfill=1 imports everything currently in the sheets (skipping people
    # already in the database); add &dry_run=1 to only count. Without it, the normal weekly mode.
    backfill = request.args.get('backfill') == '1'
    dry_run = request.args.get('dry_run') == '1'
    summary = sync_all(now, backfill=backfill, apply=not dry_run)
    if not dry_run:
        mode = 'Backfill' if backfill else 'Weekly'
        log_event('admin_action', f'{mode} sheet sync: {json.dumps(summary)}')
    return jsonify(summary)
