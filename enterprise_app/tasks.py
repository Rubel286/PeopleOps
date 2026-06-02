from celery import shared_task
from enterprise_app import celery, mongo, create_app
from config import Config
from enterprise_app.utils import analyze_resume, send_email
from bson.objectid import ObjectId
from datetime import datetime
from enterprise_app.utils import generate_payslip_pdf

def get_app():
    """
    Create Flask app and push app context
    so MongoDB, Mail, etc. are available in Celery.
    """
    app = create_app(Config)
    app.app_context().push()
    return app


@shared_task(bind=True, max_retries=3)
def process_resume_analysis(self, applicant_id: str, resume_path: str, job_id: str):
    """
    Process resume analysis with retries and update applicant data.
    """
    get_app()  # 🔑 ensures mongo is initialized

    try:
        job = mongo.db.jobs.find_one({"_id": ObjectId(job_id)})
        if not job:
            raise ValueError("Job not found")

        from enterprise_app.utils import extract_text_from_pdf, extract_links
        from enterprise_app.services.nlp_service import analyze_resume_full
        
        resume_text = extract_text_from_pdf(resume_path)
        if not resume_text:
            raise ValueError("Could not extract text from PDF.")
            
        full_job_desc = f"{job.get('description', '')} {job.get('requirements', '')}"
        analysis = analyze_resume_full(resume_text, full_job_desc, job.get("title", ""))

        mongo.db.applicants.update_one(
            {"_id": ObjectId(applicant_id)},
            {
                "$set": {
                    "status": "Applied",
                    "predicted_category": job.get("department", "General"),
                    "category_fit_score": analysis.get("score"),
                    "matched_categories": analysis.get("matched_categories"),
                    "missing_categories": analysis.get("missing_categories"),
                    "extracted_skills": analysis.get("skills"),
                    "explanation": f"Score synthesized via heuristics: {len(analysis.get('matched_categories', []))} matching domain categories with {analysis.get('years_of_experience')} years experience mapped. System Recommendation: {analysis.get('recommendation')}",
                    "recommendation": analysis.get("recommendation"),
                    "years_of_experience": analysis.get("years_of_experience"),
                    "education": analysis.get("education"),
                    "experience_preview": analysis.get("experience"),
                    "extracted_links": extract_links(resume_path),
                    "match_score": analysis.get("score"),
                },
                "$push": {
                    "activity": {
                        "$each": [{
                            "type": "analysis_completed",
                            "timestamp": datetime.utcnow().isoformat(),
                            "message": "Resume analysis completed."
                        }],
                        "$position": 0
                    }
                }
            }
        )

    except Exception as e:
        mongo.db.applicants.update_one(
            {"_id": ObjectId(applicant_id)},
            {
                "$set": {
                    "status": "Error",
                    "error_message": str(e)
                },
                "$push": {
                    "activity": {
                        "$each": [{
                            "type": "error",
                            "timestamp": datetime.utcnow().isoformat(),
                            "message": f"Analysis failed: {str(e)}"
                        }],
                        "$position": 0
                    }
                }
            }
        )
        self.retry(countdown=60, max_retries=3)
        raise


@celery.task(bind=True, max_retries=0)
def send_email_task(self, email_type: str, recipient: str, context: dict):
    """
    Unified Celery Task to background all platform emails securely.
    """
    import re
    print(f"[TRACE] send_email_task started | email_type={email_type} | recipient={recipient}")
    
    # Validate Email Format
    if not recipient or not isinstance(recipient, str) or not re.match(r"[^@]+@[^@]+\.[^@]+", recipient):
        print(f"[Celery] Invalid email rejected: {recipient}")
        return False

    # Ensure Flask app + extensions (mail, config) are available
    get_app()

    from enterprise_app.services.email_service import send_unified_email

    try:
        result = send_unified_email(email_type, recipient, context)

        if not result:
            print(f"[Celery] Email sending failed via service for {recipient}")
            return False

    except Exception as e:
        # Log error securely without triggering infinite retries
        print(f"[Celery] Email task failed for {recipient}: {e}")
        return False
        
    return True