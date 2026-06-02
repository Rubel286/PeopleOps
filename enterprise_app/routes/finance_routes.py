from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, jsonify, send_file
)
from flask_login import login_required, current_user
from bson.objectid import ObjectId
from bson.decimal128 import Decimal128
from datetime import datetime
import io
import csv

from enterprise_app import mongo
from enterprise_app.decorators import admin_required, employee_required
from enterprise_app.utils import safe_number, calculate_payroll, generate_payslip_pdf, log_activity, sanitize_numbers
from enterprise_app.tasks import send_email_task
from enterprise_app.services.appraisal_service import generate_appraisal

finance_bp = Blueprint("finance", __name__, url_prefix="/finance")

# ============================================================
# COLLECTION NAMES
# ============================================================

COL_PAYROLL_RUNS = "payroll_runs"
COL_PAYSLIPS = "payslips"
COL_ADJUSTMENTS = "payroll_adjustments"
COL_AUDIT = "audit_logs"


# ============================================================
# HELPERS
# ============================================================



def get_payroll_summary():
    employees = list(mongo.db.employees.find())

    total_salary = sum(safe_number(emp.get("base_salary", 0)) for emp in employees)
    avg_salary = total_salary / len(employees) if employees else 0

    intern_salaries = [safe_number(emp.get("base_salary", 0)) for emp in employees if 'intern' in emp.get("employee_type", "").lower() or 'intern' in emp.get("role", "").lower()]
    fulltime_salaries = [safe_number(emp.get("base_salary", 0)) for emp in employees if 'intern' not in emp.get("employee_type", "").lower() and 'intern' not in emp.get("role", "").lower()]

    avg_intern = sum(intern_salaries) / len(intern_salaries) if intern_salaries else 0
    avg_fulltime = sum(fulltime_salaries) / len(fulltime_salaries) if fulltime_salaries else 0
    
    cashflow_reserve = 500000000 - total_salary  # Base mocked 50Cr reserve minus payroll 

    last_run = mongo.db[COL_PAYROLL_RUNS].find_one(
        sort=[("created_at", -1)]
    )

    return {
        "employee_count": len(employees),
        "total_payroll": total_salary,
        "avg_salary": avg_salary,
        "avg_intern": avg_intern,
        "avg_fulltime": avg_fulltime,
        "total_interns": len(intern_salaries),
        "total_fulltime": len(fulltime_salaries),
        "cashflow_reserve": cashflow_reserve,
        "last_run": last_run
    }


def get_payroll_trends():
    runs = list(
        mongo.db[COL_PAYROLL_RUNS]
        .find({"status": "completed"})
        .sort("period", 1)
    )

    labels = [r["period"] for r in runs]
    data = [r.get("total_payout", 0) for r in runs]

    return {
        "labels": labels,
        "data": data
    }


def log_audit(action, details=None):
    mongo.db[COL_AUDIT].insert_one({
        "user": current_user.email,
        "action": action,
        "details": details or {},
        "timestamp": datetime.utcnow()
    })


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@finance_bp.route("/admin/dashboard")
@admin_required
def admin_dashboard():

    summary = get_payroll_summary()
    trends = get_payroll_trends()

    history = list(
        mongo.db[COL_PAYROLL_RUNS]
        .find()
        .sort("created_at", -1)
        .limit(20)
    )

    adjustments = list(
        mongo.db[COL_ADJUSTMENTS]
        .find({"status": "pending"})
        .sort("created_at", -1)
    )

    months = []
    now = datetime.utcnow()
    for i in range(12):
        m = datetime(now.year, now.month, 1)
        m = m.replace(month=((now.month - i - 1) % 12) + 1)
        months.append(m.strftime("%Y-%m"))

    t_data = trends.get("data", [])
    payroll_trend = "Stable"
    anomalies = []
    
    if len(t_data) >= 2:
        prev, curr = t_data[-2], t_data[-1]
        if curr > prev:
            diff_pct = ((curr - prev) / prev) * 100 if prev else 100
            payroll_trend = f"Increasing ↗ (+{diff_pct:.1f}%)"
            if diff_pct > 15:
                anomalies.append(f"Payroll Anomaly: Latest period jumped heavily by {diff_pct:.0f}%")
        elif curr < prev:
            diff_pct = ((prev - curr) / prev) * 100 if prev else 100
            payroll_trend = f"Decreasing ↘ (-{diff_pct:.1f}%)"
            
    if len(adjustments) >= 5:
        anomalies.append(f"Operational Bottleneck: High volume of unfinished adjustments ({len(adjustments)})")
        
    insights = {
        "payroll_trend": payroll_trend,
        "employees_affected": summary.get("employee_count", 0),
        "pending_adjustments": len(adjustments),
        "anomalies": anomalies or ["Secure: Operating within normal baseline limits"]
    }

    return render_template(
        "finance/admin_run_payroll.html",
        summary=sanitize_numbers(summary),
        trends=sanitize_numbers(trends),
        history=sanitize_numbers(history),
        months=months,
        adjustments=sanitize_numbers(adjustments),
        insights=sanitize_numbers(insights)
    )

# ============================================================
# APPRAISALS
# ============================================================

@finance_bp.route("/admin/appraisals")
@admin_required
def appraisals():
    from collections import defaultdict
    employees = list(mongo.db.employees.find())
    
    # 1. Calculate Department Averages dynamically
    dept_totals = defaultdict(float)
    dept_counts = defaultdict(int)
    for emp in employees:
        dept = emp.get("department", "General")
        dept_totals[dept] += safe_number(emp.get("base_salary", 0))
        dept_counts[dept] += 1
        
    dept_averages = {k: v / dept_counts[k] for k, v in dept_totals.items()}
    
    # 2. Extract Latest Performance Score mapping
    # Note: A real system might only fetch the CURRENT cycle. We fetch the latest matching review.
    reviews = list(mongo.db.performance_reviews.find().sort("timestamp", -1))
    emp_scores = {}
    for r in reviews:
        emp_id = str(r["employee_id"])
        if emp_id not in emp_scores:
            # Safely grab "overall" rating
            ratings = r.get("ratings", {})
            if isinstance(ratings, dict):
                emp_scores[emp_id] = safe_number(ratings.get("overall", 0.0))
            else:
                emp_scores[emp_id] = safe_number(r.get("rating", 0.0))

    # 3. Process every employee through the Deterministic Appraisal Engine
    appraisal_results = []
    budget_impact = 0.0
    
    for emp in employees:
        dept = emp.get("department", "General")
        score = emp_scores.get(str(emp["_id"]), 0.0)
        
        # Check if they were already appraised recently (e.g. this year).
        # For simplicity, we just look up if they have an appraisal log this year.
        current_year = datetime.utcnow().year
        existing_log = mongo.db.appraisal_logs.find_one({
            "employee_id": str(emp["_id"]),
            "timestamp": {"$gte": datetime(current_year, 1, 1)}
        })
        
        if not existing_log:
            res = generate_appraisal(emp, score, dept_averages.get(dept, 0.0))
            if res["suggested_hike_percent"] > 0:
                budget_impact += (res["new_salary"] - res["current_salary"])
                appraisal_results.append({
                    "employee_id": str(emp["_id"]),
                    "name": emp.get("name", "Unknown"),
                    "department": dept,
                    "performance": res["performance_score"],
                    "tenure": res["tenure_years"],
                    "current_salary": res["current_salary"],
                    "suggested_hike": res["suggested_hike_percent"],
                    "new_salary": res["new_salary"],
                    "justification": res["justification"]
                })
                
    # Sort by highest hike
    appraisal_results.sort(key=lambda x: x["suggested_hike"], reverse=True)

    return render_template(
        "finance/appraisals.html", 
        appraisals=sanitize_numbers(appraisal_results),
        budget_impact=sanitize_numbers(budget_impact),
        pending_count=len(appraisal_results)
    )

@finance_bp.route("/admin/appraisals/approve", methods=["POST"])
@admin_required
def approve_appraisal():
    if request.is_json:
        data = request.json
    else:
        data = request.form
        
    emp_id = data.get("employee_id")
    new_salary = data.get("new_salary")
    hike_percent = data.get("hike_percent")
    justification = data.get("justification", "Deterministically approved by Finance Admin.")
    
    emp = mongo.db.employees.find_one({"_id": ObjectId(emp_id)})
    if not emp:
        if request.is_json:
            return jsonify({"success": False, "error": "Employee not found."}), 404
        flash("Employee not found.", "danger")
        return redirect(url_for("finance.appraisals"))
        
    old_salary = emp.get("base_salary", 0)
    
    # 1. Update Employee Base Salary
    mongo.db.employees.update_one(
        {"_id": ObjectId(emp_id)},
        {"$set": {"base_salary": float(new_salary)}}
    )
    
    # 2. Write strictly to Finance Audit Logs
    mongo.db.appraisal_logs.insert_one({
        "employee_id": str(emp_id),
        "employee_name": emp["name"],
        "old_salary": float(old_salary),
        "new_salary": float(new_salary),
        "hike_percent": float(hike_percent),
        "justification": justification,
        "approved_by": current_user.email,
        "timestamp": datetime.utcnow()
    })
    
    if request.is_json:
        return jsonify({"success": True})
    
    flash("Appraisal Approved. Employee Base Salary updated.", "success")
    return redirect(url_for("finance.appraisals"))


# ============================================================
# RUN PAYROLL
# ============================================================

@finance_bp.route("/admin/run", methods=["POST"])
@admin_required
def run_payroll():

    period = request.form.get("month")
    dry_run = request.form.get("dry_run") == "on"

    if not period:
        flash("Period required", "danger")
        return redirect(url_for("finance.admin_dashboard"))

    employees = list(mongo.db.employees.find())

    run_id = mongo.db[COL_PAYROLL_RUNS].insert_one({
        "period": period,
        "status": "processing",
        "created_by": current_user.email,
        "created_at": datetime.utcnow(),
        "dry_run": dry_run,
        "employee_count": len(employees),
        "total_payout": 0
    }).inserted_id

    total_payout = 0
    processed = 0

    for emp in employees:

        payroll = calculate_payroll(emp)

        total_payout += payroll["net_pay"]
        processed += 1

        if not dry_run:

            pdf = generate_payslip_pdf(emp, payroll)

            payslip_id = mongo.db[COL_PAYSLIPS].insert_one({
                "run_id": run_id,
                "employee_id": emp["_id"],
                "period": period,
                "gross": payroll["gross"],
                "taxes": payroll["taxes"],
                "net_pay": payroll["net_pay"],
                "created_at": datetime.utcnow()
            }).inserted_id

            import base64
            pdf_b64 = base64.b64encode(pdf).decode("ascii") if pdf else None
            
            send_email_task.delay(
                email_type="payslip",
                recipient=emp["email"],
                context={"period": period, "pdf_data": pdf_b64}
            )

    mongo.db[COL_PAYROLL_RUNS].update_one(
        {"_id": run_id},
        {"$set": {
            "status": "completed",
            "total_payout": total_payout,
            "processed": processed
        }}
    )

    log_audit("payroll_run", {
        "run_id": str(run_id),
        "period": period,
        "total": total_payout
    })

    flash("Payroll run completed", "success")

    return redirect(url_for("finance.admin_dashboard"))


# ============================================================
# RUN DETAILS
# ============================================================

@finance_bp.route("/admin/run/<run_id>")
@admin_required
def run_details(run_id):

    run = mongo.db[COL_PAYROLL_RUNS].find_one(
        {"_id": ObjectId(run_id)}
    )

    payslips = list(
        mongo.db[COL_PAYSLIPS]
        .find({"run_id": ObjectId(run_id)})
    )

    return render_template(
        "payroll/admin_run_details.html",
        run=sanitize_numbers(run),
        payslips=sanitize_numbers(payslips)
    )


# ============================================================
# EXPORT CSV
# ============================================================

@finance_bp.route("/admin/run/<run_id>/csv")
@admin_required
def export_csv(run_id):

    payslips = mongo.db[COL_PAYSLIPS].find({
        "run_id": ObjectId(run_id)
    })

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Employee ID",
        "Period",
        "Gross",
        "Taxes",
        "Net Pay"
    ])

    for p in payslips:
        writer.writerow([
            str(p["employee_id"]),
            p["period"],
            p["gross"],
            p["taxes"],
            p["net_pay"]
        ])

    output.seek(0)

    return send_file(
        io.BytesIO(output.read().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"payroll_{run_id}.csv"
    )


# ============================================================
# EMPLOYEE DASHBOARD
# ============================================================

@finance_bp.route("/employee/dashboard")
@employee_required
def employee_dashboard():

    employee = mongo.db.employees.find_one({
        "email": current_user.email
    })

    if not employee:
        flash("You are not registered as an active employee.", "warning")
        return redirect(url_for('main.index'))

    payslips = list(
        mongo.db[COL_PAYSLIPS]
        .find({"employee_id": employee["_id"]})
        .sort("period", -1)
    )

    total_ytd = sum(p["net_pay"] for p in payslips)

    return render_template(
        "finance/employee_payslips.html",
        payslips=sanitize_numbers(payslips),
        total_ytd=sanitize_numbers(total_ytd)
    )


# ============================================================
# DOWNLOAD PAYSLIP PDF
# ============================================================

@finance_bp.route("/employee/payslip/<payslip_id>")
@employee_required
def download_payslip(payslip_id):

    payslip = mongo.db[COL_PAYSLIPS].find_one({
        "_id": ObjectId(payslip_id)
    })

    employee = mongo.db.employees.find_one({
        "_id": payslip["employee_id"]
    })

    payroll = {
        "period": payslip["period"],
        "gross": payslip["gross"],
        "taxes": payslip["taxes"],
        "net_pay": payslip["net_pay"]
    }

    pdf = generate_payslip_pdf(employee, payroll)

    return send_file(
        io.BytesIO(pdf),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"payslip_{payslip['period']}.pdf"
    )


# ============================================================
# ADJUSTMENT REQUESTS
# ============================================================

@finance_bp.route("/employee/request-adjustment", methods=["POST"])
@employee_required
def request_adjustment():

    amount = float(request.form.get("amount", 0))
    reason = request.form.get("reason")

    employee = mongo.db.employees.find_one({
        "email": current_user.email
    })

    mongo.db[COL_ADJUSTMENTS].insert_one({
        "employee_id": employee["_id"],
        "amount": amount,
        "reason": reason,
        "status": "pending",
        "created_at": datetime.utcnow()
    })

    flash("Adjustment request submitted", "success")

    return redirect(url_for("finance.employee_dashboard"))
