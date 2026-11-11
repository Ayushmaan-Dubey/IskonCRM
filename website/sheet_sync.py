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
TIMESTAMP_FORMATS = ('%m/%d/%Y %H:%M:%S', '%m/%d/%Y %H:%M', '%m/%d/%Y')


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


def _parse_timestamp(text):
    """Sheet timestamp -> naive UTC datetime, or None if it can't be read."""
    text = (text or '').strip()
    for fmt in TIMESTAMP_FORMATS:
        try:
            local = datetime.strptime(text, fmt).replace(tzinfo=SHEET_TZ)
            return local.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            continue
    return None


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
    stamp = _pick(row, 'timestamp')
    raw = '|'.join([sheet_key, stamp, _pick(row, 'full name', 'name'), _pick(row, 'email'),
                    _pick(row, 'contact', 'phone', 'mobile', 'whatsapp')])
    return hashlib.sha256(raw.lower().encode()).hexdigest()


def _import_user_id():
    """Imported newcomers need an owner; use the earliest super admin (else any admin)."""
    user = User.query.filter_by(role='super_admin').order_by(User.id).first() \
        or User.query.filter_by(role='admins').order_by(User.id).first()
    if user is None:
        raise RuntimeError('no admin user exists to attribute imported records to')
    return user.id


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
    from .views import _create_guest_intake_record

    name = _pick(row, 'full name', 'name')
    if not name:
        return None
    email = _pick(row, 'email') or None
    phone = format_phone(_pick(row, 'contact', 'phone', 'mobile', 'whatsapp')) or None
    submitted_local = submitted_utc.replace(tzinfo=timezone.utc).astimezone(SHEET_TZ)

    # Keep every other answer so nothing from the form is lost, without guessing its meaning.
    answered = [f'{h.strip()}: {v.strip()}' for h, v in row.items()
                if h and v and v.strip() and 'timestamp' not in h.lower()
                and v.strip() not in (name, email or '', _pick(row, 'contact', 'phone', 'mobile', 'whatsapp'))]
    notes = f'Imported from "Interested in Bhakti Sangha" form ({submitted_local:%m/%d/%Y %I:%M %p}).'
    if answered:
        notes += '\n' + '\n'.join(answered)

    record = _create_guest_intake_record(
        name[:200], phone, email, notes, False, '', [], '', [], '', False, False, _import_user_id(),
    )
    record.created_at = submitted_utc.replace(tzinfo=timezone.utc)
    return record


SHEETS = {
    'sponsors': {
        'label': 'Sponsors',
        'sheet_id': os.environ.get('SPONSORS_SHEET_ID', '17cdqF4OsRv2laZ3EQRvv6cqSXp9kQoqp62XklpztJ4Y'),
        'gid': os.environ.get('SPONSORS_SHEET_GID', '906065027'),
        'handler': _import_sponsor,
    },
    'bhakti_sangha': {
        'label': 'Interested in Bhakti Sangha',
        'sheet_id': os.environ.get('BHAKTI_SHEET_ID', '1NcmiI87tY16grE6hnxoIJCJWPxFjjJjZf0AXEM3LX6U'),
        'gid': os.environ.get('BHAKTI_SHEET_GID', '143134962'),
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


def _sync_one(key, cfg, now):
    state = db.session.get(SheetSyncState, key)
    if state is None:
        db.session.add(SheetSyncState(sheet_key=key, watermark=now))
        db.session.commit()
        return {'baseline_set': True, 'imported': 0}

    window_start = max(state.watermark, now - MAX_LOOKBACK)
    imported = already = too_old = no_timestamp = skipped = 0
    for row in _fetch_rows(cfg['sheet_id'], cfg['gid']):
        submitted = _parse_timestamp(_pick(row, 'timestamp'))
        if submitted is None:
            no_timestamp += 1
            continue
        if submitted <= window_start or submitted > now:
            too_old += 1
            continue
        fingerprint = _row_hash(key, row)
        if SheetSyncedRow.query.filter_by(row_hash=fingerprint).first():
            already += 1
            continue
        if cfg['handler'](row, submitted) is None:
            skipped += 1
            continue
        db.session.add(SheetSyncedRow(sheet_key=key, row_hash=fingerprint))
        imported += 1

    result = {'imported': imported, 'already_imported': already, 'outside_window': too_old,
              'skipped_incomplete': skipped, 'no_timestamp': no_timestamp}
    state.watermark = now          # advance only when everything above succeeded
    state.last_run_at = now
    state.last_result = json.dumps(result)
    db.session.commit()
    return result


def sync_all(now=None):
    now = now or datetime.utcnow()
    summary = {}
    for key, cfg in SHEETS.items():
        try:
            summary[key] = _sync_one(key, cfg, now)
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

    summary = sync_all(now)
    log_event('admin_action', f'Weekly sheet sync: {json.dumps(summary)}')
    return jsonify(summary)
