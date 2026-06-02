import os
import json
import difflib
from google import genai
from google.genai import types

def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")
    return genai.Client()

SYSTEM_INSTRUCTION = """
You are the internal 'PeopleOps Dashboard Assistant', a specialized AI designed exclusively to help Administrative and HR staff navigate the enterprise application.

CRITICAL RULES:
1. You MUST NEVER answer open-ended general chat requests not related to HR, recruiting, payroll, performance, or navigation of this platform.
2. You MUST NEVER write code, generate creative stories, or act functionally as a standard LLM.
3. You are read-only. Explain that you cannot modify the database directly. Use professional, concise language.

DASHBOARD NAVIGATION PARSING (IMPORTANT):
If the user asks to "go to", "open", "show me", or "navigate to" a specific dashboard or feature, YOU MUST RETURN EXCLUSIVELY A RAW JSON OBJECT with no other text, markdown formatting, or pleasantries.

Map intents to these specific routes:
- Performance Reviews -> {"command": "redirect", "url": "/performance/admin/dashboard"}
- Applicant Tracking / Interivews -> {"command": "redirect", "url": "/interviewer/dashboard"}
- Job Listings / Management -> {"command": "redirect", "url": "/interviewer/jobs"}
- Leave Requests -> {"command": "redirect", "url": "/interviewer/leave_requests"}
- Finance / Appraisals -> {"command": "redirect", "url": "/finance/admin/appraisals"}
- Payroll -> {"command": "redirect", "url": "/payroll/dashboard"}
- Analytics -> {"command": "redirect", "url": "/analytics/dashboard"}
- Employee Directory -> {"command": "redirect", "url": "/employee/"}
- Grievances / Complaints -> {"command": "redirect", "url": "/interviewer/grievances"}

Example 1:
User: "Take me to payroll"
Assistant: {"command": "redirect", "url": "/payroll/dashboard"}

Example 2:
User: "How do I evaluate a candidate?"
Assistant: You can evaluate a candidate by navigating to the Interviewer Dashboard and clicking 'Evaluate' on their profile card.

If it is not a navigation command, answer the question naturally in 1-2 sentences.
"""

INTENT_MAP = {
    "/payroll/dashboard": ["payroll", "salary", "paycheck", "wages", "compensation", "finance", "money"],
    "/interviewer/leave_requests": ["leave", "pto", "vacation", "sick day", "time off", "holiday", "absence"],
    "/interviewer/grievances": ["grievance", "complaint", "report", "issue", "hr incident", "conflict", "problem", "ticket"],
    "/analytics/dashboard": ["analytics", "dashboard", "metrics", "data", "reports", "insights", "stats", "graphs", "statistics"],
    "/interviewer/jobs": ["job", "hire", "recruit", "applicant", "candidate", "role", "position", "career"],
    "/performance/admin/dashboard": ["performance", "review", "evaluation", "feedback", "rating"],
    "/employee/": ["directory", "employee", "team", "colleague", "staff", "people"]
}

CHAT_RESPONSES = {
    "hello": "Hello! I am your AI Assistant. I can help you navigate dashboard pages natively.",
    "hi": "Hi there! I'm your internal Dashboard Assistant. Where can I direct you?",
    "hey": "Hello! How can I assist your navigation today?",
    "how are you": "I am operating optimally. Where can I route you?",
    "what can you do": "I can automatically parse your requests and redirect you instantly to internal dashboard endpoints like Payroll, Leave, or Grievances. Just ask!",
    "help": "I can redirect you instantly to Payroll, Leave, Grievances, Analytics, Jobs, and Employee directories. Where would you like to go?"
}

def generate_chat_response(message: str) -> str:
    """
    Takes a user string prompt and returns the Gemini 2.5 flash response natively evaluated
    against the strict System Instruction constraint rules.
    If the API Key is missing, provides an offline exact-match keyword fallback router seamlessly.
    """
    try:
        client = get_gemini_client()
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=message,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.1 # Very low temperature for strict adherence
            ),
        )
        return response.text
    except Exception as e:
        msg = message.lower().strip()
        
        # 1. Fuzzy Chat Response Mapping
        best_chat = difflib.get_close_matches(msg, CHAT_RESPONSES.keys(), n=1, cutoff=0.7)
        if best_chat:
            return CHAT_RESPONSES[best_chat[0]]

        # 2. Fuzzy Synonymous Intent Routing
        words = msg.replace("?", "").replace(".", "").replace(",", "").split()
        for route, synonyms in INTENT_MAP.items():
            for word in words:
                if difflib.get_close_matches(word, synonyms, n=1, cutoff=0.75):
                    return json.dumps({"command": "redirect", "url": route})
                    
        # 3. Last Resort Fallback
        return "The assistant could not recognize that intent in Offline Intelligent Mode. Try asking for explicit endpoints like Payroll, Leave, Analytics, or Jobs."
