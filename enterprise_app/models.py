class User:
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.email = user_data['email']
        self.password_hash = user_data['password_hash']
        self.role = user_data.get('role', 'candidate')
        # --- FIX: Store the user's name on the object ---
        self.name = user_data.get('name', '') # Get name, default to empty string
    
    @property
    def is_active(self): return True
    @property
    def is_authenticated(self): return True
    @property
    def is_anonymous(self): return False
    def get_id(self): return self.id

class PayrollHistory:
    def __init__(self, data):
        self.employee_id = data['employee_id']
        self.period = data['period']
        self.gross = data['gross']
        self.taxes = data['taxes']
        self.net_pay = data['net_pay']
        self.timestamp = data['timestamp']

class PerformanceReview:
    def __init__(self, data):
        self.employee_id = data['employee_id']
        self.reviewer_id = data['reviewer_id']
        self.cycle = data['cycle']  # e.g., '2026-Q1'
        self.goals = data.get('goals', [])  # List of {'goal': str, 'progress': int (0-100), 'status': 'Pending/Completed'}
        self.ratings = data.get('ratings', {})  # Dict like {'skills': 4, 'teamwork': 5, 'overall': 4.5}
        self.feedback = data['feedback']
        self.self_feedback = data.get('self_feedback', '')  # Employee's own comments
        self.timestamp = data['timestamp']