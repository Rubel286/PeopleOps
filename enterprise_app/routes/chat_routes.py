from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
import json
from enterprise_app.services.chatbot_service import generate_chat_response

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")

@chat_bp.route("/", methods=["POST"])
@login_required
def chat():
    data = request.json
    user_message = data.get("message", "").strip()
    
    if not user_message:
        return jsonify({"success": False, "error": "No message provided."}), 400
        
    try:
        # Pass to Gemini strictly controlled wrapper
        bot_response = generate_chat_response(user_message)
        
        # Determine if Gemini returned our strict JSON command dictionary
        if '{"command":' in bot_response and '"redirect"' in bot_response:
            try:
                # Strip markdown codeblocks if it wrapped them
                cleaned = bot_response.replace("```json", "").replace("```", "").strip()
                payload = json.loads(cleaned)
                return jsonify({
                    "success": True, 
                    "type": "command", 
                    "payload": payload
                })
            except Exception:
                pass # Fallback to standard text response if it mangled the json
                
        # Standard natural language text response
        return jsonify({
            "success": True, 
            "type": "text", 
            "reply": bot_response.strip()
        })
        
    except Exception as e:
        # E.g. API key missing or quota exhaustion
        print(f"Chatbot Error: {str(e)}")
        return jsonify({
            "success": False, 
            "error": "The AI Assistant is currently unavailable. Please check API Key configuration."
        }), 500
