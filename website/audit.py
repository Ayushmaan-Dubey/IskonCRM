from flask import request

from . import db
from .models import SecurityAuditLog


def log_event(event_type, description=None, actor=None, actor_email=None, target_type=None, target_id=None):
    try:
        entry = SecurityAuditLog(
            event_type=event_type,
            actor_user_id=getattr(actor, 'id', None),
            actor_email=actor_email or getattr(actor, 'email', None),
            target_type=target_type,
            target_id=target_id,
            description=description,
            ip_address=request.remote_addr,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
