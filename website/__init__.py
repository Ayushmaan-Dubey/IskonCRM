from os import path
from flask import Flask
import os
from flask_login import LoginManager
from sqlalchemy import inspect, text

# Try to import Flask-SQLAlchemy; make it optional so app still runs if package is missing.
try:
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy()
except Exception:
    db = None

DB_NAME = "database.db"

login_manager = LoginManager()
login_manager.login_view = 'auth.login'

def create_app():
    app = Flask(__name__)
    # ensure SECRET_KEY is set so flash() (which uses the session) works
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret')
    # enable admin signup via environment variable (true/1/yes)
    app.config['ADMIN_SIGNUP_ENABLED'] = os.environ.get('ADMIN_SIGNUP_ENABLED', 'false').lower() in ('1','true','yes')

    # initialize db only if Flask-SQLAlchemy is installed
    if db is not None:
        # use DATABASE_URL in production (e.g. Heroku, Railway, Render); fall back to SQLite locally
        database_url = os.environ.get('DATABASE_URL')
        if database_url:
            # Heroku may use postgres:// - SQLAlchemy expects postgresql://
            if database_url.startswith('postgres://'):
                database_url = 'postgresql://' + database_url[len('postgres://'):]
            app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        else:
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            app.config.setdefault('SQLALCHEMY_DATABASE_URI', f"sqlite:///{db_path}")
        app.config.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', False)
        db.init_app(app)

        # import models so SQLAlchemy registers the metadata
        with app.app_context():
            from . import models  # registers model classes
            # if the user table already exists but lacks is_admin, add the column
            inspector = inspect(db.engine)
            if 'user' in inspector.get_table_names():
                cols = [c['name'] for c in inspector.get_columns('user')]
                # add is_admin if missing
                if 'is_admin' not in cols:
                    db.session.execute(text("ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0"))
                    db.session.commit()
                # add new fields if missing
                if 'last_name' not in cols:
                    db.session.execute(text("ALTER TABLE user ADD COLUMN last_name VARCHAR"))
                    db.session.commit()
                if 'legal_name' not in cols:
                    db.session.execute(text("ALTER TABLE user ADD COLUMN legal_name VARCHAR"))
                    db.session.commit()
                if 'username' not in cols:
                    db.session.execute(text("ALTER TABLE user ADD COLUMN username VARCHAR"))
                    db.session.commit()
                if 'phone_number' not in cols:
                    db.session.execute(text("ALTER TABLE user ADD COLUMN phone_number VARCHAR"))
                    db.session.commit()
                if 'role' not in cols:
                    db.session.execute(text("ALTER TABLE user ADD COLUMN role VARCHAR DEFAULT 'user'"))
                    db.session.commit()
                if 'must_change_password' not in cols:
                    db.session.execute(text("ALTER TABLE user ADD COLUMN must_change_password BOOLEAN DEFAULT 0"))
                    db.session.commit()
                if 'first_time_at_temple' not in cols:
                    db.session.execute(text("ALTER TABLE user ADD COLUMN first_time_at_temple BOOLEAN DEFAULT 0"))
                    db.session.commit()
                if 'contact_date' not in cols:
                    db.session.execute(text("ALTER TABLE user ADD COLUMN contact_date DATE"))
                    db.session.commit()
                if 'area' not in cols:
                    db.session.execute(text("ALTER TABLE user ADD COLUMN area VARCHAR"))
                    db.session.commit()
                if 'interests' not in cols:
                    db.session.execute(text("ALTER TABLE user ADD COLUMN interests VARCHAR"))
                    db.session.commit()
                if 'event_source' not in cols:
                    db.session.execute(text("ALTER TABLE user ADD COLUMN event_source VARCHAR"))
                    db.session.commit()
                if 'created_by_admin' not in cols:
                    db.session.execute(text("ALTER TABLE user ADD COLUMN created_by_admin VARCHAR"))
                    db.session.commit()
            # create any missing tables
            db.create_all()

    from .views import views
    from .auth import auth
    from .admin import admin

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')
    app.register_blueprint(admin, url_prefix='/')

    # initialize login manager with the app (do not call init_app at module import time)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    return app

def create_database(app):
    if not path.exists('website/' + DB_NAME):
        db.create_all(app=app)
        print('Database created!')

@login_manager.user_loader
def load_user(user_id):
    from .models import User
    return User.query.get(int(user_id))
