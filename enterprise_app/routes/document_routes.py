from flask import Blueprint, render_template, send_from_directory, current_app, request, abort, flash, redirect, url_for
from flask_login import login_required, current_user
from enterprise_app import mongo
from bson.objectid import ObjectId
from datetime import datetime
import os
from enterprise_app.decorators import employee_required, admin_required

document_bp = Blueprint("document", __name__)

def log_activity(action, details):
    log_entry = {
        "user_email": current_user.email,
        "action": action,
        "details": details,
        "ip_address": request.remote_addr,
        "timestamp": datetime.utcnow()
    }
    mongo.db.activity_logs.insert_one(log_entry)

def get_allowed_access_levels():
    if current_user.role == 'admin':
        return ["All", "Intern", "Full-time"]
    
    employee = mongo.db.employees.find_one({"email": current_user.email})
    if not employee:
        return []
    
    allowed = ["All"]
    emp_type = employee.get("employee_type")
    if emp_type == 'Intern':
        allowed.append("Intern")
    elif emp_type in ['Full-time', 'Contract']:
        allowed.append("Full-time")
    
    return allowed

@document_bp.route("/")
@employee_required
def library():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    skip = (page - 1) * per_page

    query = {"access_level": {"$in": get_allowed_access_levels()}}
    total_docs = mongo.db.documents.count_documents(query)
    documents = list(mongo.db.documents.find(query).sort("display_name", 1).skip(skip).limit(per_page))
    return render_template("main/document_library.html", documents=documents, page=page, total_pages=(total_docs // per_page) + (1 if total_docs % per_page else 0))

@document_bp.route("/view/<string:doc_id>")
@employee_required
def view_document(doc_id):
    document = mongo.db.documents.find_one({"_id": ObjectId(doc_id)})
    if not document:
        flash("Document not found.", "danger")
        return redirect(url_for("document.library"))

    if document.get("access_level") not in get_allowed_access_levels():
        abort(403)

    project_root = os.path.abspath(os.path.join(current_app.root_path, '..'))
    file_path = os.path.join(project_root, document["file_path"].lstrip('/'))
    
    if not os.path.exists(file_path):
        flash("File not found on server.", "danger")
        return redirect(url_for("document.library"))

    log_activity("view_document", {"document_name": document["display_name"], "document_id": str(document["_id"])})
    
    return send_from_directory(os.path.dirname(file_path), os.path.basename(file_path), mimetype='application/pdf')

@document_bp.route("/download/<string:doc_id>")
@employee_required
def download_document(doc_id):
    document = mongo.db.documents.find_one({"_id": ObjectId(doc_id)})
    if not document:
        flash("Document not found.", "danger")
        return redirect(url_for("document.library"))

    if document.get("access_level") not in get_allowed_access_levels():
        abort(403)

    project_root = os.path.abspath(os.path.join(current_app.root_path, '..'))
    file_path = os.path.join(project_root, document["file_path"].lstrip('/'))
    
    if not os.path.exists(file_path):
        flash("File not found on server.", "danger")
        return redirect(url_for("document.library"))

    log_activity("download_document", {"document_name": document["display_name"], "document_id": str(document["_id"])})

    return send_from_directory(os.path.dirname(file_path), os.path.basename(file_path), as_attachment=True, download_name=document.get("display_name", "document.pdf"))