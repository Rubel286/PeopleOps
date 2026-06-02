from flask import Blueprint, render_template, request, redirect, url_for, current_app, flash, session
from flask_login import current_user, login_required, login_user
from enterprise_app.utils import get_active_role
from enterprise_app.models import User
from werkzeug.utils import secure_filename
import os
from enterprise_app import mongo
from bson.objectid import ObjectId
from datetime import datetime
from enterprise_app.tasks import process_resume_analysis, send_email_task
from enterprise_app.utils import validate_file

main_bp = Blueprint("main", __name__, template_folder='templates')

@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        # Validate session identity cleanly against DB dropping ghost cookies
        user_check = mongo.db.users.find_one({"_id": ObjectId(current_user.id)})
        if not user_check:
            from flask_login import logout_user
            logout_user()
            return render_template("main/index.html")
            
        if user_check.get('role') == 'admin':
            return redirect(url_for('interviewer.dashboard'))
        elif user_check.get('role') == 'employee':
            return redirect(url_for('employee_portal.dashboard'))
            
    return render_template("main/index.html")

@main_bp.route("/jobs")
def job_listings():
    jobs = list(mongo.db.jobs.find({"status": "Open"}).sort("date_posted", -1))
    return render_template("main/job_listings.html", jobs=jobs)

@main_bp.route("/switch_role/<role>")
@login_required
def switch_role(role):
    if role == "employee":
        if current_user.role == "admin":
            session["original_admin_id"] = str(current_user.id)
            
        emp = mongo.db.users.find_one({"role": "employee"})
        if not emp:
            flash("No employee account found. Create one first.", "warning")
            return redirect(url_for("interviewer.dashboard"))
            
        login_user(User(emp))
        flash("Demo Sandbox: Logged in as real Employee.", "success")
        return redirect(url_for("employee_portal.dashboard"))
        
    elif role == "admin" or role == "reset":
        admin_id = session.get("original_admin_id")
        if admin_id:
            admin_user = mongo.db.users.find_one({"_id": ObjectId(admin_id)})
            if admin_user:
                login_user(User(admin_user))
                flash("Demo Sandbox: Restored Admin access.", "success")
                return redirect(url_for("interviewer.dashboard"))
                
        if current_user.role == "admin":
            return redirect(url_for("interviewer.dashboard"))
            
        flash("Could not restore admin. Please login again.", "danger")
        return redirect(url_for("auth.logout"))

    return redirect(url_for("main.index"))

@main_bp.route("/apply/<string:job_id>")
def apply_form(job_id):
    job = mongo.db.jobs.find_one_or_404({"_id": ObjectId(job_id)})
    return render_template("main/apply.html", job=job)

@main_bp.route("/submit_application", methods=["POST"])
def submit_application():
    name = request.form.get("name")
    email = request.form.get("email")
    job_id = request.form.get("job_id")
    resume = request.files.get("resume")

    if not all([name, email, job_id, resume]):
        flash("All fields are required.", "danger")
        return redirect(url_for('main.apply_form', job_id=job_id))
    
    if not validate_file(resume, ['application/pdf']):
        flash("Invalid file type. Please upload a PDF.", "danger")
        return redirect(url_for('main.apply_form', job_id=job_id))

    job = mongo.db.jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        flash("The job you are applying for no longer exists.", "danger")
        return redirect(url_for("main.job_listings"))

    if mongo.db.applicants.find_one({"email": email, "job_id": ObjectId(job_id)}):
        flash("You have already applied for this position.", "warning")
        return redirect(url_for("main.job_listings"))

    upload_folder = current_app.config["UPLOAD_FOLDER_RESUMES"]
    filename = secure_filename(f"{job_id}_{email.replace('@', '_')}.pdf")
    resume_path = os.path.join(upload_folder, filename)
    resume.save(resume_path)

    applicant_data = {
        "name": name,
        "email": email,
        "role_applied_for": job["title"],
        "job_id": ObjectId(job_id),
        "resume_path": resume_path,
        "status": "Applied",  # <-- FIX
        "match_score": -1,
        "activity": [{
            "type": "application",
            "notes": f"Applied for {job['title']}.",
            "author": "System",
            "timestamp": datetime.utcnow()
        }]
    }

    result = mongo.db.applicants.insert_one(applicant_data)
    applicant_id = result.inserted_id

    process_resume_analysis.delay(str(applicant_id), resume_path, str(job_id))

    send_email_task.delay(
        email_type="application",
        recipient=email,
        context={"name": name, "role": job["title"]}
    )

    return redirect(url_for("main.success", message="Your application has been submitted! Our AI is now processing it."))

@main_bp.route("/success")
def success():
    message = request.args.get('message', 'Operation successful.')
    return render_template("main/success.html", message=message)