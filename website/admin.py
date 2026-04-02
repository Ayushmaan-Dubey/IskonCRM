from functools import wraps
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, abort, request
from flask_login import current_user
from .models import User
from . import db
from werkzeug.security import generate_password_hash
import secrets

# Attempt to import send_new_user_email robustly
try:
    from .email_utils import send_new_user_email
except Exception:
    try:
        from website.email_utils import send_new_user_email
    except Exception:
        # last-resort: load module by file path so the helper works even in odd import contexts
        import importlib.util, os
        module_path = os.path.join(os.path.dirname(__file__), 'email_utils.py')
        if os.path.exists(module_path):
            spec = importlib.util.spec_from_file_location('email_utils', module_path)
            email_utils = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(email_utils)
            send_new_user_email = getattr(email_utils, 'send_new_user_email')
        else:
            # define a noop fallback so code that calls send_new_user_email won't crash
            def send_new_user_email(to_email, temp_password):
                return False, 'email_utils module not found'

admin = Blueprint('admin', __name__)
ROLE_OPTIONS = [
    ('user', 'User'),
    ('sales', 'Sales'),
    ('sunday_school_teacher', 'Sunday School Teacher'),
    ('congregational_development', 'Congregational Development'),
    ('admins', 'Admin'),
]


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None

# helper decorator to require admin login
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Use Login to access Admin Users.', 'info')
            return redirect(url_for('auth.admin_login'))
        if not getattr(current_user, 'is_admin', False):
            flash('Access denied.', 'danger')
            return redirect(url_for('views.home'))
        return f(*args, **kwargs)
    return decorated

@admin.route('/admin')
@admin_required
def admin_index():
    users = User.query.all() if hasattr(User, 'query') else []
    return render_template('admin/users.html', users=users, role_options=ROLE_OPTIONS)

# New route: /admin/users (explicit list URL)
@admin.route('/admin/users')
@admin_required
def admin_users():
    users = User.query.order_by(User.id.desc()).all() if hasattr(User, 'query') else []
    return render_template('admin/users.html', users=users, role_options=ROLE_OPTIONS)


@admin.route('/admin/users/<int:user_id>/role', methods=['POST'])
@admin_required
def admin_update_user_role(user_id):
    user = User.query.get_or_404(user_id)
    selected_role = request.form.get('role', 'user')
    valid_roles = {value for value, _label in ROLE_OPTIONS}
    if selected_role not in valid_roles:
        flash('Invalid role selected.', 'warning')
        return redirect(url_for('admin.admin_users'))

    user.role = selected_role
    user.is_admin = selected_role == 'admins'
    db.session.commit()
    flash(f'Updated role for {user.email}.', 'success')
    return redirect(url_for('admin.admin_users'))

@admin.route('/admin/create-user', methods=['GET', 'POST'])
@admin_required
def admin_create_user():
    errors = []
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        legal_name = request.form.get('legalName', '').strip()
        username = request.form.get('username', '').strip()
        phone_number = request.form.get('phoneNumber', '').strip()
        firstName = legal_name.split()[0] if legal_name else request.form.get('firstName', '').strip()
        lastName = request.form.get('lastName', '').strip()
        first_time = request.form.get('first_time_at_temple', 'no') == 'yes'
        contact_date = _parse_date(request.form.get('contact_date', '').strip())
        area = request.form.get('area', '').strip() or None
        interests_list = request.form.getlist('interests') if request.form else []
        interests = ', '.join(interests_list) if interests_list else None
        event_source = request.form.get('event_source', '').strip() or None

        # Check if user with same first and last name already exists
        if db is not None:
            name_conflict = None
            if firstName and lastName:
                name_conflict = User.query.filter_by(first_name=firstName, last_name=lastName).first()
            if name_conflict:
                flash('User already exists. Please check existing users in the database.', 'warning')
                return redirect(url_for('admin.admin_users'))

        if not email or not firstName:
            errors.append('Please fill out all required fields.')
        if not legal_name or not username or not phone_number:
            errors.append('Legal name, username, and phone number are required.')

        if db is not None:
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                errors.append('An account with that email already exists.')
            existing_username = User.query.filter_by(username=username).first()
            if existing_username:
                errors.append('That username is already taken.')

        if errors:
            return render_template('admin/create_user.html', errors=errors, form=request.form)

        if db is not None:
            temp_password = secrets.token_urlsafe(8)
            new_user = User(
                email=email,
                first_name=firstName,
                legal_name=legal_name,
                username=username,
                phone_number=phone_number,
                last_name=lastName,
                password=generate_password_hash(temp_password, method='pbkdf2:sha256'),
                is_admin=False,
                role='user',
                must_change_password=True,
                first_time_at_temple=first_time,
                contact_date=contact_date,
                area=area,
                interests=interests,
                event_source=event_source,
                created_by_admin=getattr(current_user, 'first_name', None),
            )
            db.session.add(new_user)
            db.session.commit()
            sent, err = send_new_user_email(email, temp_password)
            if not sent:
                flash(f'User created but failed to send email: {err}', 'warning')
            else:
                flash('User created and email sent successfully.', 'success')
        else:
            pass

        return redirect(url_for('admin.admin_users'))

    return render_template('admin/create_user.html')
