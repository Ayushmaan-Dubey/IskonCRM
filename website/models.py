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


class Person(db.Model):
    """Unified record for anyone who visits or donates to the temple."""
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(150), nullable=True, index=True)
    phone_number = db.Column(db.String(50), nullable=True)
    # Additive status tags stored as comma-separated string: visitor,donator,member
    status_tags = db.Column(db.String(200), default='', nullable=False)
    # Home Program Outreach fields
    home_program_outreach_participant = db.Column(db.Boolean, default=False, nullable=False)
    favorable_contact = db.Column(db.Boolean, default=False, nullable=False)
    location = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now(), nullable=False)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    def get_tags(self):
        if not self.status_tags:
            return []
        return [t.strip() for t in self.status_tags.split(',') if t.strip()]

    def has_tag(self, tag):
        return tag in self.get_tags()

    def add_tag(self, tag):
        tags = self.get_tags()
        if tag not in tags:
            tags.append(tag)
            self.status_tags = ','.join(tags)

    def remove_tag(self, tag):
        self.status_tags = ','.join(t for t in self.get_tags() if t != tag)

    @property
    def tag_badges(self):
        labels = {'visitor': ('Visitor', 'info'), 'donator': ('Donator', 'success'), 'member': ('Member', 'primary')}
        return [labels.get(t, (t.title(), 'secondary')) for t in self.get_tags()]


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
    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=True)


class Sponsorship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sponsor_legal_name = db.Column(db.String(200), nullable=False)
    sponsor_spiritual_name = db.Column(db.String(200), nullable=True)
    sponsor_phone_number = db.Column(db.String(50), nullable=True)
    sponsor_email = db.Column(db.String(150), nullable=True)
    # New: structured sponsorship categories (multi-select checkboxes)
    sponsorship_categories = db.Column(db.String(500), nullable=True)
    # Legacy free-text fields kept for backward compat
    sponsoring_for = db.Column(db.String(200), nullable=True)
    occasion = db.Column(db.String(200), nullable=True)
    sponsorship_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    # Explicit donation amount (new)
    donation_amount = db.Column(db.String(50), nullable=True)
    # Legacy amount fields kept for backward compat
    amount_options = db.Column(db.String(200), nullable=True)
    amount_other = db.Column(db.String(50), nullable=True)
    # Payment: single-select (Zelle, GPay, PayPal, Other, Not Yet Paid)
    payment_methods = db.Column(db.String(200), nullable=True)
    payment_method_other = db.Column(db.String(100), nullable=True)
    not_yet_paid = db.Column(db.Boolean, default=False, nullable=False)
    # Source: 'internal' (staff) or 'public' (public donation form)
    source = db.Column(db.String(20), default='internal', nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now(), nullable=False)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=True)


class InventoryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), nullable=True)
    quantity = db.Column(db.Integer, default=0, nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now(), nullable=False)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    audit_logs = db.relationship('InventoryAuditLog', backref='item', lazy=True, cascade='all, delete-orphan')


class InventoryAuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    quantity_before = db.Column(db.Integer, nullable=False)
    quantity_after = db.Column(db.Integer, nullable=False)
    changed_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    changed_at = db.Column(db.DateTime(timezone=True), default=func.now(), nullable=False)
    note = db.Column(db.String(500), nullable=True)


class MessageTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    # Types: welcome, not_yet_paid, thursday_broadcast, new_member_digest, hpo_added, donation_confirmation
    template_type = db.Column(db.String(50), nullable=False, unique=True)
    subject = db.Column(db.String(200), nullable=True)
    body = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=func.now())
    updated_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    def render(self, context):
        text = self.body
        for key, value in context.items():
            text = text.replace('{' + key + '}', str(value) if value is not None else '')
        return text

    def render_subject(self, context):
        text = self.subject or ''
        for key, value in context.items():
            text = text.replace('{' + key + '}', str(value) if value is not None else '')
        return text


class FactSheet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_data = db.Column(db.Text, nullable=False)  # base64 encoded image
    image_mime = db.Column(db.String(50), nullable=False, default='image/png')
    image_filename = db.Column(db.String(200), nullable=True)
    uploaded_at = db.Column(db.DateTime(timezone=True), default=func.now())
    uploaded_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)


class PaymentSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    zelle_details = db.Column(db.String(300), nullable=True)
    gpay_details = db.Column(db.String(300), nullable=True)
    paypal_details = db.Column(db.String(300), nullable=True)
    other_details = db.Column(db.String(300), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=func.now())
    updated_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)


class SecurityAuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), nullable=False)
    actor_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    actor_email = db.Column(db.String(150), nullable=True)
    target_type = db.Column(db.String(50), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    description = db.Column(db.String(500), nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now(), nullable=False)
    actor = db.relationship('User', foreign_keys=[actor_user_id])


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
        guest_intakes = db.relationship('GuestIntake', backref='created_by_user', lazy=True,
                                        foreign_keys='GuestIntake.created_by_user_id')
        sponsorships = db.relationship('Sponsorship', backref='created_by_user', lazy=True,
                                       foreign_keys='Sponsorship.created_by_user_id')
        is_admin = db.Column(db.Boolean, default=False, nullable=False)
        # Roles: member, user, sales, sunday_school_teacher, congregational_development, admins, super_admin
        role = db.Column(db.String(100), default='user', nullable=False)
        must_change_password = db.Column(db.Boolean, default=False, nullable=False)
        first_time_at_temple = db.Column(db.Boolean, default=False, nullable=False)
        contact_date = db.Column(db.Date, nullable=True)
        area = db.Column(db.String(200), nullable=True)
        interests = db.Column(db.String(500), nullable=True)
        event_source = db.Column(db.String(200), nullable=True)
        created_by_admin = db.Column(db.String(200), nullable=True)
        failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
        locked_until = db.Column(db.DateTime(timezone=True), nullable=True)

        @property
        def is_super_admin(self):
            return self.role == 'super_admin'

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
            self.created_by_admin = created_by_admin

        @property
        def is_super_admin(self):
            return self.role == 'super_admin'

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
