"""
Декораторы для проверки ролей пользователей.
Fix #1 — авторизация по ролям.
"""
from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user


def manager_required(f):
    """Требует роль manager или admin."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_manager():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Требует роль admin."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function
