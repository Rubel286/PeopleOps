# PeopleOps - Enterprise HRMS & AI Recruitment Management System

**Project Overview**

PeopleOps is a comprehensive Enterprise Human Resource Management System (HRMS) and AI-powered Recruitment Platform designed to streamline hiring, employee management, payroll operations, performance tracking, and workforce administration.

The platform combines Machine Learning-powered resume screening, intelligent candidate evaluation, automated HR workflows, payroll processing, employee analytics, and an AI assistant to help organizations manage their workforce efficiently from a single dashboard.

---

## Features

### Recruitment & Hiring

- ✅ AI-powered resume screening and classification
- ✅ Automated PDF resume parsing and text extraction
- ✅ Resume-to-job matching and candidate scoring
- ✅ Job posting and applicant tracking
- ✅ Candidate profile management
- ✅ Interview scheduling and communication workflows

### Employee Management

- ✅ Employee directory and profile management
- ✅ Dedicated dashboards for administrators, employees, and interns
- ✅ Employee onboarding workflows
- ✅ Contract tracking and management
- ✅ Leave request and approval system

### Payroll & Finance

- ✅ Payroll management and processing
- ✅ Tax calculations and payroll logs
- ✅ Automated PDF payslip generation
- ✅ Employee payslip portal
- ✅ Financial reporting tools

### Performance Management

- ✅ Goal setting and progress tracking
- ✅ Performance reviews and appraisals
- ✅ Employee performance analytics
- ✅ Historical performance records

### Communication & Automation

- ✅ Automated email notifications
- ✅ Background task processing using Celery
- ✅ Asynchronous workflow execution
- ✅ AI-powered PeopleOps Assistant using Google Gemini

### Operations & Analytics

- ✅ Employee grievance management
- ✅ Workforce analytics dashboard
- ✅ Organizational insights and reporting
- ✅ Leave tracking and monitoring

---

## Technology Stack

### Backend

- Python
- Flask
- Celery
- Redis

### Database

- MongoDB

### Machine Learning & AI

- Scikit-Learn
- Joblib
- Google Gemini API

### Frontend

- HTML5
- CSS3
- JavaScript
- Jinja2

### Reporting & Utilities

- ReportLab
- PyMuPDF

---

## Project Structure

```plaintext
PeopleOps/
│
│── enterprise_app/
│   ├── routes/                # Flask route blueprints (Auth, Finance, Performance, etc.)
│   ├── services/              # Business logic (Appraisals, Chatbot, Email, NLP matching)
│   ├── static/                # CSS styling, brand assets, and user avatars
│   ├── templates/             # HTML templates (Layouts, Emails, Dashboards)
│   ├── tasks.py               # Background Celery task definitions
│   ├── utils.py               # Shared utility functions (PDF generation, logging, math)
│   └── __init__.py            # Flask application factory and Celery initialization
│── models/                    # Trained Machine Learning models and metrics reports
│── tools/                     # Development utilities
│── config.py                  # Global application configurations and environment maps
│── manage.py                  # Database seeders, schema alignments, and CLI utilities
│── training.py                # Pipeline script to retrain the SVM resume classifier
│── run.py                     # Entrypoint script to start the Flask application
│── requirements.txt           # Explicitly pinned application dependencies
│── start-all.bat              # Batch file to start Redis, Celery, and Flask simultaneously
│── UpdatedResumeDataSet.csv   # Dataset used to train the resume classification models
│── .gitignore                 
└── README.md
```

---

## Prerequisites

Make sure the following software is installed before running the project:

- Redis

### Verify Installation

```bash
redis-server --version
```

---

## Installation & Setup

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/Rubel286/PeopleOps.git
cd PeopleOps
```

### 2️⃣ Create & Activate Virtual Environment

#### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

#### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

### 4️⃣ Configure Environment Variables

Create a `.env` file in the project root:

```env
SECRET_KEY="your-key"

MONGO_URI=mongodb://127.0.0.1:27017/recruitmentDB

MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=1
MAIL_USERNAME="your-email"
MAIL_PASSWORD="your-password"

CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0

GEMINI_API_KEY="your-key"
```

### 5️⃣ Start Redis

```bash
redis-server
```

### 6️⃣ Database Initialization

```bash
flask --app manage.py seed-db
```

### 7️⃣ Run the Application

#### Quick Start (Windows)

```bash
start-all.bat
```

#### Manual Startup

Start Celery Worker:

```bash
python -m celery -A enterprise_app.celery worker -P solo --loglevel=info
```

Start Flask Application:

```bash
python run.py
```

## Access the Application

Open your browser and navigate to:

```text
http://127.0.0.1:5000
```

## Default Login Credentials

After running `flask --app manage.py seed-db`, you can immediately log in to the portal using these default testing accounts.

### Administrative / Recruiter Access

- **Email:** `admin@peopleops.dev`
- **Password:** `admin`

### Employee Portal Access

- **Email:** `[first_name].[last_name]@peopleops.dev`
  - Example: `aravind.swamy@peopleops.dev`
- **Password:** `password`

---

## Screenshots

### Admin Dashboard
![Admin Dashboard](screenshots/admin-dashboard.png)

### Candidate Pipeline
![Candidate Pipeline](screenshots/candidate-pipeline.png)

### Candidate Profile
![Candidate Profile](screenshots/candidate-profile.png)

### Employee Dashboard
![Employee Dashboard](screenshots/employee-dashboard.png)

### Grievance Management
![Grievance Management](screenshots/grievance-management.png)

### Leave Requests
![Leave Requests](screenshots/leave-requests.png)

---

## Important

This project uses Google Gemini API.

Get your API key from:

https://aistudio.google.com/app/apikey

---

## License

This project is licensed under the MIT License.

See the LICENSE file for details.