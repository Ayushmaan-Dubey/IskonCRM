from os import path
from flask import Flask
import os
from flask_login import LoginManager
from sqlalchemy import inspect, text

try:
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy()
except Exception:
    db = None

DB_NAME = "database.db"

login_manager = LoginManager()
login_manager.login_view = 'auth.login'

# Default message templates seeded on first run
DEFAULT_TEMPLATES = [
    {
        'name': 'Welcome Message',
        'template_type': 'welcome',
        'subject': 'Welcome to ISKCON Temple — We are glad you visited!',
        'body': (
            'Hare Krishna, {first_name}!\n\n'
            'Thank you for visiting the temple. We are so happy you joined us.\n\n'
            'We invite you to stay connected with our community. Feel free to reach out with any questions.\n\n'
            'Hare Krishna,\nTemple Team'
        ),
    },
    {
        'name': 'Not Yet Paid',
        'template_type': 'not_yet_paid',
        'subject': 'Temple Donation — Payment Instructions',
        'body': (
            'Hare Krishna, {first_name}!\n\n'
            'A donation record has been created for you. To complete your offering, please send payment '
            'using one of the methods below and confirm at: {form_url}\n\n'
            'Thank you for your seva.\n\nHare Krishna,\nTemple Team'
        ),
    },
    {
        'name': 'Thursday Broadcast',
        'template_type': 'thursday_broadcast',
        'subject': 'Sunday Temple Program — This Week at ISKCON',
        'body': (
            'Hare Krishna, {first_name}!\n\n'
            'A reminder that we have a temple program this Sunday. We hope to see you there!\n\n'
            'Date: {date}\nTime: Please check with the temple for current times.\n\n'
            'Hare Krishna,\nTemple Team'
        ),
    },
    {
        'name': 'New Member Digest',
        'template_type': 'new_member_digest',
        'subject': 'Weekly New Member Digest — {date}',
        'body': (
            'Hare Krishna!\n\n'
            'Here is a summary of new members and visitors who joined us this week:\n\n'
            '{member_list}\n\n'
            'Please make them feel welcome!\n\nHare Krishna,\nTemple Team'
        ),
    },
    {
        'name': 'Home Program Outreach Added',
        'template_type': 'hpo_added',
        'subject': 'Home Program Outreach — You Have Been Added',
        'body': (
            'Hare Krishna, {first_name}!\n\n'
            'You have been added to our Home Program Outreach list. '
            'A devotee will be in touch with you soon to discuss hosting a home program.\n\n'
            'Hare Krishna,\nTemple Team'
        ),
    },
    {
        'name': 'Donation Confirmation',
        'template_type': 'donation_confirmation',
        'subject': 'Thank You for Your Donation — {sponsorship_categories}',
        'body': (
            'Hare Krishna, {first_name}!\n\n'
            'Thank you for your generous offering. Your donation record has been received.\n\n'
            'Sponsorship: {sponsorship_categories}\nAmount: {donation_amount}\n\n'
            'May Krishna bless you abundantly.\n\nHare Krishna,\nTemple Team'
        ),
    },
]


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret')
    app.config['ADMIN_SIGNUP_ENABLED'] = os.environ.get('ADMIN_SIGNUP_ENABLED', 'false').lower() in ('1', 'true', 'yes')

    if db is not None:
        database_url = os.environ.get('DATABASE_URL')
        if database_url:
            if database_url.startswith('postgres://'):
                database_url = 'postgresql://' + database_url[len('postgres://'):]
            app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        else:
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            app.config.setdefault('SQLALCHEMY_DATABASE_URI', f"sqlite:///{db_path}")
        app.config.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', False)
        db.init_app(app)

        with app.app_context():
            from . import models

            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()

            # ── User table migrations ───────────────────────────────────────
            if 'user' in existing_tables:
                cols = [c['name'] for c in inspector.get_columns('user')]
                for col, ddl in [
                    ('is_admin',             'ALTER TABLE "user" ADD COLUMN is_admin BOOLEAN DEFAULT 0'),
                    ('last_name',            'ALTER TABLE "user" ADD COLUMN last_name VARCHAR'),
                    ('legal_name',           'ALTER TABLE "user" ADD COLUMN legal_name VARCHAR'),
                    ('username',             'ALTER TABLE "user" ADD COLUMN username VARCHAR'),
                    ('phone_number',         'ALTER TABLE "user" ADD COLUMN phone_number VARCHAR'),
                    ('role',                 "ALTER TABLE \"user\" ADD COLUMN role VARCHAR DEFAULT 'user'"),
                    ('must_change_password', 'ALTER TABLE "user" ADD COLUMN must_change_password BOOLEAN DEFAULT 0'),
                    ('first_time_at_temple', 'ALTER TABLE "user" ADD COLUMN first_time_at_temple BOOLEAN DEFAULT 0'),
                    ('contact_date',         'ALTER TABLE "user" ADD COLUMN contact_date DATE'),
                    ('area',                 'ALTER TABLE "user" ADD COLUMN area VARCHAR'),
                    ('interests',            'ALTER TABLE "user" ADD COLUMN interests VARCHAR'),
                    ('event_source',         'ALTER TABLE "user" ADD COLUMN event_source VARCHAR'),
                    ('created_by_admin',     'ALTER TABLE "user" ADD COLUMN created_by_admin VARCHAR'),
                ]:
                    if col not in cols:
                        try:
                            db.session.execute(text(ddl))
                            db.session.commit()
                        except Exception:
                            db.session.rollback()

            # ── Sponsorship table migrations ────────────────────────────────
            if 'sponsorship' in existing_tables:
                cols = [c['name'] for c in inspector.get_columns('sponsorship')]
                for col, ddl in [
                    ('sponsor_phone_number',   'ALTER TABLE sponsorship ADD COLUMN sponsor_phone_number VARCHAR'),
                    ('sponsor_email',          'ALTER TABLE sponsorship ADD COLUMN sponsor_email VARCHAR'),
                    ('sponsorship_categories', 'ALTER TABLE sponsorship ADD COLUMN sponsorship_categories VARCHAR'),
                    ('donation_amount',        'ALTER TABLE sponsorship ADD COLUMN donation_amount VARCHAR'),
                    ('not_yet_paid',           'ALTER TABLE sponsorship ADD COLUMN not_yet_paid BOOLEAN DEFAULT 0'),
                    ('source',                 "ALTER TABLE sponsorship ADD COLUMN source VARCHAR DEFAULT 'internal'"),
                    ('person_id',              'ALTER TABLE sponsorship ADD COLUMN person_id INTEGER REFERENCES person(id)'),
                    ('created_by_user_id_nullable_fix', None),  # handled below
                ]:
                    if col == 'created_by_user_id_nullable_fix':
                        # Make created_by_user_id nullable for public form submissions (Postgres only)
                        is_postgres = 'postgresql' in app.config.get('SQLALCHEMY_DATABASE_URI', '')
                        if is_postgres:
                            try:
                                db.session.execute(text(
                                    'ALTER TABLE sponsorship ALTER COLUMN created_by_user_id DROP NOT NULL'
                                ))
                                db.session.commit()
                            except Exception:
                                db.session.rollback()
                        continue
                    if col not in cols:
                        try:
                            db.session.execute(text(ddl))
                            db.session.commit()
                        except Exception:
                            db.session.rollback()

            # ── GuestIntake table migrations ────────────────────────────────
            if 'guest_intake' in existing_tables:
                cols = [c['name'] for c in inspector.get_columns('guest_intake')]
                if 'person_id' not in cols:
                    try:
                        db.session.execute(text(
                            'ALTER TABLE guest_intake ADD COLUMN person_id INTEGER REFERENCES person(id)'
                        ))
                        db.session.commit()
                    except Exception:
                        db.session.rollback()

            # ── Create all new tables ───────────────────────────────────────
            db.create_all()

            # ── Seed default message templates ──────────────────────────────
            from .models import MessageTemplate
            for tmpl in DEFAULT_TEMPLATES:
                if not MessageTemplate.query.filter_by(template_type=tmpl['template_type']).first():
                    db.session.add(MessageTemplate(**tmpl))
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

            # ── Migrate existing GuestIntake → Person (visitor tag) ─────────
            _migrate_guest_intakes_to_persons()

            # ── Migrate existing Sponsorships → Person (donator tag) ────────
            _migrate_sponsorships_to_persons()

    from .views import views
    from .auth import auth
    from .admin import admin

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')
    app.register_blueprint(admin, url_prefix='/')

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    return app


def _migrate_guest_intakes_to_persons():
    """One-time migration: create Person records for existing GuestIntake rows."""
    if db is None:
        return
    try:
        from .models import GuestIntake, Person
        unlinked = GuestIntake.query.filter(GuestIntake.person_id.is_(None)).all()
        for gi in unlinked:
            person = _find_or_create_person(
                gi.full_name, gi.email, gi.phone_number, gi.created_by_user_id
            )
            person.add_tag('visitor')
            gi.person_id = person.id
        db.session.commit()
    except Exception:
        db.session.rollback()


def _migrate_sponsorships_to_persons():
    """One-time migration: create/update Person records for existing Sponsorship rows."""
    if db is None:
        return
    try:
        from .models import Sponsorship, Person
        unlinked = Sponsorship.query.filter(Sponsorship.person_id.is_(None)).all()
        for sp in unlinked:
            person = _find_or_create_person(
                sp.sponsor_legal_name, sp.sponsor_email, sp.sponsor_phone_number,
                sp.created_by_user_id
            )
            person.add_tag('donator')
            sp.person_id = person.id
        db.session.commit()
    except Exception:
        db.session.rollback()


def _find_or_create_person(full_name, email, phone_number, created_by_user_id=None):
    from .models import Person
    person = None
    if email:
        person = Person.query.filter_by(email=email).first()
    if person is None and phone_number:
        person = Person.query.filter(
            Person.phone_number == phone_number,
            Person.email.is_(None)
        ).first()
    if person is None:
        person = Person(
            full_name=full_name,
            email=email or None,
            phone_number=phone_number or None,
            created_by_user_id=created_by_user_id,
        )
        db.session.add(person)
        db.session.flush()
    return person


def create_database(app):
    if not path.exists('website/' + DB_NAME):
        db.create_all(app=app)
        print('Database created!')


@login_manager.user_loader
def load_user(user_id):
    from .models import User
    return User.query.get(int(user_id))
