from flask import Blueprint, render_template, request, redirect, url_for, current_app, flash, abort
from werkzeug.utils import secure_filename
import os
from enterprise_app import mongo
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash
from enterprise_app.utils import validate_onboarding_token, validate_file

onboarding_bp = Blueprint("onboarding", __name__)

@onboarding_bp.route("/<string:applicant_id>")
def portal(applicant_id):
    token = request.args.get('token')
    if not validate_onboarding_token(applicant_id, token):
        abort(403)
    employee = mongo.db.applicants.find_one_or_404({"_id": ObjectId(applicant_id)})
    return render_template("main/onboarding.html", employee=employee, token=token)

@onboarding_bp.route("/upload_docs/<string:applicant_id>", methods=["POST"])
def upload_docs(applicant_id):
    token = request.form.get('token')
    if not validate_onboarding_token(applicant_id, token):
        abort(403)

    applicant = mongo.db.applicants.find_one_or_404({"_id": ObjectId(applicant_id)})

    files = request.files.getlist("documents")
    target_folder = os.path.join(current_app.config["UPLOAD_FOLDER_ONBOARDING"], applicant_id)
    os.makedirs(target_folder, exist_ok=True)

    doc_paths = []
    for f in files:
        if f and f.filename:
            if not validate_file(f, ['application/pdf']):
                flash("Invalid file type. Only PDF allowed.", "danger")
                return redirect(url_for("onboarding.portal", applicant_id=applicant_id, token=token))
            filename = secure_filename(f.filename)
            path = os.path.join(target_folder, filename)
            f.save(path)
            doc_paths.append(path)

    mongo.db.applicants.update_one({"_id": ObjectId(applicant_id)}, {"$set": {"onboarding_docs": doc_paths}})

    # This part of your code creates a duplicate employee if you hire them from the dashboard
    # and then they complete the onboarding. You may want to refactor this to an `update_one`
    # with `upsert=True` in the future.
    mongo.db.users.update_one(
        {'email': applicant['email']},
        {'$set': {
            'name': applicant['name'],
            'password_hash': generate_password_hash('change_me_please'),
            'role': 'employee'
        }},
        upsert=True
    )
    employee_data = {
        'email': applicant['email'],
        'name': applicant['name'],
        'department': applicant.get('predicted_category', 'Unassigned'),
        'role': applicant['role_applied_for'],
        'employee_type': 'Full-time',  # Assume, or from job
        'start_date': datetime.utcnow(),
        'leave_allowance': 20,
        'leave_taken': 0
    }
    mongo.db.employees.update_one({'email': applicant['email']}, {'$set': employee_data}, upsert=True)
    mongo.db.applicants.update_one({"_id": ObjectId(applicant_id)}, {"$set": {"status": "Onboarded"}})

    return redirect(url_for("main.success", message="Onboarding documents uploaded successfully!"))