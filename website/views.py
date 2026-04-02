import csv
import io
from datetime import datetime, timedelta

from flask import Blueprint, Response, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required
from sqlalchemy import desc

from . import db
from .models import GuestIntake, Sponsorship

views = Blueprint('views', __name__)

ROLE_LABELS = {
    'user': 'User',
    'sales': 'Sales',
    'sunday_school_teacher': 'Sunday School Teacher',
    'congregational_development': 'Congregational Development',
    'admins': 'Admin',
}

REFERRAL_OPTIONS = [
    'Drive by',
    'Social Media',
    'Book Rack',
    'Friends and Family',
    'Google',
    'Other',
]

AREA_OPTIONS = [
    'Round Rock',
    'Georgetown',
    'Leander',
    'Cedar Park',
    'Liberty Hill',
    'Pflugerville',
    'North Austin',
    'Downtown',
    'South Austin',
    'Other',
]

AMOUNT_OPTIONS = ['$301', '$151', '$51', 'Other']
PAYMENT_OPTIONS = ['Cash', 'Zelle', 'Card', 'Other']
WHATSAPP_OPTIONS = ['Yes', 'No', 'Already on it']


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None


def _admin_only():
    if not getattr(current_user, 'is_admin', False):
        flash('Reports are only available to admins.', 'warning')
        return False
    return True


@views.route('/')
@login_required
def home():
    now = datetime.utcnow()
    week_start = now - timedelta(days=7)
    upcoming_cutoff = now.date() + timedelta(days=30)

    my_guest_count = GuestIntake.query.filter_by(created_by_user_id=current_user.id).count()
    my_sponsorship_count = Sponsorship.query.filter_by(created_by_user_id=current_user.id).count()
    newcomers_this_week = GuestIntake.query.filter(GuestIntake.created_at >= week_start).count()
    upcoming_sponsorships = Sponsorship.query.filter(
        Sponsorship.sponsorship_date.isnot(None),
        Sponsorship.sponsorship_date >= now.date(),
        Sponsorship.sponsorship_date <= upcoming_cutoff,
    ).order_by(Sponsorship.sponsorship_date.asc()).limit(5).all()

    return render_template(
        'Home.HTML',
        user=current_user,
        role_labels=ROLE_LABELS,
        metrics={
            'my_guest_count': my_guest_count,
            'my_sponsorship_count': my_sponsorship_count,
            'newcomers_this_week': newcomers_this_week,
        },
        upcoming_sponsorships=upcoming_sponsorships,
    )


@views.route('/newcomers/new', methods=['GET', 'POST'])
@login_required
def guest_intake():
    if request.method == 'POST':
        form = request.form
        full_name = form.get('full_name', '').strip()
        phone_number = form.get('phone_number', '').strip()
        email = form.get('email', '').strip()
        notes = form.get('notes', '').strip()
        first_time_value = form.get('first_time_at_temple', 'no')
        whatsapp_status = form.get('whatsapp_status', '').strip()
        referral_sources = form.getlist('referral_sources')
        referral_other = form.get('referral_other', '').strip()
        residence_areas = form.getlist('residence_areas')
        residence_other = form.get('residence_other', '').strip()

        errors = []
        if not full_name:
            errors.append('Full name is required.')
        if not phone_number:
            errors.append('Phone number is required.')
        if not whatsapp_status:
            errors.append('Please select WhatsApp interest.')

        if errors:
            return render_template(
                'guest-intake.html',
                errors=errors,
                form=form,
                referral_options=REFERRAL_OPTIONS,
                area_options=AREA_OPTIONS,
                whatsapp_options=WHATSAPP_OPTIONS,
            )

        record = GuestIntake(
            full_name=full_name,
            phone_number=phone_number or None,
            email=email or None,
            notes=notes or None,
            first_time_at_temple=(first_time_value == 'yes'),
            whatsapp_status=whatsapp_status,
            referral_sources=', '.join(referral_sources) if referral_sources else None,
            referral_other=referral_other or None,
            residence_areas=', '.join(residence_areas) if residence_areas else None,
            residence_other=residence_other or None,
            created_by_user_id=current_user.id,
        )
        db.session.add(record)
        db.session.commit()

        flash('Guest intake saved successfully.', 'success')
        if form.get('submit_action') == 'save_add_another':
            return redirect(url_for('views.guest_intake'))
        return redirect(url_for('views.my_data'))

    return render_template(
        'guest-intake.html',
        referral_options=REFERRAL_OPTIONS,
        area_options=AREA_OPTIONS,
        whatsapp_options=WHATSAPP_OPTIONS,
    )


@views.route('/sponsorships/new', methods=['GET', 'POST'])
@login_required
def sponsorship():
    if request.method == 'POST':
        form = request.form
        sponsor_legal_name = form.get('sponsor_legal_name', '').strip()
        sponsor_spiritual_name = form.get('sponsor_spiritual_name', '').strip()
        sponsoring_for = form.get('sponsoring_for', '').strip()
        occasion = form.get('occasion', '').strip()
        sponsorship_date_raw = form.get('sponsorship_date', '').strip()
        sponsorship_date = _parse_date(sponsorship_date_raw)
        notes = form.get('notes', '').strip()
        amount_options = form.getlist('amount_options')
        amount_other = form.get('amount_other', '').strip()
        payment_methods = form.getlist('payment_methods')
        payment_method_other = form.get('payment_method_other', '').strip()

        errors = []
        if not sponsor_legal_name:
            errors.append('Sponsor legal name is required.')
        if not sponsorship_date_raw:
            errors.append('Date of sponsorship is required.')
        elif not sponsorship_date:
            errors.append('Date of sponsorship must be a valid date.')
        if not amount_options:
            errors.append('Select at least one amount option.')
        if not payment_methods:
            errors.append('Select at least one payment method.')

        if errors:
            return render_template(
                'sponsorship.html',
                errors=errors,
                form=form,
                amount_options=AMOUNT_OPTIONS,
                payment_options=PAYMENT_OPTIONS,
            )

        record = Sponsorship(
            sponsor_legal_name=sponsor_legal_name,
            sponsor_spiritual_name=sponsor_spiritual_name or None,
            sponsoring_for=sponsoring_for or None,
            occasion=occasion or None,
            sponsorship_date=sponsorship_date,
            notes=notes or None,
            amount_options=', '.join(amount_options) if amount_options else None,
            amount_other=amount_other or None,
            payment_methods=', '.join(payment_methods) if payment_methods else None,
            payment_method_other=payment_method_other or None,
            created_by_user_id=current_user.id,
        )
        db.session.add(record)
        db.session.commit()
        flash('Sponsorship saved successfully.', 'success')
        return redirect(url_for('views.my_data'))

    return render_template(
        'sponsorship.html',
        amount_options=AMOUNT_OPTIONS,
        payment_options=PAYMENT_OPTIONS,
    )


@views.route('/my-data')
@login_required
def my_data():
    guest_records = GuestIntake.query.filter_by(created_by_user_id=current_user.id).order_by(desc(GuestIntake.created_at)).all()
    sponsorship_records = Sponsorship.query.filter_by(created_by_user_id=current_user.id).order_by(desc(Sponsorship.created_at)).all()
    return render_template(
        'my-data.html',
        guest_records=guest_records,
        sponsorship_records=sponsorship_records,
    )


@views.route('/reports')
@login_required
def reports():
    if not _admin_only():
        return redirect(url_for('views.home'))

    guest_records = GuestIntake.query.order_by(desc(GuestIntake.created_at)).all()
    sponsorship_records = Sponsorship.query.order_by(
        Sponsorship.sponsorship_date.asc(),
        desc(Sponsorship.created_at),
    ).all()
    whatsapp_ready = GuestIntake.query.filter(GuestIntake.whatsapp_status.in_(['Yes', 'Already on it'])).all()

    return render_template(
        'reports.html',
        guest_records=guest_records,
        sponsorship_records=sponsorship_records,
        whatsapp_ready=whatsapp_ready,
    )


@views.route('/reports/export/<report_name>.csv')
@login_required
def export_report(report_name):
    if not _admin_only():
        return redirect(url_for('views.home'))

    output = io.StringIO()
    writer = csv.writer(output)

    if report_name == 'newcomers':
        writer.writerow([
            'Full Name', 'Phone Number', 'Email', 'First Time', 'WhatsApp Status',
            'Referral Sources', 'Referral Other', 'Residence Areas', 'Residence Other',
            'Notes', 'Created By', 'Created At',
        ])
        for record in GuestIntake.query.order_by(desc(GuestIntake.created_at)).all():
            writer.writerow([
                record.full_name,
                record.phone_number or '',
                record.email or '',
                'Yes' if record.first_time_at_temple else 'No',
                record.whatsapp_status or '',
                record.referral_sources or '',
                record.referral_other or '',
                record.residence_areas or '',
                record.residence_other or '',
                record.notes or '',
                record.created_by_user.display_name if record.created_by_user else '',
                record.created_at.strftime('%Y-%m-%d %H:%M'),
            ])
    elif report_name == 'sponsorships':
        writer.writerow([
            'Sponsor Legal Name', 'Sponsor Spiritual Name', 'Sponsoring For', 'Occasion',
            'Sponsorship Date', 'Amount Options', 'Amount Other', 'Payment Methods',
            'Payment Method Other', 'Notes', 'Created By', 'Created At',
        ])
        for record in Sponsorship.query.order_by(
            Sponsorship.sponsorship_date.asc(),
            desc(Sponsorship.created_at),
        ).all():
            writer.writerow([
                record.sponsor_legal_name,
                record.sponsor_spiritual_name or '',
                record.sponsoring_for or '',
                record.occasion or '',
                record.sponsorship_date.isoformat() if record.sponsorship_date else '',
                record.amount_options or '',
                record.amount_other or '',
                record.payment_methods or '',
                record.payment_method_other or '',
                record.notes or '',
                record.created_by_user.display_name if record.created_by_user else '',
                record.created_at.strftime('%Y-%m-%d %H:%M'),
            ])
    else:
        flash('Unknown report requested.', 'warning')
        return redirect(url_for('views.reports'))

    filename = f'{report_name}-report.csv'
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )


@views.route('/manifest.json')
def manifest():
    return send_from_directory(current_app.static_folder, 'manifest.json')


@views.route('/sw.js')
def service_worker():
    response = send_from_directory(current_app.static_folder, 'sw.js')
    response.headers['Cache-Control'] = 'no-cache'
    return response


@views.route('/offline')
def offline():
    return render_template('offline.html')
