from . import db
from sqlalchemy import func
from flask_login import UserMixin

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String(10000))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date = db.Column(db.DateTime(timezone=True), default=func.now())

class Reminder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    description = db.Column(db.String(1000))
    remind_at = db.Column(db.DateTime(timezone=True))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class GuestIntake(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False)
    phone_number = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(150), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    first_time_at_temple = db.Column(db.Boolean, default=False, nullable=False)
    whatsapp_status = db.Column(db.String(50), nullable=True)
    referral_sources = db.Column(db.String(500), nullable=True)
    referral_other = db.Column(db.String(200), nullable=True)
    residence_areas = db.Column(db.String(500), nullable=True)
    residence_other = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now(), nullable=False)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Sponsorship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sponsor_legal_name = db.Column(db.String(200), nullable=False)
    sponsor_spiritual_name = db.Column(db.String(200), nullable=True)
    sponsor_phone_number = db.Column(db.String(50), nullable=True)
    sponsor_email = db.Column(db.String(150), nullable=True)
    sponsoring_for = db.Column(db.String(200), nullable=True)
    occasion = db.Column(db.String(200), nullable=True)
    sponsorship_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    amount_options = db.Column(db.String(200), nullable=True)
    amount_other = db.Column(db.String(50), nullable=True)
    payment_methods = db.Column(db.String(200), nullable=True)
    payment_method_other = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now(), nullable=False)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

if db is not None:
    class User(db.Model, UserMixin):
        id = db.Column(db.Integer, primary_key=True)
        email = db.Column(db.String(150), unique=True, nullable=False)
        password = db.Column(db.String(150), nullable=False)
        first_name = db.Column(db.String(150), nullable=False)
        legal_name = db.Column(db.String(200), nullable=True)
        username = db.Column(db.String(150), unique=True, nullable=True)
        phone_number = db.Column(db.String(50), nullable=True)
        last_name = db.Column(db.String(150), nullable=True)
        notes = db.relationship('Note')
        guest_intakes = db.relationship('GuestIntake', backref='created_by_user', lazy=True)
        sponsorships = db.relationship('Sponsorship', backref='created_by_user', lazy=True)
        is_admin = db.Column(db.Boolean, default=False, nullable=False)
        role = db.Column(db.String(100), default='user', nullable=False)
        must_change_password = db.Column(db.Boolean, default=False, nullable=False)
        first_time_at_temple = db.Column(db.Boolean, default=False, nullable=False)
        contact_date = db.Column(db.Date, nullable=True)
        area = db.Column(db.String(200), nullable=True)
        interests = db.Column(db.String(500), nullable=True)  # comma-separated
        event_source = db.Column(db.String(200), nullable=True)
        created_by_admin = db.Column(db.String(200), nullable=True)  # new field

        @property
        def display_name(self):
            if self.username:
                return self.username
            if self.legal_name:
                return self.legal_name
            full_name = ' '.join(part for part in [self.first_name, self.last_name] if part)
            return full_name or self.email

        def __repr__(self):
            return f"<User {self.email}>"
else:
    class User(UserMixin):
        def __init__(self, email, first_name, password, is_admin=False, last_name=None,
                     first_time_at_temple=False, contact_date=None, area=None, interests=None,
                     event_source=None, created_by_admin=None, legal_name=None, username=None,
                     phone_number=None, role='user', must_change_password=False):
            self.email = email
            self.first_name = first_name
            self.legal_name = legal_name
            self.username = username
            self.phone_number = phone_number
            self.last_name = last_name
            self.password = password
            self.is_admin = is_admin
            self.role = role
            self.must_change_password = must_change_password
            self.first_time_at_temple = first_time_at_temple
            self.contact_date = contact_date
            self.area = area
            self.interests = interests
            self.event_source = event_source
            self.created_by_admin = created_by_admin  # new field

        @property
        def display_name(self):
            if self.username:
                return self.username
            if self.legal_name:
                return self.legal_name
            full_name = ' '.join(part for part in [self.first_name, self.last_name] if part)
            return full_name or self.email

        def __repr__(self):
            return f"<User {self.email}>"
