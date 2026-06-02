from flask import Blueprint, render_template, request
from flask_login import login_required
from enterprise_app import mongo
from bson.objectid import ObjectId
from enterprise_app.decorators import admin_required
from itertools import groupby
from datetime import datetime, timedelta # Import datetime and timedelta

employee_bp = Blueprint("employee", __name__)

@employee_bp.route("/")
@login_required
@admin_required
def directory():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    skip = (page - 1) * per_page
    
    # Define 'now' to be passed to the template
    now = datetime.utcnow()

    total_employees = mongo.db.employees.count_documents({})
    employees_cursor = mongo.db.employees.find().sort([("department", 1), ("name", 1)]).skip(skip).limit(per_page)
    employees_by_dept = {}
    for key, group in groupby(employees_cursor, key=lambda x: x['department']):
        employees_by_dept[key] = list(group)
    
    # Pass 'now' and 'timedelta' into the template context
    return render_template(
        "interviewer/employee_directory.html", 
        employees_by_dept=employees_by_dept, 
        page=page, 
        total_pages=(total_employees // per_page) + (1 if total_employees % per_page else 0),
        now=now,
        timedelta=timedelta
    )

@employee_bp.route("/profile/<string:employee_id>")
@login_required
@admin_required
def profile(employee_id):
    employee = mongo.db.employees.find_one_or_404({"_id": ObjectId(employee_id)})
    activity_logs = list(mongo.db.activity_logs.find({"user_email": employee["email"]}).sort("timestamp", -1))
    
    mentor = None
    if employee.get("mentor"):
        mentor = mongo.db.employees.find_one({"name": employee["mentor"]})

    return render_template("main/employee_profile.html", employee=employee, logs=activity_logs, mentor=mentor)