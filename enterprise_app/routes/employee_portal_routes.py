from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from enterprise_app.decorators import employee_required
from flask_login import current_user
from enterprise_app import mongo
from bson.objectid import ObjectId
from datetime import datetime
from enterprise_app.tasks import send_email_task
from werkzeug.utils import secure_filename
import os
from enterprise_app.routes.performance_routes import get_current_cycle

employee_portal_bp = Blueprint("employee_portal", __name__)

@employee_portal_bp.route("/my_applications")
@employee_required
def my_applications():
    # Fetch all applications tied to the current employee's email
    applications = list(mongo.db.applicants.find({"email": current_user.email}).sort("_id", -1))
    
    # Enrich jobs
    for app in applications:
        job = mongo.db.jobs.find_one({"_id": app.get("job_id")})
        app["job_title"] = job.get("title") if job else "Unknown Position"
        app["job_department"] = job.get("department") if job else "Unknown Department"
        
    return render_template("main/my_applications.html", applications=applications)

@employee_portal_bp.route("/dashboard")
@employee_required
def dashboard():
    employee = mongo.db.employees.find_one({"email": current_user.email})
    if not employee:
        # Fallback UI instead of redirect loop!
        return render_template_string("""
        {% extends "layouts/base.html" %}
        {% block title %}System Error{% endblock %}
        {% block content %}
        <div class="flex flex-col items-center justify-center h-full text-center" style="margin-top: 10rem;">
            <i data-feather="alert-triangle" style="width: 64px; height: 64px; color: var(--danger); margin-bottom: 2rem;"></i>
            <h1 class="text-gradient mb-4">Workspace Initialization Failed</h1>
            <p class="text-secondary" style="max-width: 500px; line-height: 1.6;">
                The central routing arrays detected a verified authentication token, but your corresponding Employee Identity Document ({{ current_user.email }}) could not be extracted from the active database schema.
            </p>
            <p class="text-secondary mt-4">Debug: current_user={{ current_user.email }}, role={{ current_user.role }}, route=employee_portal.dashboard</p>
        </div>
        <script>feather.replace();</script>
        {% endblock %}
        """)
    
    # Fetch performance cycle and review
    from enterprise_app.routes.performance_routes import get_current_cycle

    current_cycle = get_current_cycle()  # Or hardcode "2025-Q4" for testing if function missing

    review = mongo.db.performance_reviews.find_one({
        "employee_id": employee["_id"],
        "cycle": current_cycle
    }) or {}  # empty dict if no review — safe

    # Task queries — using "assignee_email" to show assigned tasks
    page = request.args.get('page', 1, type=int)
    per_page = 20
    skip = (page - 1) * per_page

    query = {"assignee_email": current_user.email}

    total_pending_tasks = mongo.db.tasks.count_documents({**query, "status": "Pending"})
    pending_tasks = list(mongo.db.tasks.find({**query, "status": "Pending"}).sort("due_date", 1).skip(skip).limit(per_page))

    total_in_progress_tasks = mongo.db.tasks.count_documents({**query, "status": "In Progress"})
    in_progress_tasks = list(mongo.db.tasks.find({**query, "status": "In Progress"}).sort("due_date", 1).skip(skip).limit(per_page))

    total_completed_tasks = mongo.db.tasks.count_documents({**query, "status": "Completed"})
    completed_tasks = list(mongo.db.tasks.find({**query, "status": "Completed"}).sort("completed_at", -1).skip(skip).limit(per_page))

    total_awaiting_tasks = mongo.db.tasks.count_documents({**query, "status": "Awaiting Acceptance"})
    awaiting_tasks = list(mongo.db.tasks.find({**query, "status": "Awaiting Acceptance"}).sort("created_at", -1).skip(skip).limit(per_page))

    leave_balance = employee.get("leave_allowance", 20) - employee.get("leave_taken", 0)

    resources = {
        "New Hire Guide": "https://example.com/new-hire-guide",
        "Employee Handbook": "https://example.com/employee-handbook",
        "Training Portal": "https://example.com/training-portal"
    }
    if employee.get("employee_type") == "Intern":
        resources["Intern Training"] = "https://example.com/intern-training"
    
    mentees = list(mongo.db.employees.find({"mentor": employee['name']})) if employee.get("employee_type") == "Full-time" else []

    return render_template("main/employee_dashboard.html",
                           employee=employee,
                           current_cycle=current_cycle,
                           review=review,
                           pending_tasks=pending_tasks,
                           total_pages_pending=(total_pending_tasks // per_page) + (1 if total_pending_tasks % per_page else 0),
                           in_progress_tasks=in_progress_tasks,
                           total_pages_in_progress=(total_in_progress_tasks // per_page) + (1 if total_in_progress_tasks % per_page else 0),
                           completed_tasks=completed_tasks,
                           total_pages_completed=(total_completed_tasks // per_page) + (1 if total_completed_tasks % per_page else 0),
                           awaiting_tasks=awaiting_tasks,
                           total_pages_awaiting=(total_awaiting_tasks // per_page) + (1 if total_awaiting_tasks % per_page else 0),
                           leave_balance=leave_balance,
                           resources=resources,
                           mentees=mentees,
                           page=page)

@employee_portal_bp.route("/update_task_status/<string:task_id>", methods=["POST"])
@employee_required
def update_task_status(task_id):
    new_status = request.form.get('status')

    if not new_status or new_status not in ['Pending', 'In Progress', 'Completed']:
        flash("Invalid status selected.", "danger")
        return redirect(url_for('employee_portal.dashboard'))

    try:
        task_id_obj = ObjectId(task_id)
    except:
        flash("Invalid task ID.", "danger")
        return redirect(url_for('employee_portal.dashboard'))

    # Find task assigned to current user
    task = mongo.db.tasks.find_one({
        "_id": task_id_obj,
        "assignee_email": current_user.email
    })

    if not task:
        flash("Task not found or you do not have permission to update it.", "danger")
        return redirect(url_for('employee_portal.dashboard'))

    # Optional: Prevent changing Completed back
    if task['status'] == 'Completed' and new_status != 'Completed':
        flash("Completed tasks cannot be changed.", "warning")
        return redirect(url_for('employee_portal.dashboard'))

    # Update status + timestamp if completed
    update_data = {"status": new_status}
    if new_status == 'Completed':
        update_data["completed_at"] = datetime.utcnow()

    mongo.db.tasks.update_one(
        {"_id": task_id_obj},
        {"$set": update_data}
    )

    flash(f"Task status updated to {new_status}.", "success")
    return redirect(url_for('employee_portal.dashboard'))

@employee_portal_bp.route("/accept_task", methods=['POST'])
@employee_required
def accept_task():
    task_id = request.form.get('task_id')  # Hidden input from template

    if not task_id:
        flash("Task ID missing.", "danger")
        return redirect(url_for('employee_portal.dashboard'))

    try:
        task_id_obj = ObjectId(task_id)
    except:
        flash("Invalid task ID.", "danger")
        return redirect(url_for('employee_portal.dashboard'))

    # Find task assigned to current user and still awaiting acceptance
    task = mongo.db.tasks.find_one({
        "_id": task_id_obj,
        "assignee_email": current_user.email,
        "status": "Awaiting Acceptance"
    })

    if not task:
        flash("Task not found or already accepted.", "danger")
        return redirect(url_for('employee_portal.dashboard'))

    # Accept it
    mongo.db.tasks.update_one(
        {"_id": task_id_obj},
        {
            "$set": {
                "status": "Pending",
                "accepted_at": datetime.utcnow()
            }
        }
    )

    flash("Task accepted successfully.", "success")
    return redirect(url_for('employee_portal.dashboard'))

@employee_portal_bp.route("/request_leave", methods=["POST"])
@employee_required
def request_leave():
    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")
    reason = request.form.get("reason")

    if not all([start_date, end_date, reason]):
        flash("All fields are required.", "danger")
        return redirect(url_for("employee_portal.dashboard"))

    try:
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        if end < start:
            flash("End date must be after start date.", "danger")
            return redirect(url_for("employee_portal.dashboard"))
        
        employee = mongo.db.employees.find_one({"email": current_user.email})
        days = (end - start).days + 1
        if employee.get("leave_allowance", 20) - employee.get("leave_taken", 0) < days:
            flash("Insufficient leave balance.", "danger")
            return redirect(url_for("employee_portal.dashboard"))

        mongo.db.leave_requests.insert_one({
            "employee_email": current_user.email,
            "employee_name": employee.get("name"),
            "start_date": start_date,
            "end_date": end_date,
            "reason": reason,
            "status": "Pending",
            "submitted_at": datetime.utcnow()
        })
        flash("Leave request submitted.", "success")
    except Exception:
        flash("Invalid date format.", "danger")
    
    return redirect(url_for("employee_portal.dashboard"))

@employee_portal_bp.route("/create_task", methods=["POST"])
@employee_required
def create_task():
    title = request.form.get("title")
    description = request.form.get("description")
    due_date = request.form.get("due_date")
    
    if not all([title, description, due_date]):
        flash("All fields are required.", "danger")
        return redirect(url_for("employee_portal.dashboard"))
    
    try:
        datetime.fromisoformat(due_date)
        mongo.db.tasks.insert_one({
            "title": title,
            "description": description,
            "employee_email": current_user.email,
            "status": "Pending",
            "created_at": datetime.utcnow(),
            "due_date": due_date
        })
        flash("Task created successfully.", "success")
    except Exception:
        flash("Invalid due date format.", "danger")
    
    return redirect(url_for("employee_portal.dashboard"))

@employee_portal_bp.route("/assign_task", methods=['POST'])
@employee_required
def assign_task():
    title = request.form.get('title')
    description = request.form.get('description')
    mentee_email = request.form.get('mentee_email')
    due_date_str = request.form.get('due_date')

    if not all([title, description, mentee_email, due_date_str]):
        flash("All fields are required.", "danger")
        return redirect(url_for('employee_portal.dashboard'))

    try:
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
    except ValueError:
        flash("Invalid due date format.", "danger")
        return redirect(url_for('employee_portal.dashboard'))

    # Check if mentee exists and current user is their mentor
    mentee = mongo.db.employees.find_one({
        "email": mentee_email,
        "employee_type": "Intern",
        "mentor": current_user.name  # Change to "mentor_email": current_user.email if you store email
    })

    if not mentee:
        flash("Invalid intern or you are not their mentor.", "danger")
        return redirect(url_for('employee_portal.dashboard'))

    # Create task
    task = {
        "title": title,
        "description": description,
        "assignee_email": mentee_email,
        "assigner_email": current_user.email,
        "due_date": due_date,
        "status": "Awaiting Acceptance",
        "created_at": datetime.utcnow()
    }
    mongo.db.tasks.insert_one(task)

    flash("Task assigned successfully.", "success")
    return redirect(url_for('employee_portal.dashboard'))

@employee_portal_bp.route("/submit_grievance", methods=["GET", "POST"])
@employee_required
def submit_grievance():
    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        submission_type = request.form.get("submission_type", "Standard IT/HR Support")
        
        if not all([title, description]):
            flash("All fields are required.", "danger")
            return redirect(url_for("employee_portal.submit_grievance"))
            
        # Anonymity override mechanism
        emp_email = current_user.email
        emp_name = getattr(current_user, 'name', 'Unknown User')
        
        if submission_type == "Confidential Grievance":
            emp_email = "Secure-Anonymous"
            emp_name = "Anonymous Employee"
        
        mongo.db.grievances.insert_one({
            "title": title,
            "description": description,
            "type": submission_type,
            "employee_email": emp_email,
            "employee_name": emp_name,
            "status": "Submitted",
            "submitted_at": datetime.utcnow()
        })
        flash("Support Ticket / Grievance submitted successfully.", "success")
        return redirect(url_for("employee_portal.dashboard"))
    
    return render_template("main/submit_grievance.html")

from werkzeug.utils import secure_filename
import os
from flask import request, redirect, url_for, flash, current_app
from flask_login import current_user

@employee_portal_bp.route("/update_profile_image", methods=["POST"])
@employee_required
def update_profile_image():
    file = request.files.get("image")

    if not file:
        flash("No file uploaded.", "danger")
        return redirect(url_for("employee_portal.dashboard"))

    if not file.mimetype.startswith("image/"):
        flash("Invalid file type.", "danger")
        return redirect(url_for("employee_portal.dashboard"))

    filename = secure_filename(f"{current_user.email}.png")
    upload_dir = os.path.join(current_app.root_path, "static/uploads/avatars")
    os.makedirs(upload_dir, exist_ok=True)

    path = os.path.join(upload_dir, filename)
    file.save(path)

    mongo.db.employees.update_one(
        {"email": current_user.email},
        {"$set": {"profile_image": f"uploads/avatars/{filename}"}}
    )

    flash("Profile picture updated.", "success")
    return redirect(url_for("employee_portal.dashboard"))
