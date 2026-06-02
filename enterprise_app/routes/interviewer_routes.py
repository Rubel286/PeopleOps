from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory, current_app
from enterprise_app.decorators import admin_required
from flask_login import current_user, login_required
from enterprise_app import mongo
from bson.objectid import ObjectId
from bson.errors import InvalidId
import os
from datetime import datetime, date, timedelta
from enterprise_app.tasks import send_email_task
from ics import Calendar, Event
from enterprise_app.utils import generate_onboarding_token
from enterprise_app.company_structure import COMPANY_STRUCTURE


interviewer_bp = Blueprint("interviewer", __name__)

@interviewer_bp.route("/dashboard")
@admin_required
def dashboard():
    search = request.args.get('search', '').strip()
    query = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"role_applied_for": {"$regex": search, "$options": "i"}}
        ]

    employee = mongo.db.employees.find_one({"email": current_user.email})
    if not employee:
        employee = {"name": current_user.name, "email": current_user.email}

    page = request.args.get('page', 1, type=int)
    per_page = 20
    skip = (page - 1) * per_page

    # Applied
    applied_query = {**query, "status": "Applied"}
    total_applied = mongo.db.applicants.count_documents(applied_query)
    applied_candidates = list(
        mongo.db.applicants.find(applied_query)
        .sort([("activity.timestamp", -1)])
        .skip(skip)
        .limit(per_page)
    )

    # Shortlisted
    shortlisted_query = {**query, "status": "Shortlist"}
    total_shortlisted = mongo.db.applicants.count_documents(shortlisted_query)
    shortlisted_candidates = list(
        mongo.db.applicants.find(shortlisted_query)
        .sort([("activity.timestamp", -1)])
        .skip(skip)
        .limit(per_page)
    )

    # Upcoming Interviews (paginated, future only)
    now = datetime.utcnow()
    interview_pipeline = [
        {"$match": {**query, "status": "Shortlist"}},
        {"$unwind": "$activity"},
        {"$match": {"activity.type": "interview", "activity.interview_date": {"$gte": now}}},
        {"$sort": {"activity.interview_date": 1}},
        {"$group": {
            "_id": "$_id",
            "activity": {"$push": "$activity"},
            "original": {"$first": "$$ROOT"}
        }},
        {"$replaceRoot": {"newRoot": {"$mergeObjects": ["$original", {"activity": "$activity"}]}}},
        {"$skip": skip},
        {"$limit": per_page}
    ]
    upcoming_interviews = list(mongo.db.applicants.aggregate(interview_pipeline))

    # Total upcoming interviews count (for pagination)
    total_interviews_pipeline = [
        {"$match": {**query, "status": "Shortlist"}},
        {"$unwind": "$activity"},
        {"$match": {"activity.type": "interview", "activity.interview_date": {"$gte": now}}},
        {"$count": "total"}
    ]
    total_interviews_result = list(mongo.db.applicants.aggregate(total_interviews_pipeline))
    total_interviews = total_interviews_result[0]["total"] if total_interviews_result else 0

    # Pending Leave
    pending_leave_count = mongo.db.leave_requests.count_documents({"status": "Pending"})

    # Employees on leave today
    today = datetime.utcnow().date().isoformat()
    employees_on_leave = list(mongo.db.leave_requests.find({
        "status": "Approved",
        "start_date": {"$lte": today},
        "end_date": {"$gte": today}
    }))

    # Extracted Feed Items
    recent_leaves = list(mongo.db.leave_requests.find({"status": "Pending"}).sort("created_at", -1).limit(5))
    recent_grievances = list(mongo.db.grievances.find({"status": "Pending"}).sort("created_at", -1).limit(5))

    # Total hires
    total_hires = mongo.db.applicants.count_documents({"status": "Hired"})

    return render_template(
        "interviewer/interviewer_dashboard.html",
        applied=applied_candidates,
        total_applied=total_applied,
        total_pages_applied=(total_applied // per_page) + (1 if total_applied % per_page else 0),
        shortlisted=shortlisted_candidates,
        total_shortlisted=total_shortlisted,
        total_pages_shortlisted=(total_shortlisted // per_page) + (1 if total_shortlisted % per_page else 0),
        agenda=upcoming_interviews,
        total_interviews=total_interviews,
        total_pages_agenda=(total_interviews // per_page) + (1 if total_interviews % per_page else 0),
        employee=employee,
        pending_leave_count=pending_leave_count,
        employees_on_leave=employees_on_leave,
        recent_leaves=recent_leaves,
        recent_grievances=recent_grievances,
        total_hires=total_hires,
        page=page,
        search=search  # pass search term back to template for input value
    )

@interviewer_bp.route("/candidate/<string:applicant_id>")
@admin_required
def candidate_profile(applicant_id):
    try:
        applicant = mongo.db.applicants.find_one_or_404({"_id": ObjectId(applicant_id)})
        return render_template("interviewer/candidate_profile.html", applicant=applicant)
    except InvalidId:
        flash("Invalid candidate ID format.", "danger")
        return redirect(url_for("interviewer.dashboard"))
    except Exception as e:
        current_app.logger.error(f"Error loading candidate profile for ID {applicant_id}: {e}")
        flash("An unexpected error occurred while loading the candidate profile.", "danger")
        return redirect(url_for("interviewer.dashboard"))

@interviewer_bp.route("/pipeline")
@admin_required
def pipeline():
    candidates = list(mongo.db.applicants.find().sort("applied_at", -1))
    
    # Sanitize object IDs and datetime for JSON serialization in the template
    for c in candidates:
        c['_id'] = str(c['_id'])
        if 'applied_at' in c and hasattr(c['applied_at'], 'isoformat'):
            c['applied_at'] = c['applied_at'].isoformat()
        if 'activity' in c:
            for act in c['activity']:
                if 'timestamp' in act and hasattr(act['timestamp'], 'isoformat'):
                    act['timestamp'] = act['timestamp'].isoformat()
    return render_template("interviewer/pipeline.html", candidates=candidates)

@interviewer_bp.route("/candidate/<string:applicant_id>/activity", methods=["POST"])
@login_required
def add_activity(applicant_id):
    try:
        action_type = request.form.get("action_type")
        message = request.form.get("message", "").strip()
        interview_date_str = request.form.get("interview_date")

        applicant = mongo.db.applicants.find_one({"_id": ObjectId(applicant_id)})
        if not applicant:
            flash("Candidate not found.", "danger")
            return redirect(url_for("interviewer.dashboard"))

        activity_entry = {
            "type": action_type,
            "message": message,
            "author": current_user.name,
            "timestamp": datetime.utcnow().isoformat(),
        }

        update_fields = {
            "$push": {
                "activity": {
                    "$each": [activity_entry],
                    "$position": 0,
                }
            }
        }

        if action_type == "interview":
            if not interview_date_str:
                flash("Interview date is required.", "danger")
                return redirect(url_for("interviewer.candidate_profile", applicant_id=applicant_id))

            try:
                interview_date = datetime.strptime(interview_date_str, "%Y-%m-%dT%H:%M")
            except ValueError:
                flash("Invalid interview date format.", "danger")
                return redirect(url_for("interviewer.candidate_profile", applicant_id=applicant_id))

            update_fields["$set"] = {
                "status": "Interview Scheduled",
                "interview_date": interview_date,
            }
            
            send_email_task.delay(
                email_type="interview",
                recipient=applicant.get("email"),
                context={
                    "name": applicant.get("name"),
                    "role": applicant.get("role_applied_for", "Position"),
                    "interview_type": "Technical Interview",
                    "interview_date": interview_date.isoformat()
                }
            )

        elif action_type == "hire":
            print(f"[TRACE] action_type == 'hire' detected for applicant {applicant_id}")
            existing_employee = mongo.db.employees.find_one({"email": applicant.get("email")})

            if existing_employee:
                flash("Employee already exists.", "warning")
            else:
                job = mongo.db.jobs.find_one({"_id": ObjectId(applicant.get("job_id"))})
                employee_doc = {
                    "name": applicant.get("name", "Unknown"),
                    "email": applicant.get("email"),
                    "phone_number": applicant.get("phone_number", ""),
                    "department": job.get("department") if job else "General",
                    "role": job.get("title") if job else "Employee",
                    "start_date": datetime.utcnow(),
                    "employee_type": "Full-time",
                    "leave_allowance": 20,
                    "leave_taken": 0,
                    "gender": applicant.get("gender", "male"),
                    "contract_end_date": None,
                }
                mongo.db.employees.insert_one(employee_doc)
                mongo.db.users.update_one(
                    {"email": applicant["email"]},
                    {"$set": {"role": "employee"}}
                )

            update_fields["$set"] = {
                "status": "Hired",
                "hired_at": datetime.utcnow(),
            }
            
            token = applicant.get("onboarding_token")
            if not token:
                token = generate_onboarding_token(applicant_id)
            
            # Generate the URL synchronously so it has Request Context before hitting the Celery Queue
            onboarding_link = url_for('onboarding.portal', applicant_id=str(applicant_id), token=token, _external=True)
                
            print(f"[TRACE] Preparing to queue send_email_task.delay(hire) for {applicant.get('email')}")
            send_email_task.delay(
                email_type="hire",
                recipient=applicant.get("email"),
                context={
                    "name": applicant.get("name", "Candidate"),
                    "role": applicant.get("role_applied_for", "Position"),
                    "onboarding_link": onboarding_link
                }
            )

        elif action_type == "reject":
            update_fields["$set"] = {
                "status": "Rejected",
                "rejected_at": datetime.utcnow(),
            }
            
            send_email_task.delay(
                email_type="reject",
                recipient=applicant.get("email"),
                context={
                    "name": applicant.get("name"),
                    "role": applicant.get("role_applied_for", "Position")
                }
            )

        elif action_type == "shortlist":
            update_fields["$set"] = {
                "status": "Shortlist",
                "shortlisted_at": datetime.utcnow(),
            }



        elif action_type == "comment":
            # Only add comment — no status change
            pass

        else:
            flash("Invalid action type.", "danger")
            return redirect(url_for("interviewer.candidate_profile", applicant_id=applicant_id))

        mongo.db.applicants.update_one(
            {"_id": ObjectId(applicant_id)},
            update_fields,
        )

        flash(f"{action_type.capitalize()} action completed.", "success")
        return redirect(url_for("interviewer.candidate_profile", applicant_id=applicant_id))

    except Exception as e:
        current_app.logger.exception("Error processing candidate action")
        flash("Server error occurred.", "danger")
        return redirect(url_for("interviewer.dashboard"))

@interviewer_bp.route("/view_resume/<string:applicant_id>")
@admin_required
def view_resume(applicant_id):
    try:
        applicant = mongo.db.applicants.find_one_or_404({"_id": ObjectId(applicant_id)})
        resume_path = applicant.get("resume_path")
        if not resume_path or not os.path.exists(resume_path):
            flash("Resume not found.", "danger")
            return redirect(url_for("interviewer.candidate_profile", applicant_id=applicant_id))
        
        directory, filename = os.path.split(resume_path)
        # Use root_path to construct absolute path correctly
        return send_from_directory(directory=os.path.join(current_app.root_path, '..', directory), path=filename, as_attachment=False)
    except Exception as e:
        current_app.logger.error(f"Error viewing resume for {applicant_id}: {e}")
        flash("Invalid request to view resume.", "danger")
        return redirect(url_for("interviewer.dashboard"))

@interviewer_bp.route("/manage_jobs")
@admin_required
def manage_jobs():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    skip = (page - 1) * per_page
    total_jobs = mongo.db.jobs.count_documents({})
    
    # Corrected order of operations
    jobs = list(
        mongo.db.jobs.find()
        .sort([("date_posted", -1)])
        .skip(skip)
        .limit(per_page)
    )
    
    return render_template(
        "interviewer/manage_jobs.html", 
        jobs=jobs, 
        page=page, 
        total_pages=(total_jobs // per_page) + (1 if total_jobs % per_page else 0)
    )

@interviewer_bp.route("/create_job", methods=["GET", "POST"])
@admin_required
def create_job():
    if request.method == "POST":
        title = request.form.get("title")
        department = request.form.get("department")
        location = request.form.get("location")
        job_type = request.form.get("job_type")
        description = request.form.get("description")
        requirements = request.form.get("requirements")
        if not all([title, department, location, job_type, description]):
            flash("All required fields must be filled.", "danger")
            return redirect(url_for("interviewer.create_job"))
        mongo.db.jobs.insert_one({
            "title": title,
            "department": department,
            "location": location,
            "type": job_type,
            "description": description,
            "requirements": requirements,
            "status": "Open",
            "date_posted": datetime.utcnow()
        })
        flash("Job created successfully.", "success")
        return redirect(url_for("interviewer.manage_jobs"))
    return render_template("main/job_form.html", action="Create", departments=list(COMPANY_STRUCTURE.keys()))

@interviewer_bp.route("/edit_job/<string:job_id>", methods=["GET", "POST"])
@admin_required
def edit_job(job_id):
    try:
        job = mongo.db.jobs.find_one_or_404({"_id": ObjectId(job_id)})
        if request.method == "POST":
            title = request.form.get("title")
            department = request.form.get("department")
            location = request.form.get("location")
            job_type = request.form.get("job_type")
            description = request.form.get("description")
            requirements = request.form.get("requirements")
            status = request.form.get("status")
            
            if not all([title, department, location, job_type, description]):
                flash("All required fields must be filled.", "danger")
                return redirect(url_for("interviewer.edit_job", job_id=job_id))
                
            mongo.db.jobs.update_one(
                {"_id": ObjectId(job_id)},
                {"$set": {
                    "title": title,
                    "department": department,
                    "location": location,
                    "type": job_type,
                    "description": description,
                    "requirements": requirements,
                    "status": status
                }}
            )
            flash("Job updated successfully.", "success")
            return redirect(url_for("interviewer.manage_jobs"))
        
        return render_template("main/job_form.html", job=job, action="Edit", departments=list(COMPANY_STRUCTURE.keys()))
    except Exception as e:
        current_app.logger.error(f"Error editing job {job_id}: {e}")
        flash("Invalid job ID or error occurred.", "danger")
        return redirect(url_for("interviewer.manage_jobs"))

@interviewer_bp.route("/delete_job/<string:job_id>", methods=["POST"])
@admin_required
def delete_job(job_id):
    try:
        mongo.db.jobs.delete_one({"_id": ObjectId(job_id)})
        flash("Job deleted successfully.", "success")
        return redirect(url_for("interviewer.manage_jobs"))
    except Exception as e:
        current_app.logger.error(f"Error deleting job {job_id}: {e}")
        flash("Error deleting job.", "danger")
        return redirect(url_for("interviewer.manage_jobs"))

@interviewer_bp.route("/contract_tracking")
@admin_required
def contract_tracking():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    skip = (page - 1) * per_page
    thirty_days_from_now = datetime.utcnow() + timedelta(days=30)
    query = {"contract_end_date": {"$exists": True, "$ne": None, "$lte": thirty_days_from_now}}
    total_contracts = mongo.db.employees.count_documents(query)
    contracts_expiring = list(mongo.db.employees.find(query).sort("contract_end_date", 1).skip(skip).limit(per_page))
    return render_template("interviewer/contract_tracking.html", contracts_expiring=contracts_expiring, page=page, total_pages=(total_contracts // per_page) + (1 if total_contracts % per_page else 0))

@interviewer_bp.route("/grievances")
@admin_required
def grievances():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    skip = (page - 1) * per_page
    total_grievances = mongo.db.grievances.count_documents({})
    grievances_list = list(mongo.db.grievances.find().sort("submitted_at", -1).skip(skip).limit(per_page))
    return render_template("interviewer/manage_grievances.html", grievances=grievances_list, page=page, total_pages=(total_grievances // per_page) + (1 if total_grievances % per_page else 0))

@interviewer_bp.route("/employees_on_leave")
@admin_required
def employees_on_leave():
    today = datetime.utcnow().date().isoformat()
    leaves_cursor = mongo.db.leave_requests.find({
        "status": "Approved",
        "start_date": {"$lte": today},
        "end_date": {"$gte": today}
    })
    
    employees_on_leave_list = []
    for req in leaves_cursor:
        email = req.get("employee_email")
        emp = mongo.db.employees.find_one({"email": email}) if email else None
        req["employee_name"] = emp.get("name", "Unknown") if emp else "Unknown"
        employees_on_leave_list.append(req)
        
    return render_template("interviewer/employees_on_leave.html", employees_on_leave=employees_on_leave_list)

@interviewer_bp.route("/leave_requests")
@admin_required
def leave_requests():
    page = request.args.get('page', 1, type=int)
    per_page = 15
    skip = (page - 1) * per_page

    total_leave_requests = mongo.db.leave_requests.count_documents({"status": "Pending"})
    requests_cursor = mongo.db.leave_requests.find({"status": "Pending"}).sort("start_date", 1).skip(skip).limit(per_page)
    leave_requests_list = []

    for req in requests_cursor:
        req["_id"] = str(req["_id"])
        email = req.get("employee_email")
        emp = mongo.db.employees.find_one({"email": email}) if email else None
        if emp:
            req["employee_name"] = emp.get("name", "Unknown")
            try:
                start = datetime.fromisoformat(req["start_date"])
                end = datetime.fromisoformat(req["end_date"])
                req["days"] = (end - start).days + 1
            except ValueError:
                req["days"] = 0
            req["balance"] = emp.get("leave_allowance", 0) - emp.get("leave_taken", 0)
        else:
            req["employee_name"] = "Unknown"
            req["days"] = 0
            req["balance"] = 0
        leave_requests_list.append(req)

    return render_template("main/leave_requests.html", leave_requests=leave_requests_list, page=page, total_pages=(total_leave_requests // per_page) + (1 if total_leave_requests % per_page else 0))

@interviewer_bp.route("/approve_leave/<string:leave_id>", methods=["POST"])
@admin_required
def approve_leave(leave_id):
    try:
        leave_request = mongo.db.leave_requests.find_one_or_404({"_id": ObjectId(leave_id)})
        
        start_date = leave_request["start_date"]
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            
        end_date = leave_request["end_date"]
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            
        days = (end_date - start_date).days + 1
        mongo.db.leave_requests.update_one({"_id": ObjectId(leave_id)}, {"$set": {"status": "Approved"}})
        
        email = leave_request.get("employee_email")
        if email:
            mongo.db.employees.update_one({"email": email}, {"$inc": {"leave_taken": days}})
        
        send_email_task.delay(
            email_type="leave_approved",
            recipient=email or "unknown@example.com",
            context={
                "name": leave_request.get("employee_name", "Employee"),
                "start_date": str(leave_request["start_date"]),
                "end_date": str(leave_request["end_date"]),
                "days": days,
                "decision": "Approved"
            }
        )
        flash("Leave request approved.", "success")
    except Exception as e:
        current_app.logger.error(f"Error approving leave {leave_id}: {e}")
        flash("Invalid leave request ID.", "danger")
    return redirect(url_for("interviewer.leave_requests"))

@interviewer_bp.route("/deny_leave/<string:leave_id>", methods=["POST"])
@admin_required
def deny_leave(leave_id):
    try:
        leave_request = mongo.db.leave_requests.find_one_or_404({"_id": ObjectId(leave_id)})
        mongo.db.leave_requests.update_one({"_id": ObjectId(leave_id)}, {"$set": {"status": "Denied"}})
        
        send_email_task.delay(
            email_type="leave_denied",
            recipient=leave_request.get("employee_email", "unknown@example.com"),
            context={
                "name": leave_request.get("employee_name", "Employee"),
                "start_date": str(leave_request["start_date"]),
                "end_date": str(leave_request["end_date"]),
                "decision": "Denied"
            }
        )
        flash("Leave request denied.", "success")
    except Exception as e:
        current_app.logger.error(f"Error denying leave {leave_id}: {e}")
        flash("Invalid leave request ID.", "danger")
    return redirect(url_for("interviewer.leave_requests"))

@interviewer_bp.route("/grievance/<string:grievance_id>")
@admin_required
def grievance_details(grievance_id):
    grievance = mongo.db.grievances.find_one({"_id": ObjectId(grievance_id)})
    if not grievance:
        flash("Grievance not found.", "danger")
        return redirect(url_for("interviewer.grievances"))
    flash(f"Loaded confidential grievance report {grievance_id}.", "success")
    return redirect(url_for("interviewer.grievances"))

@interviewer_bp.route("/candidate/<string:applicant_id>/generate_ai_interview", methods=["POST"])
@admin_required
def generate_ai_interview(applicant_id):
    import uuid
    from datetime import datetime
    
    try:
        applicant = mongo.db.applicants.find_one_or_404({"_id": ObjectId(applicant_id)})
        
        token = uuid.uuid4().hex
        mongo.db.interview_links.insert_one({
            "candidate_id": ObjectId(applicant_id),
            "token": token,
            "status": "pending",
            "created_at": datetime.utcnow()
        })
        
        interview_url = f"http://127.0.0.1:5050/?token={token}"
        
        mongo.db.applicants.update_one(
            {"_id": ObjectId(applicant_id)},
            {
                "$set": {
                    "ai_interview_sent_at": datetime.utcnow()
                },
                "$push": {
                    "activity": {
                        "$each": [{
                            "type": "ai_interview_sent", 
                            "author": current_user.name,
                            "timestamp": datetime.utcnow().isoformat(),
                            "link": interview_url
                        }],
                        "$position": 0
                    }
                }
            }
        )
        
        if applicant.get("email"):
            send_email_task.delay(
                email_type="ai_interview",
                recipient=applicant["email"],
                context={
                    "name": applicant.get("name"),
                    "role": applicant.get("role_applied_for"),
                    "link": interview_url
                }
            )
            flash("AI Interview Generation Protocol Triggered! Email securely dispatched.", "success")
        else:
            flash("AI Interview Linked. Note: Candidate email missing, dispatch failed.", "warning")
            
    except Exception as e:
        current_app.logger.error(f"Failed to generate AI Interview link: {e}")
        flash("Failed to trigger AI Interview protocol.", "danger")
        
    return redirect(url_for("interviewer.candidate_profile", applicant_id=applicant_id))