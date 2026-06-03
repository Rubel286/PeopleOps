from flask import Flask, render_template
from flask_pymongo import PyMongo
from flask_login import LoginManager
from bson.objectid import ObjectId
from flask_mail import Mail
from datetime import datetime
from functools import lru_cache
import os
from flask_wtf.csrf import CSRFProtect
from celery import Celery
from werkzeug.exceptions import HTTPException

mongo = PyMongo()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'
mail = Mail()
csrf = CSRFProtect()
celery = Celery(__name__, broker=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'), backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'))
celery.autodiscover_tasks(['enterprise_app'])

def format_datetime_filter(value, format='%b %d, %Y at %I:%M %p'):
    if not value:
        return ""
    
    dt_object = None
    if isinstance(value, str):
        try:
            dt_object = datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return value
    elif isinstance(value, datetime):
        dt_object = value
    else:
        return value

    return dt_object.strftime(format)


from urllib.parse import urlparse, urlunparse

def create_app(config_class):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure MONGO_URI has a database name to prevent mongo.db from being None
    mongo_uri = app.config.get("MONGO_URI")
    if mongo_uri:
        try:
            parsed = urlparse(mongo_uri)
            if not parsed.path or parsed.path == '/':
                parsed = parsed._replace(path='/recruitmentDB')
                app.config["MONGO_URI"] = urlunparse(parsed)
        except Exception:
            pass

    mongo.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)

    # Adjust session cookie security for local development vs production iframe hosting
    if app.config.get("DEBUG"):
        app.config["SESSION_COOKIE_SECURE"] = False
        app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    else:
        app.config["SESSION_COOKIE_SECURE"] = True
        app.config["SESSION_COOKIE_SAMESITE"] = "None"

    # Force synchronous execution for testing to ensure instant emails
    app.config['CELERY_TASK_ALWAYS_EAGER'] = True
    celery.conf.update(app.config)

    app.jinja_env.filters['format_datetime'] = format_datetime_filter
    
    os.makedirs("uploads/resumes", exist_ok=True)
    os.makedirs("uploads/onboarding_docs", exist_ok=True)
    os.makedirs("uploads/joining_letters", exist_ok=True)
    os.makedirs("uploads/company_documents", exist_ok=True)
    os.makedirs(app.config.get('MAIL_FILE_PATH', 'mail_output'), exist_ok=True)
    
    app.config["UPLOAD_FOLDER_RESUMES"] = "uploads/resumes"
    app.config["UPLOAD_FOLDER_ONBOARDING"] = "uploads/onboarding_docs"
    
    # --- CORRECTED PART ---
    # Import utils and initialize the model logger here
    from . import utils
    utils.init_ml_model(app)
    # --- END CORRECTION ---
    
    from .models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        try:
            user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
            if user_data:
                if user_data.get('role') in ['employee', 'admin']:
                    emp_data = mongo.db.employees.find_one({'email': user_data['email']})
                    if emp_data:
                        user_data['name'] = emp_data.get('name', user_data.get('name', 'User'))
                return User(user_data) if user_data else None
        except Exception:
            return None

    @app.errorhandler(404)
    def not_found(e):
        return render_template('layouts/404.html'), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('layouts/403.html'), 403

    @app.errorhandler(HTTPException)
    def handle_exception(e):
        return render_template('layouts/error.html', error=e), e.code

    # Existing blueprint imports
    from .routes import main_routes, auth_routes, employee_routes, employee_portal_routes, document_routes, interviewer_routes, onboarding_routes, analytics_routes
    
    # NEW: Import the payroll and performance blueprints
    from .routes import finance_routes, performance_routes, chat_routes

    # Register existing blueprints
    app.register_blueprint(main_routes.main_bp)
    app.register_blueprint(auth_routes.auth_bp)
    app.register_blueprint(employee_routes.employee_bp, url_prefix='/employees')
    app.register_blueprint(employee_portal_routes.employee_portal_bp, url_prefix='/portal')
    app.register_blueprint(document_routes.document_bp, url_prefix='/documents')
    app.register_blueprint(interviewer_routes.interviewer_bp, url_prefix='/interviewer')
    app.register_blueprint(onboarding_routes.onboarding_bp, url_prefix='/onboarding')
    app.register_blueprint(analytics_routes.analytics_bp, url_prefix='/analytics')

    # NEW: Register the new blueprints
    app.register_blueprint(finance_routes.finance_bp)
    app.register_blueprint(performance_routes.performance_bp)
    app.register_blueprint(chat_routes.chat_bp)

    return app