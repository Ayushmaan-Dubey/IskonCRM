#!/usr/bin/env python3
import sys

try:
    from website import create_app
    from website import db
    from website.models import User
except ModuleNotFoundError as exc:
    missing_module = exc.name or "unknown dependency"
    raise SystemExit(
        f"Missing dependency: {missing_module}. "
        "Install project requirements with 'python3 -m pip install -r requirements.txt'."
    ) from exc

app = create_app()
with app.app_context():
    email = input('Email to make admin: ').strip()
    user = User.query.filter_by(email=email).first()
    if not user:
        print('User not found')
    else:
        user.is_admin = True
        db.session.commit()
        print('User promoted to admin')
