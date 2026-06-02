from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from enterprise_app import mongo
from enterprise_app.models import User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated: return redirect(url_for('main.index'))
    if request.method == 'POST':
        email, password, name = request.form.get('email'), request.form.get('password'), request.form.get('name')
        confirm = request.form.get('confirm_password')
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('auth.signup'))
        if mongo.db.users.find_one({'email': email}):
            flash('Email address already exists.', 'warning')
            return redirect(url_for('auth.signup'))
        
        user_data = {
            'email': email, 
            'name': name,
            'password_hash': generate_password_hash(password), 
            'role': 'candidate'
        }
        mongo.db.users.insert_one(user_data)
        user_obj = User(user_data)
        login_user(user_obj)
        flash('Account created! You are now logged in.', 'success')
        return redirect(url_for('main.index'))
    return render_template('auth/signup.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # ===== DEBUG: ENTRY =====
    print("LOGIN ROUTE HIT")
    print("Authenticated:", current_user.is_authenticated)
    print("Current role:", getattr(current_user, "role", None))
    # =======================

    # 🚫 If already logged in
    if current_user.is_authenticated:
        if getattr(current_user, "role", None) == 'admin':
            print("AUTHENTICATED ADMIN HIT /login → logging out")
            logout_user()
            flash('Admins must log in using the admin login page.', 'danger')
            return redirect(url_for('auth.admin_login'))
        elif getattr(current_user, "role", None) == 'employee':
            print("AUTHENTICATED EMPLOYEE → redirecting")
            return redirect(url_for('employee_portal.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user_data = mongo.db.users.find_one({'email': email})

        # ===== DEBUG: POST =====
        print("LOGIN POST ATTEMPT")
        print("DB role:", user_data.get("role") if user_data else None)
        # ======================

        if not user_data or not check_password_hash(user_data['password_hash'], password):
            flash('Invalid credentials. Please check your email and password.', 'danger')
            return render_template('auth/login.html')

        # 🚫 HARD BLOCK ADMINS
        if user_data.get('role') == 'admin':
            print("ADMIN BLOCKED AT POST LEVEL")
            flash('Admins must log in using the admin login page.', 'danger')
            return redirect(url_for('auth.admin_login'))

        # ✅ EMPLOYEE LOGIN ONLY
        if user_data.get('role') == 'employee':
            employee_data = mongo.db.employees.find_one({'email': email})
            if employee_data:
                user_data['name'] = employee_data.get('name', user_data.get('name'))

        user_obj = User(user_data)
        login_user(user_obj)
        print("EMPLOYEE LOGGED IN SUCCESSFULLY")

        return redirect(url_for('employee_portal.dashboard'))

    return render_template('auth/login.html')


@auth_bp.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('interviewer.dashboard'))
        else:
            flash('You are not authorized to access the admin panel.', 'danger')
            return redirect(url_for('auth.login'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user_data = mongo.db.users.find_one({'email': email, 'role': 'admin'})

        if not user_data or not check_password_hash(user_data['password_hash'], password):
            flash('Invalid admin credentials.', 'danger')
            return render_template('auth/admin_login.html')

        user_obj = User(user_data)
        login_user(user_obj)

        return redirect(url_for('interviewer.dashboard'))

    return render_template('auth/admin_login.html')


@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))