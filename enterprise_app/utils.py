import os
import fitz  # PyMuPDF
import joblib
from pathlib import Path
import re
from .constants import SKILLS_DB
from flask_mail import Message
from enterprise_app import mail, mongo
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from flask import current_app
from flask_login import current_user
import uuid
import mimetypes
from bson.objectid import ObjectId
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io
from flask import session
from flask_login import current_user
from bson.decimal128 import Decimal128

def safe_number(value):
    if value is None:
        return 0.0
    if isinstance(value, Decimal128):
        return float(value.to_decimal())
    if isinstance(value, (int, float)):
        return float(value)
    try:
        if isinstance(value, str):
            val = value.replace("$", "").replace(",", "")
            if not val.strip():
                return 0.0
            return float(val)
        return float(value)
    except (ValueError, TypeError):
        return 0.0

def sanitize_numbers(data):
    if isinstance(data, dict):
        return {k: sanitize_numbers(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_numbers(i) for i in data]
    elif isinstance(data, Decimal128):
        from flask import current_app
        try:
            current_app.logger.warning("Decimal128 detected before render! Auto-converting to float via sanitize_numbers global handler.")
        except:
            pass
        return float(data.to_decimal())
    return data

def get_active_role():
    if current_user.is_authenticated:
        return current_user.role
    return None

# DEFERRED MODEL INITIALIZATION
MODEL_PATH = Path("models/resume_pipeline.joblib")
pipeline = None

def init_ml_model(app):
    """Loads the ML model and logs its status within the app context."""
    global pipeline
    with app.app_context():
        if MODEL_PATH.exists():
            pipeline = joblib.load(MODEL_PATH)
            current_app.logger.info("Resume categorizer model loaded successfully.")
        else:
            current_app.logger.warning(
                f"ML model not found at '{MODEL_PATH}'. "
                "Resume analysis will be disabled. Run 'python training.py' to create it."
            )

def extract_text_from_pdf(pdf_path: str) -> str:
    if not Path(pdf_path).exists():
        return ""
    try:
        doc = fitz.open(pdf_path)
        text = "".join(page.get_text() for page in doc)
        doc.close()
        return text
    except Exception as e:
        current_app.logger.error(f"Error extracting text from {pdf_path}: {e}")
        return ""

def extract_links(pdf_path: str) -> dict:
    links = {"linkedin": "", "github": "", "portfolio": "", "other": []}
    if not Path(pdf_path).exists():
        return links
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            for link in page.get_links():
                uri = link.get("uri", "")
                if "linkedin.com" in uri: links["linkedin"] = uri
                elif "github.com" in uri: links["github"] = uri
                elif any(kw in uri for kw in ["portfolio", "dribbble", "behance"]): links["portfolio"] = uri
                else: links["other"].append(uri)
        doc.close()
    except Exception as e:
        current_app.logger.error(f"Error extracting links from {pdf_path}: {e}")
    return links

def analyze_resume(file_path: str, job_description: str) -> dict:
    raise DeprecationWarning("analyze_resume is deprecated in favor of tasks natively calling analyze_resume_full")
    
    raw_resume_text = extract_text_from_pdf(file_path)
    if not raw_resume_text:
        return {"error": "Could not extract text from PDF."}

    # Clean text purely for the ML Predictor Model (which expects lowercase squashed text)
    ml_text = re.sub(r'http\S+', '', raw_resume_text)
    ml_text = re.sub(r'\S*@\S*\s?', '', ml_text)
    ml_text = re.sub(r'[^\w\s]', '', ml_text)
    ml_text = re.sub(r'\s+', ' ', ml_text).strip().lower()

    # Use our new strict ONE pipeline backend
    from enterprise_app.services.nlp_service import analyze_resume_full
    nlp_results = analyze_resume_full(raw_resume_text, job_description)

    predicted_category = pipeline.predict([ml_text])[0] if pipeline else "General"
    try:
        if pipeline:
            proba = pipeline.predict_proba([ml_text])
            category_fit_score = round(np.max(proba) * 100)
        else:
            category_fit_score = nlp_results["score"] 
    except (AttributeError, ValueError):
        # Fallback category fit strongly relies on the actual resume 100-point engine instead of constant 100
        category_fit_score = nlp_results["score"]

    return {
        "predicted_category": predicted_category,
        "category_fit_score": category_fit_score,
        "years_of_experience": nlp_results["years_of_experience"],
        "education": nlp_results["education"],
        "extracted_links": extracted_links,
        "match_score": nlp_results["score"],
        "matched_skills": nlp_results["matched_skills"],
        "missing_skills": nlp_results["missing_skills"],
        "recommendation": nlp_results["recommendation"],
        "all_skills_detected": nlp_results["skills"],
        "experience_preview": nlp_results["experience"]
    }

def send_email(to: str, subject: str, template: str, attachments: list = None):
    try:
        msg = Message(subject, recipients=[to], html=template)

        if attachments:
            for attachment_data in attachments:
                if not attachment_data:
                    continue
                if not isinstance(attachment_data, (list, tuple)) or len(attachment_data) != 3:
                    continue
                filename, content_type, data = attachment_data
                msg.attach(filename=filename, content_type=content_type, data=data)

        if current_app.debug and current_app.config.get('MAIL_FILE_PATH'):
            file_path = current_app.config['MAIL_FILE_PATH']
            os.makedirs(file_path, exist_ok=True)
            eml_path = os.path.join(file_path, f"{uuid.uuid4()}.eml")
            with open(eml_path, "w", encoding="utf-8") as f:
                f.write(msg.as_string())
        else:
            mail.send(msg)

        return True

    except Exception as e:
        import traceback
        traceback.print_exc()
        current_app.logger.error(f"Failed to send email to {to}: {e}")
        return False

def validate_file(file, allowed_types=['application/pdf']):
    mime, _ = mimetypes.guess_type(file.filename)
    return mime in allowed_types

def generate_onboarding_token(applicant_id):
    token = uuid.uuid4().hex
    mongo.db.applicants.update_one({'_id': ObjectId(applicant_id)}, {'$set': {'onboarding_token': token}})
    return token

def validate_onboarding_token(applicant_id, token):
    applicant = mongo.db.applicants.find_one({'_id': ObjectId(applicant_id)})
    return applicant and applicant.get('onboarding_token') == token

def log_activity(action, details=None, user_email=None):
    """Log important actions for transparency/audit."""
    user_email = user_email or (current_user.email if current_user.is_authenticated else 'anonymous')
    log_entry = {
        "user_email": user_email,
        "action": action,
        "details": details or {},
        "ip_address": request.remote_addr if 'request' in globals() else 'unknown',
        "timestamp": datetime.utcnow()
    }
    mongo.db.activity_logs.insert_one(log_entry)
    current_app.logger.info(f"Action logged: {action} by {user_email}")

def calculate_payroll(employee):
    """Simple payroll calc: base + bonus - deductions - taxes (10% flat)."""
    base_salary = safe_number(employee.get('base_salary', 0))
    bonus = safe_number(employee.get('bonus', 0))
    deductions = safe_number(employee.get('deductions', 0))
    gross = base_salary + bonus - deductions
    taxes = gross * 0.10  # Flat 10% tax for demo
    net_pay = gross - taxes
    return {
        'gross': gross,
        'taxes': taxes,
        'net_pay': net_pay,
        'period': datetime.utcnow().strftime('%Y-%m')
    }

def generate_payslip_pdf(employee, payroll_data):
    """Generate PDF payslip."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.drawString(100, 750, f"Payslip for {employee['name']}")
    c.drawString(100, 730, f"Period: {payroll_data['period']}")
    c.drawString(100, 710, f"Gross: ${payroll_data['gross']:.2f}")
    c.drawString(100, 690, f"Taxes: ${payroll_data['taxes']:.2f}")
    c.drawString(100, 670, f"Net Pay: ${payroll_data['net_pay']:.2f}")
    c.save()
    buffer.seek(0)
    return buffer.getvalue()