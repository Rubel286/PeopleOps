import sys
import os
import pprint

# Add project root directory to path for imports to work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enterprise_app.services.nlp_service import analyze_resume_full
from enterprise_app.utils import extract_text_from_pdf

# Folder containing all resume PDFs
current_dir = os.getcwd()
resumes_folder = os.path.join(current_dir, "resumes")

# Auto-fallback to parent directory if run from inside tools/
if not os.path.exists(resumes_folder) and os.path.basename(current_dir) == "tools":
    resumes_folder = os.path.join(os.path.abspath(".."), "resumes")

# Check if resumes folder exists
if not os.path.exists(resumes_folder):
    print("❌ Error: Please create a 'resumes' folder in the MainFrame_ENTERPRISE root folder.")
    sys.exit(1)

# Get all PDF files inside resumes folder
resume_files = [f for f in os.listdir(resumes_folder) if f.lower().endswith(".pdf")]

# Check if any PDFs are found
if not resume_files:
    print(f"❌ Error: No PDF resumes found inside the folder '{resumes_folder}'.")
    sys.exit(1)

job_desc = "Looking for a Data Analyst with 3 years of experience in SQL, Python, and Tableau."

# Process each resume
for resume_filename in resume_files:
    resume_path = os.path.join(resumes_folder, resume_filename)

    print(f"\n📄 Extracting text from {resume_filename}...")
    resume_text = extract_text_from_pdf(resume_path)

    if not resume_text:
        print(f"❌ Failed to extract structural text from {resume_filename}. It may be an image scan.")
        continue

    print("🧠 Running NLP Intelligence algorithms...\n")
    result = analyze_resume_full(resume_text, job_desc, "Data Analyst")

    print(f"--- 📊 EXTRACTION REPORT FOR: {resume_filename} ---")
    pprint.pprint(result)
    print("-" * 80)
