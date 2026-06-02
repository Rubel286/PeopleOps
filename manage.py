# manage.py
import click
from enterprise_app import create_app, mongo
from faker import Faker
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import random
from config import Config
from bson.objectid import ObjectId

app = create_app(Config)
fake = Faker()

# A blueprint for a realistic small-to-mid-scale startup structure
COMPANY_STRUCTURE = {
    "Engineering": {
        "roles": ["Junior Software Engineer", "Software Engineer", "Senior Software Engineer", "Engineering Manager"],
        "intern_role": "Software Engineer Intern",
        "job_description": "to build and scale our core platform using modern technologies.",
        "job_requirements": "Proficiency in Python, experience with Flask or Django, and knowledge of REST APIs."
    },
    "Product & Design": {
        "roles": ["UX/UI Designer", "Product Manager", "Senior Product Manager"],
        "intern_role": "UX/UI Design Intern",
        "job_description": "to craft intuitive and beautiful user experiences for our products.",
        "job_requirements": "A strong portfolio in UI/UX design, proficiency in Figma, and user research skills."
    },
    "Data Science": {
        "roles": ["Data Analyst", "Data Scientist"],
        "intern_role": "Data Analyst Intern",
        "job_description": "to derive actionable insights from our data to drive business decisions.",
        "job_requirements": "Experience with SQL, Python (pandas, scikit-learn), and data visualization tools like Tableau."
    },
    "Sales & Marketing": {
        "roles": ["Sales Development Representative", "Account Executive", "Marketing Specialist"],
        "intern_role": "Marketing Intern",
        "job_description": "to drive revenue growth and expand our market presence.",
        "job_requirements": "Excellent communication skills, experience with CRM software, and a passion for technology sales."
    },
    "Operations": {
        "roles": ["HR Generalist", "Recruiter", "Office Manager"],
        "intern_role": "HR Intern",
        "job_description": "to ensure our company runs smoothly and our team is supported.",
        "job_requirements": "Strong organizational skills and experience in an administrative or HR role."
    },
    "Finance": {
        "roles": ["Accountant", "Financial Analyst"],
        "intern_role": None,
        "job_description": "to manage our financial health and support strategic planning.",
        "job_requirements": "A degree in Finance or Accounting, strong analytical skills, and proficiency with spreadsheets."
    }
}


@app.cli.command("seed-db")
def seed_db():
    """Clears and seeds the database with a fully pre-populated, culturally authentic Indian dataset."""
    fake_in = Faker('en_IN')
    click.secho("Starting comprehensive AI-optimized Indian database seed...", fg="yellow")

    try:
        # 1. Clear existing data
        click.echo("Clearing old data collections...")
        collections_to_clear = ["users", "jobs", "applicants", "employees", "documents", "tasks", "leave_requests", "performance_reviews", "payroll_runs", "payslips", "grievances", "interview_links", "activity_logs"]
        for collection in collections_to_clear:
            mongo.db[collection].delete_many({})

        # 2. Create Admin User
        click.echo("Creating admin user (admin@recruitai.dev)...")
        mongo.db.users.insert_one({
            "email": "admin@recruitai.dev", "name": "System Administrator",
            "password_hash": generate_password_hash("admin"), "role": "admin"
        })

        # 3. Create Realistic Job Postings
        click.echo("Creating realistic job postings...")
        job_ids = []
        jobs_data = []
        depts_with_jobs = list(COMPANY_STRUCTURE.keys())
        for dept_name in depts_with_jobs:
            structure = COMPANY_STRUCTURE[dept_name]
            role = random.choice(structure["roles"])
            job = {
                "title": role, "department": dept_name, "location": random.choice(["Bengaluru", "Hyderabad", "Pune", "Remote"]),
                "type": "Full-time",
                "description": f"We are looking for a talented {role} {structure['job_description']} Join our high-growth team scaling pan-India operations.",
                "requirements": structure['job_requirements'], "status": "Open",
                "date_posted": datetime.utcnow() - timedelta(days=random.randint(5, 30))
            }
            res = mongo.db.jobs.insert_one(job)
            job["_id"] = res.inserted_id
            job_ids.append(res.inserted_id)
            jobs_data.append(job)

        # 4. Create Full-Time Indian Employees (25)
        click.echo("Creating 25 realistic Indian full-time employees...")
        full_time_employees = []
        for i in range(25):
            department = random.choice(list(COMPANY_STRUCTURE.keys()))
            role = random.choice(COMPANY_STRUCTURE[department]["roles"])

            gender = random.choice(["male", "female"])
            name = fake_in.name_male() if gender == "male" else fake_in.name_female()
            
            # Clean name for email logic
            clean_name = name.replace(' ', '.').replace('Mr.', '').replace('Ms.', '').replace('Mrs.', '').strip().lower()
            # Ensure email doesn't have duplicate dots or artifacts
            clean_name = ''.join([c for c in clean_name if c.isalnum() or c == '.']).strip('.')
            email = f"{clean_name}@recruitai.dev"
            
            start_date = fake_in.date_time_between(start_date=datetime(2021, 1, 1), end_date=datetime(2025, 8, 1))
            
            base_sal = random.randint(600000, 3000000) # 6L to 30L INR
            emp_data = {
                "name": name,
                "email": email,
                "phone_number": fake_in.phone_number(),
                "department": department,
                "role": role,
                "start_date": start_date,
                "employee_type": "Full-time",
                "leave_allowance": 24, # Standard Indian SL/PL total
                "leave_taken": random.randint(0, 15),
                "gender": gender,
                "base_salary": base_sal,
                "bonus": int(base_sal * random.uniform(0.05, 0.2)),
                "deductions": int(base_sal * 0.05)
            }
            
            mongo.db.users.insert_one({
                "email": email,
                "name": name,
                "password_hash": generate_password_hash("password"),
                "role": "employee",
                "gender": gender,
                "profile_image": None
            })

            res = mongo.db.employees.insert_one(emp_data)
            emp_data["_id"] = res.inserted_id
            full_time_employees.append(emp_data)

        # 5. Create Applicants (50)
        click.echo("Creating 50 applicants...")
        for _ in range(50):
            job = random.choice(jobs_data)
            gender = random.choice(["male", "female"])
            name = fake_in.name_male() if gender == "male" else fake_in.name_female()
            applicant = {
                "name": name, "email": fake_in.email(),
                "role_applied_for": job["title"], "job_id": job["_id"],
                "resume_path": "fake/path/to/resume.pdf", "status": random.choice(["Applied", "Shortlist", "Interview Scheduled", "Hired", "Rejected"]),
                "match_score": random.randint(50, 99), "predicted_category": job["department"],
                "category_fit_score": random.randint(70, 100),
                "activity": [{"type": "application", "notes": f"Applied for {job['title']} via Portal.", "author": "System", "timestamp": datetime.utcnow() - timedelta(days=random.randint(10, 40))}]
            }
            if applicant["status"] == "Hired":
                applicant["activity"].append({"type": "hire", "notes": "Candidate passed all algorithmic and HR rounds brilliantly.", "author": "Admin", "timestamp": datetime.utcnow() - timedelta(days=2)})
            
            mongo.db.applicants.insert_one(applicant)

        # 6. Global Docs
        click.echo("Creating HR global documents...")
        documents = [
            {"display_name": "Employee Handbook (India) 2026", "description": "Core policies, compliance, and holiday logic.", "file_path": "uploads/company_documents/fake_hb.pdf", "filename": "fake_hb.pdf", "access_level": "All"},
            {"display_name": "Provident Fund & Gratuity Policy", "description": "Retirement and tax deductions breakdown.", "file_path": "uploads/company_documents/fake_pf.pdf", "filename": "fake_pf.pdf", "access_level": "Full-time"}
        ]
        mongo.db.documents.insert_many(documents)

        # 7. Pre-fill Performance Reviews, Tasks, Grievances, Leaves, Payroll
        click.echo("Seeding telemetry (Tasks, Leaves, Grievances, Performance, Payroll runs)...")
        tasks = []
        leave_reqs = []
        grievances = []
        
        # Payroll Runs historical generation
        run_ids = []
        for m in [1, 2, 3]: # Last 3 months
            period = f"2026-0{m}"
            run_id = mongo.db.payroll_runs.insert_one({
                "period": period, "status": "completed", "created_by": "admin@recruitai.dev",
                "created_at": datetime(2026, m, 28), "dry_run": False, "employee_count": len(full_time_employees),
                "total_payout": 0
            }).inserted_id
            run_ids.append((period, run_id))

        for emp in full_time_employees:
            # Generate 2 to 5 pending or active tasks
            for _ in range(random.randint(2, 5)):
                status = random.choice(["Pending", "In Progress", "Completed", "Awaiting Acceptance"])
                title = fake_in.catch_phrase()
                tasks.append({
                    "title": f"Project: {title}",
                    "description": fake_in.text(max_nb_chars=120),
                    "assigner_email": "admin@recruitai.dev",
                    "assignee_email": emp["email"],
                    "status": status,
                    "due_date": datetime.utcnow() + timedelta(days=random.randint(2, 14)),
                    "created_at": datetime.utcnow() - timedelta(days=random.randint(1, 10)),
                    "completed_at": datetime.utcnow() if status == "Completed" else None
                })
                
            # Leaves
            leave_reqs.append({
                "employee_id": emp["_id"],
                "employee_name": emp["name"],
                "leave_type": random.choice(["Sick Leave", "Vacation", "Emergency Leave"]),
                "start_date": datetime.utcnow() + timedelta(days=random.randint(5, 20)),
                "end_date": datetime.utcnow() + timedelta(days=random.randint(22, 25)),
                "reason": "Personal family commitments back home.",
                "status": random.choice(["Pending", "Approved", "Rejected"]),
                "created_at": datetime.utcnow()
            })
            
            # Grievances (Rare constraint)
            if random.random() > 0.8:
                grievances.append({
                    "employee_id": emp["_id"],
                    "employee_name": emp["name"],
                    "subject": "Workspace Issue",
                    "description": "Seeking immediate remote work accommodation due to intense Bengaluru traffic.",
                    "status": "Pending",
                    "created_at": datetime.utcnow() - timedelta(days=random.randint(1, 4))
                })

            # Performance Appraisals
            overall_rating = round(random.uniform(3.0, 4.9), 1)
            mongo.db.performance_reviews.insert_one({
                'employee_id': emp['_id'],
                'reviewer_id': ObjectId(),
                'cycle': '2026-Q1',
                'feedback': "Demonstrates strong ownership and culturally aligns with our rapid growth scale. Exceptional dedication to assigned OKRs.",
                'timestamp': datetime.utcnow() - timedelta(days=random.randint(1, 45)),
                'goals': [
                    {'goal': "Deliver API architectural upgrade phase 1.", 'progress': random.randint(70, 100), 'status': 'In Progress' if random.random() > 0.5 else 'Completed'},
                    {'goal': "Cross-team synchronization and knowledge transfer.", 'progress': 100, 'status': 'Completed'}
                ],
                'ratings': {
                    'skills': random.randint(3, 5),
                    'teamwork': random.randint(3, 5),
                    'overall': overall_rating
                }
            })
            
            # Payslips for historical runs
            for period, run_id in run_ids:
                gross = emp['base_salary'] / 12
                taxes = gross * 0.1 # Flat 10%
                net_pay = gross - taxes
                mongo.db.payslips.insert_one({
                    "run_id": run_id,
                    "employee_id": emp["_id"],
                    "period": period,
                    "gross": round(gross, 2),
                    "taxes": round(taxes, 2),
                    "net_pay": round(net_pay, 2),
                    "created_at": datetime.utcnow()
                })
                # Accrue total payout safely
                mongo.db.payroll_runs.update_one({"_id": run_id}, {"$inc": {"total_payout": net_pay}})

        # Batch Insert Telemetry Arrays
        if tasks: mongo.db.tasks.insert_many(tasks)
        if leave_reqs: mongo.db.leave_requests.insert_many(leave_reqs)
        if grievances: mongo.db.grievances.insert_many(grievances)

        click.secho("Database seeding completed successfully with explicit Indian Telemetry profiles natively instantiated!", fg="green")

    except Exception as e:
        click.secho(f"Error during seeding: {str(e)}", fg="red")
        raise


@app.cli.command("db-align")
def db_align():
    """Aligns Grievance and Leave schemas for UI tracking."""
    click.secho("Executing Database Alignment Script for UI Component Tracking...", fg="yellow")
    
    # 1. Align Grievances Schema
    click.echo("Aligning Grievances...")
    grievances = list(mongo.db.grievances.find({"subject": {"$exists": True}}))
    for g in grievances:
        mongo.db.grievances.update_one(
            {"_id": g["_id"]},
            {"$set": {"type": g["subject"], "timestamp": g["created_at"]},
             "$unset": {"subject": "", "created_at": ""}}
        )

    # 2. Align Leave Requests Schema
    click.echo("Aligning Leave Requests...")
    leaves = list(mongo.db.leave_requests.find({"employee_email": {"$exists": False}}))
    for l in leaves:
        emp = mongo.db.employees.find_one({"_id": l["employee_id"]})
        if emp:
            # Convert datetime objects to string if needed
            sd = l["start_date"]
            ed = l["end_date"]
            # Ensure it's exported as YYYY-MM-DD
            sd_str = sd.strftime("%Y-%m-%d") if isinstance(sd, datetime) else sd
            ed_str = ed.strftime("%Y-%m-%d") if isinstance(ed, datetime) else ed
            
            mongo.db.leave_requests.update_one(
                {"_id": l["_id"]},
                {"$set": {
                    "employee_email": emp["email"],
                    "start_date": sd_str,
                    "end_date": ed_str
                },
                "$unset": {"employee_id": ""}}
            )

    # 3. Force New Hire tags
    click.echo("Forcing 'New Hire' Tags across 5 internal employees...")
    employees = list(mongo.db.employees.find({"employee_type": "Full-time"}))
    for emp in employees[:5]:
        mongo.db.employees.update_one(
            {"_id": emp["_id"]},
            {"$set": {"start_date": datetime.utcnow() - timedelta(days=5)}}
        )

    click.secho("Alignment processing completed efficiently.", fg="green")


@app.cli.command("db-augment")
def db_augment():
    """Augments seeded database with Interns, Active Leaves, Grievances, and Appraisals."""
    click.secho("Starting custom Data Augmentation to fulfill Intern, Grievance, and Appraisal injection requests...", fg="yellow")
    
    # 1. Inject 5 Interns explicitly
    full_time = list(mongo.db.employees.find({"employee_type": "Full-time"}))
    if not full_time:
        click.secho("Error: No employees found to augment. Please run seed-db first.", fg="red")
        return
        
    target_interns = full_time[:5]
    for emp in target_interns:
        mongo.db.employees.update_one(
            {"_id": emp["_id"]},
            {"$set": {
                "employee_type": "Intern",
                "role": "Intern " + emp.get("role", "Developer"),
                "base_salary": random.randint(3, 6) * 100000
            }}
        )
    click.echo("Successfully transitioned 5 standard entities to 'Intern' tracking models.")

    # 2. Inject Active Leaves so the Tracking grid populates
    leave_targets = full_time[5:10]
    for emp in leave_targets:
        mongo.db.leave_requests.insert_one({
            "employee_email": emp.get("email"),
            "start_date": datetime.utcnow().strftime("%Y-%m-%dT00:00:00"),
            "end_date": datetime.utcnow().strftime("%Y-%m-%dT00:00:00"),
            "reason": random.choice(["Sick leave", "Family emergency", "Vacation", "Mental Health Day"]),
            "status": "Approved"
        })
    click.echo("Successfully dispatched 5 Active 'Approved' physical Leave dates mapping the new Grid.")

    # 3. Inject Grievances explicitly
    for emp in full_time[10:15]:
        mongo.db.grievances.insert_one({
            "employee_email": emp.get("email"),
            "employee_name": emp.get("name"),
            "type": random.choice(["Harassment", "Work Environment", "Unfair Treatment", "Technical Issue"]),
            "description": "This is a systematically generated test grievance to validate UI grid mappings.",
            "status": "Under Investigation",
            "submitted_at": datetime.utcnow()
        })

    # 3b. Inject Anonymous Confidential Grievance explicitly
    for emp in full_time[15:17]:
        mongo.db.grievances.insert_one({
            "employee_email": "Anonymous",
            "employee_name": "Anonymous",
            "type": "Confidential",
            "description": "I have an issue with upper management allocating excessive pressure without adequate compensation scaling.",
            "status": "Pending",
            "submitted_at": datetime.utcnow()
        })
    click.echo("Successfully populated standard and confidential Grievance channels.")

    # 4. Inject Performance Appraisals
    for emp in full_time[17:22]:
        mongo.db.performance_reviews.insert_one({
            "employee_id": emp.get("email"),
            "employee_name": emp.get("name"),
            "reviewer_email": "admin@recruitai.dev",
            "status": "Completed", 
            "summary": "Consistently exceeds expectation margins during crunch time.",
            "metrics": {"code_quality": 5, "teamwork": 4, "communication": 5, "delivery": 4},
            "score": 4.5,
            "submitted_at": datetime.utcnow()
        })
    click.secho("Successfully resolved PR injection pipelines. System database augmented securely!", fg="green")


@app.cli.command("db-fix-gender")
def db_fix_gender():
    """Updates employee genders in DB based on their first names using gender-guesser."""
    click.secho("Running Gender cleanup/detection on employee profiles...", fg="yellow")
    try:
        import gender_guesser.detector as gender
    except ImportError:
        click.secho("Error: 'gender-guesser' package not found. Install it first.", fg="red")
        return

    detector = gender.Detector(case_sensitive=False)
    updated_count = 0
    for emp in mongo.db.employees.find():
        first_name = emp["name"].split()[0]
        g = detector.get_gender(first_name)

        target_gender = None
        if g in ("male", "mostly_male"):
            target_gender = "male"
        elif g in ("female", "mostly_female"):
            target_gender = "female"

        if target_gender:
            mongo.db.employees.update_one(
                {"_id": emp["_id"]},
                {"$set": {"gender": target_gender}}
            )
            updated_count += 1

    click.secho(f"Gender cleanup done. Successfully detected and updated {updated_count} employee genders.", fg="green")


@app.cli.command("db-reparse-resumes")
def db_reparse_resumes():
    """Extracts PDF text and runs NLP intelligence reparsing on all applicant profiles."""
    click.secho("Starting batch resume reparsing logic...", fg="yellow")
    
    # Lazy imports to keep CLI fast
    try:
        from enterprise_app.utils import extract_text_from_pdf, extract_links
        from enterprise_app.services.nlp_service import analyze_resume_full
    except ImportError as e:
        click.secho(f"Error importing analysis utilities: {e}", fg="red")
        return

    applicants = list(mongo.db.applicants.find())
    click.echo(f"[{len(applicants)}] applicant profiles found to process...")
    
    success_count = 0
    for c in applicants:
        if not c.get("resume_path"):
            continue
            
        job_id = c.get("job_id")
        if not job_id:
            continue
            
        job = mongo.db.jobs.find_one({"_id": ObjectId(job_id)})
        if not job:
            continue
            
        click.echo(f"Reparsing: {c['name']}")
        try:
            resume_text = extract_text_from_pdf(c["resume_path"])
            if not resume_text:
                raise ValueError("Empty extraction or PDF read failure")
                
            full_job_desc = f"{job.get('description', '')} {job.get('requirements', '')}"
            analysis = analyze_resume_full(resume_text, full_job_desc, job.get("title", ""))
            
            mongo.db.applicants.update_one(
                {"_id": c["_id"]},
                {"$set": {
                    "category_fit_score": analysis.get("score"),
                    "matched_categories": analysis.get("matched_categories"),
                    "missing_categories": analysis.get("missing_categories"),
                    "extracted_skills": analysis.get("skills"),
                    "explanation": f"Score synthesized via heuristics: {len(analysis.get('matched_categories', []))} matching domain categories with {analysis.get('years_of_experience')} years experience mapped. System Recommendation: {analysis.get('recommendation')}",
                    "recommendation": analysis.get("recommendation"),
                    "years_of_experience": analysis.get("years_of_experience"),
                    "education": analysis.get("education"),
                    "experience_preview": analysis.get("experience"),
                    "extracted_links": extract_links(c["resume_path"]),
                    "match_score": analysis.get("score"),
                }}
            )
            success_count += 1

        except Exception as e:
            click.secho(f"Error parsing {c['name']}: {e}", fg="red")

    click.secho(f"Reparsing completed. Successfully parsed and updated {success_count} applicant profiles.", fg="green")