from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from .models import User
from . import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
import os

auth = Blueprint('auth', __name__)

ADMIN_SIGNUP_PIN = os.environ.get('ADMIN_SIGNUP_PIN', 'RR')
SUPER_ADMIN_SIGNUP_PIN = os.environ.get('SUPER_ADMIN_SIGNUP_PIN', '2026')


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        super_admin_pin = request.form.get('super_admin_pin', '').strip()
        user = User.query.filter_by(email=email).first()
        if user:
            if check_password_hash(user.password, password):
                if user.role == 'super_admin' and super_admin_pin != SUPER_ADMIN_SIGNUP_PIN:
                    flash('Incorrect Super Admin PIN.', 'error')
                else:
                    flash('Logged in successfully!', 'success')
                    login_user(user, remember=True)
                    return redirect(url_for('views.home'))
            else:
                flash('Incorrect password, try again.', 'error')
        else:
            flash('Email does not exist.', 'error')
    return render_template("login.html", user=current_user)



@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@auth.route('/signup', methods=['GET', 'POST'])
def sign_up():
    errors = []
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        legal_name = request.form.get('legalName', '').strip()
        username = request.form.get('username', '').strip()
        phone_number = request.form.get('phoneNumber', '').strip()
        pin = request.form.get('pin', '').strip()
        account_type = request.form.get('account_type', 'admins').strip()
        firstName = legal_name.split()[0] if legal_name else request.form.get('firstName', '').strip()
        password1 = request.form.get('password1', '')
        password2 = request.form.get('password2', '')

        if account_type not in ('admins', 'super_admin'):
            account_type = 'admins'

        if not legal_name or not username or not email or not phone_number or not password1 or not password2 or not pin:
            errors.append('Please fill out all fields.')
        if password1 != password2:
            errors.append('Passwords do not match.')
        if len(password1) < 6:
            errors.append('Password must be at least 6 characters.')
        if account_type == 'super_admin':
            if pin != SUPER_ADMIN_SIGNUP_PIN:
                errors.append('Incorrect Super Admin PIN.')
        elif pin != ADMIN_SIGNUP_PIN:
            errors.append('Incorrect Admin PIN.')

        # check for existing email when using the database
        if db is not None:
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                errors.append('An account with that email already exists.')
            existing_username = User.query.filter_by(username=username).first()
            if existing_username:
                errors.append('That username is already taken.')

        if errors:
            return render_template('sign-up.html', errors=errors, form=request.form)

        # create user when db available; otherwise skip persistence
        if db is not None:
            new_user = User(
                email=email,
                first_name=firstName,
                legal_name=legal_name,
                username=username,
                phone_number=phone_number,
                role=account_type,
                is_admin=True,
                password=generate_password_hash(password1, method='pbkdf2:sha256'),
            )
            db.session.add(new_user)
            db.session.commit()
        else:
            # no DB installed; skip storing user but still flash success for local testing
            pass

        flash('Account created successfully. You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('sign-up.html', user=current_user)


# Old admin-specific signup/login URLs now point at the unified pages above,
# kept so existing bookmarks/emailed links don't break.
@auth.route('/admin/signup', methods=['GET', 'POST'])
def admin_sign_up():
    return redirect(url_for('auth.sign_up'))


@auth.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    return redirect(url_for('auth.login'))


@auth.route('/admin/logout')
def admin_logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
