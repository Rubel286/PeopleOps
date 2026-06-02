from datetime import datetime
from bson.decimal128 import Decimal128
from enterprise_app.utils import safe_number

def calculate_tenure_years(start_date):
    if not start_date:
        return 0
    delta = datetime.utcnow() - start_date
    return delta.days / 365.25

def generate_appraisal(employee, performance_score, department_avg_salary):
    """
    Given an Employee document, their latest performance score (out of 5),
    and the department average salary, mathematically determine their hike %
    based on strict Finance-grade parameters.
    """
    current_salary = safe_number(employee.get("base_salary", 0))
    start_date = employee.get("start_date")
    
    tenure_years = calculate_tenure_years(start_date)
    score = safe_number(performance_score)
    dept_avg = safe_number(department_avg_salary)

    justifications = []
    hike_percent = 0.0

    # 1. Base Hike (Performance)
    if score >= 4.5:
        hike_percent += 12.0
        justifications.append("Exceptional Performance (Score >= 4.5): +12.0%")
    elif score >= 3.5:
        hike_percent += 8.0
        justifications.append("Strong Performance (Score >= 3.5): +8.0%")
    elif score >= 2.5:
        hike_percent += 4.0
        justifications.append("Average Performance (Score >= 2.5): +4.0%")
    else:
        hike_percent += 0.0
        justifications.append("Needs Improvement (Score < 2.5): +0.0%")

    # 2. Loyalty Multiplier (Tenure)
    if tenure_years > 5:
        hike_percent += 3.0
        justifications.append(f"Loyalty Multiplier (> 5 Years Tenure): +3.0%")
    elif tenure_years > 2:
        hike_percent += 1.5
        justifications.append(f"Loyalty Multiplier (> 2 Years Tenure): +1.5%")

    # 3. Market Adjustment (Department Logic)
    # If the employee is making 15% less than the department average, we correct them.
    if current_salary > 0 and dept_avg > 0:
        if current_salary < (dept_avg * 0.85):
            hike_percent += 2.0
            justifications.append("Market Adjustment (Salary < 15% below Dept Avg): +2.0%")

    new_salary = current_salary * (1 + (hike_percent / 100))

    return {
        "current_salary": round(current_salary, 2),
        "suggested_hike_percent": round(hike_percent, 2),
        "new_salary": round(new_salary, 2),
        "justification": justifications,
        "tenure_years": round(tenure_years, 1),
        "performance_score": round(score, 1)
    }
