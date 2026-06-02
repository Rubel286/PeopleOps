from functools import wraps
from flask_login import login_required, current_user
from flask import flash, redirect, url_for

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'admin':
            flash("You need Admin permissions to access this page.", "danger")
            return redirect(url_for('employee_portal.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def employee_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'employee':
            flash("Employee portal access only.", "danger")
            return redirect(url_for('interviewer.dashboard'))
        return f(*args, **kwargs)
    return decorated_function