import os
from flask import render_template, current_app
from flask_mail import Message
from ics import Calendar, Event
import datetime
import uuid
import traceback

EMAIL_CONFIG = {
    "application": {
        "subject": "Your Application has been Received",
        "template": "emails/confirmation_email.html"
    },
    "leave_approved": {
        "subject": "Leave Request Approved",
        "template": "emails/leave_status_email.html"
    },
    "leave_denied": {
        "subject": "Leave Request Denied",
        "template": "emails/leave_status_email.html"
    },
    "payslip": {
        "subject": "Your Payslip is Ready",
        "body": "Your payslip for {period} is attached."
    },
    "interview": {
        "subject": "Interview Scheduled",
        "template": "emails/interview_email.html"
    },
    "hire": {
        "subject": "Congratulations on Your Offer!",
        "template": "emails/hire_email.html"
    },
    "reject": {
        "subject": "Update on your application",
        "template": "emails/reject_email.html"
    },
    "ai_interview": {
        "subject": "Invitation: AI Technical Screen Scheduled",
        "template": "emails/ai_interview_email.html"
    }
}

def build_email(email_type: str, recipient: str, context: dict) -> Message:
    if email_type not in EMAIL_CONFIG:
        raise ValueError(f"Invalid email type: {email_type}")
        
    config = EMAIL_CONFIG[email_type]
    subject = config["subject"]
    
    msg = Message(subject, recipients=[recipient])
    
    if config.get("template"):
        msg.html = render_template(config["template"], **context)
    elif config.get("body"):
        msg.body = config["body"].format(**context)
        
    # Handle specific attachments based on type
    if email_type == "payslip":
        pdf_data = context.get("pdf_data")
        period = context.get("period")
        if pdf_data and period:
            # Reconstruct bytes if it was serialized over celery as hex or base64
            if isinstance(pdf_data, str):
                try:
                    import base64
                    pdf_data = base64.b64decode(pdf_data)
                except:
                    pass
            msg.attach(f"payslip_{period}.pdf", "application/pdf", pdf_data)
            
    elif email_type == "interview":
        interview_date = context.get("interview_date")
        if interview_date:
            c = Calendar()
            e = Event()
            e.name = f"Interview for {context.get('role', 'Position')}"
            
            # Make sure it's a datetime object
            if isinstance(interview_date, str):
                try:
                    interview_date = datetime.datetime.fromisoformat(interview_date)
                except:
                    pass
                    
            e.begin = interview_date
            e.duration = datetime.timedelta(hours=1)
            e.description = "Technical Interview via PeopleOps Enterprise"
            c.events.add(e)
            
            ics_content = str(c)
            msg.attach("invite.ics", "text/calendar", ics_content.encode('utf-8'))
            
    return msg

def send_unified_email(email_type: str, recipient: str, context: dict):
    from enterprise_app import mail, mongo
    from datetime import datetime
    
    try:
        msg = build_email(email_type, recipient, context)
        
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
        traceback.print_exc()
        current_app.logger.error(f"Failed to send '{email_type}' email to {recipient}: {e}")
        
        # Log to audit_logs
        try:
            mongo.db.audit_logs.insert_one({
                "action": "email_send_failed",
                "email_type": email_type,
                "recipient": recipient,
                "error": str(e),
                "timestamp": datetime.utcnow()
            })
        except Exception as mongo_err:
            current_app.logger.error(f"Failed to write to audit_logs: {mongo_err}")
            
        return False
