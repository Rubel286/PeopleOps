from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from enterprise_app.decorators import admin_required, employee_required
from enterprise_app import mongo
from bson.objectid import ObjectId
from datetime import datetime
from enterprise_app.utils import log_activity, safe_number, sanitize_numbers

performance_bp = Blueprint('performance', __name__, url_prefix='/performance')

def get_current_cycle():
    """Auto-calculate current quarterly cycle, e.g., '2026-Q1'."""
    now = datetime.utcnow()
    year = now.year
    quarter = (now.month - 1) // 3 + 1
    return f"{year}-Q{quarter}"

def analyze_performance(reviews):
    if not reviews:
        return {"overall": 0.0, "trend": "N/A", "strengths": ["Insufficient data"], "weaknesses": ["Insufficient data"], "summary": "No performance data available."}
        
    scores = []
    for r in reviews:
        ratings = r.get('ratings', {})
        if isinstance(ratings, dict):
            overall = ratings.get('overall', r.get('rating', 0))
            scores.append(safe_number(overall))
        else:
            scores.append(safe_number(r.get('rating', 0)))
            
    trend = "Stable"
    if len(scores) >= 2:
        if scores[0] > scores[1]:
            trend = "Improving ↗"
        elif scores[0] < scores[1]:
            trend = "Declining ↘"
            
    overall_avg = round(sum(scores) / len(scores), 1) if scores else 0.0
    
    latest = reviews[0]
    strengths, weaknesses = [], []
    ratings = latest.get('ratings', {})
    
    if isinstance(ratings, dict):
        if safe_number(ratings.get('skills', 3)) >= 4: strengths.append("Technical Skills")
        elif safe_number(ratings.get('skills', 3)) <= 2.5: weaknesses.append("Technical Skills")
        if safe_number(ratings.get('teamwork', 3)) >= 4: strengths.append("Teamwork")
        elif safe_number(ratings.get('teamwork', 3)) <= 2.5: weaknesses.append("Teamwork")
        
    if not strengths: strengths = ["Consistent Performer"]
    if not weaknesses: weaknesses = ["No critical weaknesses"]
    
    summary = f"Maintaining an overall score of {overall_avg}/5.0 with a {trend.lower()} trajectory. Primary strengths include {', '.join(strengths)}."
    
    return {
        "overall": overall_avg,
        "trend": trend,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "summary": summary
    }

@performance_bp.route('/admin/dashboard')
@admin_required
def admin_performance_dashboard():
    reviews = []
    raw_reviews = list(mongo.db.performance_reviews.find().sort('timestamp', -1).limit(10))

    # Safe average calculation - convert Decimal128 to float
    total = 0.0
    count = 0
    for raw in raw_reviews:
        overall_val = None
        if 'ratings' in raw and isinstance(raw['ratings'], dict) and 'overall' in raw['ratings']:
            overall_val = raw['ratings']['overall']
        elif 'rating' in raw:
            overall_val = raw['rating']

        if overall_val is not None:
            # Convert Decimal128 / other types safely
            try:
                total += safe_number(overall_val)
                count += 1
            except (TypeError, ValueError):
                pass  # skip invalid values

    avg_overall = round(total / count, 1) if count > 0 else 0.0

    for raw in raw_reviews:
        emp = mongo.db.employees.find_one({'_id': raw['employee_id']})
        emp_name = emp['name'] if emp else 'Unknown'

        ratings = raw.get('ratings', {}) if isinstance(raw.get('ratings'), dict) else {}
        goals = raw.get('goals', [])

        # Safe completed goals count: handle both string list and dict list
        completed_goals = 0
        if isinstance(goals, list) and goals:
            if isinstance(goals[0], dict):
                completed_goals = len([g for g in goals if g.get('status') == 'Completed'])
            else:
                completed_goals = len(goals)  # old string goals - assume all completed

        reviews.append({
            'employee_name': emp_name,
            'cycle': raw.get('cycle', 'N/A'),
            'skills': ratings.get('skills', 'N/A'),
            'teamwork': ratings.get('teamwork', 'N/A'),
            'overall': ratings.get('overall', raw.get('rating', 'N/A')),  # fallback to old 'rating'
            'goals_count': len(goals),
            'completed_goals': completed_goals,
            'feedback': raw.get('feedback', 'No feedback')[:100] + '...' if len(raw.get('feedback', '')) > 100 else raw.get('feedback', 'No feedback'),
            'timestamp': raw.get('timestamp', 'N/A')
        })

    insights = analyze_performance(raw_reviews)
    return render_template('performance/admin_dashboard.html', reviews=sanitize_numbers(reviews), avg_overall=sanitize_numbers(avg_overall), insights=sanitize_numbers(insights))

@performance_bp.route('/submit/<employee_id>', methods=['GET', 'POST'])
@admin_required
def submit_review(employee_id):
    employee = mongo.db.employees.find_one_or_404({'_id': ObjectId(employee_id)})
    cycle = get_current_cycle()
    existing_review = mongo.db.performance_reviews.find_one({'employee_id': ObjectId(employee_id), 'cycle': cycle})

    if request.method == 'POST':
        ratings = {
            'skills': int(request.form['skills']),
            'teamwork': int(request.form['teamwork']),
            'overall': (int(request.form['skills']) + int(request.form['teamwork'])) / 2
        }
        review = {
            'employee_id': ObjectId(employee_id),
            'reviewer_id': current_user.id,
            'cycle': cycle,
            'goals': existing_review.get('goals', []) if existing_review else [],
            'ratings': ratings,
            'feedback': request.form['feedback'],
            'self_feedback': request.form.get('self_feedback', ''),
            'timestamp': datetime.utcnow()
        }
        mongo.db.performance_reviews.update_one(
            {'employee_id': ObjectId(employee_id), 'cycle': cycle},
            {'$set': review},
            upsert=True
        )
        log_activity('performance_review_submitted', {'employee_id': employee_id, 'cycle': cycle})
        flash('Review submitted successfully.', 'success')
        return redirect(url_for('performance.admin_performance_dashboard'))

    return render_template('performance/submit_review.html', employee=employee, existing_review=existing_review, cycle=cycle)

@performance_bp.route('/view/history')
@employee_required
def view_history():
    employee = mongo.db.employees.find_one({'email': current_user.email})
    reviews = list(mongo.db.performance_reviews.find({'employee_id': employee['_id']}).sort('timestamp', -1))
    insights = analyze_performance(reviews)
    return render_template('performance/view_history.html', reviews=sanitize_numbers(reviews), insights=sanitize_numbers(insights))

@performance_bp.route('/set_goals', methods=['GET', 'POST'])
@employee_required
def set_goals():
    employee = mongo.db.employees.find_one({'email': current_user.email})
    cycle = get_current_cycle()
    review = mongo.db.performance_reviews.find_one({'employee_id': employee['_id'], 'cycle': cycle}) or {}

    if request.method == 'POST':
        goals_text = request.form['goals'].strip()
        goals = []
        if goals_text:
            for line in goals_text.split('\n'):
                goal_str = line.strip()
                if goal_str:
                    goals.append({'goal': goal_str, 'progress': 0, 'status': 'Pending'})
        mongo.db.performance_reviews.update_one(
            {'employee_id': employee['_id'], 'cycle': cycle},
            {'$set': {'goals': goals}},
            upsert=True
        )
        flash('Goals set for this cycle.', 'success')
        return redirect(url_for('employee_portal.dashboard'))

    return render_template('performance/set_goals.html', cycle=cycle, existing_goals=review.get('goals', []))

@performance_bp.route('/update_progress/<int:goal_index>', methods=['POST'])
@employee_required
def update_progress(goal_index):
    employee = mongo.db.employees.find_one({'email': current_user.email})
    cycle = get_current_cycle()
    progress = int(request.form.get('progress', 0))
    if progress < 0 or progress > 100:
        progress = 0

    mongo.db.performance_reviews.update_one(
        {'employee_id': employee['_id'], 'cycle': cycle},
        {'$set': {f'goals.{goal_index}.progress': progress}}
    )
    flash('Goal progress updated.', 'success')
    return redirect(url_for('employee_portal.dashboard'))