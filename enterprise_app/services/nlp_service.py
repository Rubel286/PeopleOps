import re
import numpy as np
import datetime
from enterprise_app.constants import SKILLS_DB

SKILL_MAP = {
    "snowflake": "sql",
    "mysql": "sql",
    "postgresql": "sql",
    "oracle": "sql",
    "looker": "data_visualization",
    "power bi": "data_visualization",
    "tableau": "data_visualization",
    "pandas": "python",
    "numpy": "python",
    "scikit-learn": "ml",
    "pytorch": "ml",
    "tensorflow": "ml",
    "keras": "ml",
    "react": "frontend",
    "angular": "frontend",
    "vue": "frontend",
    "node": "backend",
    "django": "backend",
    "flask": "backend",
    "spring": "backend",
    "aws": "cloud",
    "gcp": "cloud",
    "azure": "cloud",
    "docker": "devops",
    "kubernetes": "devops",
    "ci/cd": "devops",
    "excel": "analysis"
}

ROLE_CATEGORIES = {
    "data_handling": ["sql", "databases", "mongodb", "cassandra"],
    "analysis": ["python", "excel", "r", "sas", "analysis"],
    "visualization": ["data_visualization", "tableau", "power bi", "looker"],
    "machine_learning": ["ml", "pytorch", "tensorflow", "scikit-learn"],
    "frontend_dev": ["frontend", "react", "angular", "vue", "javascript", "typescript", "html", "css"],
    "backend_dev": ["backend", "python", "java", "node", "django", "flask", "c#", "c++", "ruby"],
    "cloud_ops": ["cloud", "devops", "aws", "gcp", "azure", "docker", "kubernetes", "ci/cd"]
}

DEFAULT_ROLE_SKILLS = {
    "data analyst intern": ["sql", "python", "excel", "tableau", "power bi"]
}

def normalize_skill(skill: str) -> str:
    lower_skill = skill.lower()
    return SKILL_MAP.get(lower_skill, lower_skill)

def get_categories_for_skills(skills: list) -> set:
    categories = set()
    normalized = {normalize_skill(s) for s in skills}
    for cat_name, cat_skills in ROLE_CATEGORIES.items():
        if any(s in normalized for s in cat_skills):
            categories.add(cat_name)
    return categories

def extract_sections(text: str) -> dict:
    sections = {"skills": "", "education": "", "experience": ""}
    current_section = None
    for line in text.split('\n'):
        clean_line = line.strip().upper()
        if not clean_line:
            continue
        if ("EDUCATION" in clean_line or "ACADEMIC" in clean_line) and len(clean_line) < 25:
            current_section = "education"
            continue
        elif ("EXPERIENCE" in clean_line or "WORK HISTORY" in clean_line or "EMPLOYMENT" in clean_line) and len(clean_line) < 25:
            current_section = "experience"
            continue
        elif ("SKILLS" in clean_line or "TECHNOLOGIES" in clean_line) and len(clean_line) < 25:
            current_section = "skills"
            continue
            
        if current_section:
            sections[current_section] += line + "\n"
    return sections

def extract_years_experience(text: str) -> float:
    current_year = datetime.datetime.utcnow().year
    total_dates_years = 0.0
    
    pattern = r'(19\d{2}|20[012]\d)\s*(?:-|to)\s*(19\d{2}|20[012]\d|present|current|now)'
    matches = re.findall(pattern, text, re.IGNORECASE)
    
    for start, end in matches:
        start_year = int(start)
        if end.lower() in ['present', 'current', 'now']:
            end_year = current_year
        else:
            end_year = int(end)
        
        if end_year >= start_year:
            total_dates_years += (end_year - start_year + 1)
            
    exp_matches = re.findall(r'(\d+)\s*(?:years?|yrs)', text, re.IGNORECASE)
    explicit_years = sum(int(num) for num in exp_matches)
    
    return max(total_dates_years, explicit_years)

def extract_exact_skills(text: str) -> list:
    """Extract skills dynamically using explicit string checking padded by whitespace."""
    found_skills = set()
    text_lower = text.lower()
    # Normalize structural characters to isolate strict individual words natively
    padded_text = " " + text_lower.replace(",", " ").replace(".", " ").replace("\n", " ").replace("/", " ") + " "
    
    all_known_skills = {skill.lower() for cat in SKILLS_DB.values() for skill in cat}
    all_known_skills.update({"python", "java", "sql", "react", "node", "ml", "c++", "c#", "aws", "docker", "kubernetes", "javascript", "typescript", "html", "css", "flask", "django", "pandas", "numpy", "tableau", "data analysis", "data analyst", "power bi", "looker", "snowflake", "excel"})
    
    # 3. FIX SKILL EXTRACTION (Return skills if present natively in text boundaries)
    for skill in all_known_skills:
        if f" {skill} " in padded_text:
            found_skills.add(skill.title())
            
    return sorted(list(found_skills))

def analyze_resume_full(resume_text: str, job_description: str, job_title: str = "") -> dict:
    sections = extract_sections(resume_text)
    
    edu_text = sections["education"] if sections["education"].strip() else resume_text[:500] 
    exp_text = sections["experience"] if sections["experience"].strip() else resume_text
    
    raw_candidate_skills = extract_exact_skills(resume_text)
    raw_job_skills = extract_exact_skills(job_description)
    
    # 1. DEBUG EXTRACTION
    print(f"[DEBUG] raw_candidate_skills: {raw_candidate_skills}")
    print(f"[DEBUG] raw_job_skills: {raw_job_skills}")
    
    # 2. FIX JOB DESCRIPTION
    if not raw_job_skills:
        cleaned_title = job_title.lower().strip()
        if cleaned_title in DEFAULT_ROLE_SKILLS:
            print(f"[DEBUG] Injecting DEFAULT_ROLE_SKILLS fallback for role: {cleaned_title}")
            for fallback_skill in DEFAULT_ROLE_SKILLS[cleaned_title]:
                raw_job_skills.append(fallback_skill.title())

    candidate_categories = get_categories_for_skills(raw_candidate_skills)
    job_categories = get_categories_for_skills(raw_job_skills)
    
    print(f"[DEBUG] mapped candidate_categories: {candidate_categories}")
    print(f"[DEBUG] mapped job_categories: {job_categories}")
    
    # Category Match (60%)
    if not job_categories:
        cat_score = 1.0 if candidate_categories else 0.0
    else:
        matched_counter = len(candidate_categories.intersection(job_categories))
        cat_score = min(matched_counter / len(job_categories), 1.0)
        
    # Experience (25%)
    years_exp = extract_years_experience(exp_text)
    job_exp_matches = re.findall(r'(\d+)\s*(?:years?|yrs)', job_description, re.IGNORECASE)
    req_years = max([int(n) for n in job_exp_matches]) if job_exp_matches else 1
    exp_score = min(years_exp / req_years, 1.0) if req_years else 1.0
    
    # Role-Aware Overqualification Reward System
    bonus = 0.0
    if years_exp > req_years:
        bonus = min(0.05, (years_exp - req_years) * 0.01) 
        
    # Education (15%)
    edu_keywords = ["degree", "bachelor", "master", "ph.d", "b.s", "m.s", "university", "college"]
    has_edu = any(k in edu_text.lower() for k in edu_keywords)
    job_wants_edu = any(k in job_description.lower() for k in edu_keywords)
    
    if job_wants_edu and has_edu:
        edu_score = 1.0
    elif not job_wants_edu:
        edu_score = 1.0
    else:
        edu_score = 0.5
        
    # Composite Normalization
    final_score = (cat_score * 0.60) + (exp_score * 0.25) + (edu_score * 0.15) + bonus
    final_score = min(1.0, final_score)
    final_score_100 = int(final_score * 100)
    
    rec = "Strong Fit" if final_score_100 >= 75 else "Moderate Fit" if final_score_100 >= 50 else "Weak Fit"
    
    matched_cats = list(candidate_categories.intersection(job_categories))
    missing_cats = list(job_categories.difference(candidate_categories))
    
    return {
        "skills": raw_candidate_skills,
        "matched_categories": [c.replace("_", " ").title() for c in matched_cats],
        "missing_categories": [c.replace("_", " ").title() for c in missing_cats],
        "education": edu_text.strip()[:300] + ("..." if len(edu_text) > 300 else "") if edu_text.strip() else "Not specified",
        "experience": exp_text.strip()[:300] + ("..." if len(exp_text) > 300 else "") if exp_text.strip() else "Not specified",
        "years_of_experience": f"{years_exp:.1f}",
        "score": final_score_100,
        "recommendation": rec
    }
